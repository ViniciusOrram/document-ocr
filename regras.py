"""Extração por regras (sem LLM) do modelo fixo de contrato: Ficha Cadastral (PJ ou PF) + Cédula de Crédito Bancário.

Retorna só os campos cujo rótulo foi encontrado (valor None = rótulo presente mas vazio no documento).
Campos ausentes do retorno vão para o LLM como fallback.
"""
import re

# Ficha Cadastral: o valor fica na mesma linha do rótulo ou logo abaixo, na mesma coluna.
# ("conjuge", rótulo) = rótulo procurado só abaixo do título "Dados do Cônjuge" (PF repete Nome/CPF/Telefone/E-mail ali)
FICHA_PJ = {
    "data_cadastro": "Data do Cadastro:",
    "codigo_cliente": "Cód. Cliente :",
    "razao_social": "Razão Social:",
    "nome_fantasia": "Nome Fantasia:",
    "cnpj": "CNPJ:",
    "tipo_societario": "Tipo Societário:",
    "atividade": "Atividade:",
    "endereco_comercial": "Endereço Comercial:",
    "endereco_numero": "Número:",
    "endereco_complemento": "Complemento:",
    "endereco_bairro": "Bairro:",
    "endereco_cep": "CEP:",
    "endereco_cidade": "Cidade:",
    "endereco_estado": "Estado:",
    "email": "E-mail:",
    "faturamento": "Faturamento:",
    "data_abertura": "Data de Abertura:",
    "telefone": "Telefone:",
    "celular": "Celular:",
    "representante_nome": "Nome:",
    "representante_cpf": "CPF:",
    "representante_acoes": "Ações:",
    "conjuge_nome": "Nome (cônjuge):",
    "conjuge_cpf": "CPF (cônjuge):",
    "conjuge_telefone": "Telefone (cônjuge):",
    "conjuge_email": "E-mail (cônjuge):",
}

FICHA_PF = {
    "data_cadastro": "Data do Cadastro:",
    "codigo_cliente": "Cód. Cliente :",
    "nome_completo": "Nome Completo:",
    "cpf": "CPF:",
    "nacionalidade": "Nacionalidade:",
    "data_nascimento": "Data de Nascimento:",
    "rg": "RG:",
    "orgao_rg": "Órgão RG:",
    "data_expedicao_rg": "Data de Expedição:",
    "estado_civil": "Estado Civil:",
    "telefone": "Telefone:",
    "email": "E-mail:",
    "nome_mae": "Nome da Mãe:",
    "nome_pai": "Nome do Pai:",
    "endereco_residencial": "Endereço Residencial:",
    "endereco_numero": "Número:",
    "endereco_complemento": "Complemento:",
    "endereco_bairro": "Bairro:",
    "endereco_cep": "CEP:",
    "endereco_cidade": "Cidade:",
    "endereco_estado": "Estado:",
    "profissao": "Profissão ou atividade:",
    "renda": "Renda:",
    "patrimonio": "Patrimônio:",
    "conjuge_nome": ("conjuge", "Nome Completo:"),
    "conjuge_cpf": ("conjuge", "CPF:"),
    "conjuge_telefone": ("conjuge", "Telefone:"),
    "conjuge_email": ("conjuge", "E-mail:"),
}

# título da página 1 -> (tipo, regras); o tipo é o nome do grupo correspondente no campos.json
FICHAS = {
    "FICHA CADASTRAL PESSOA JURÍDICA": ("pessoa_juridica", FICHA_PJ),
    "FICHA CADASTRAL PESSOA FÍSICA": ("pessoa_fisica", FICHA_PF),
}

# CCB: (seção, rótulo) -> resto da linha. As seções evitam confundir rótulos repetidos (CPF/CNPJ, Cidade...)
CCB = {
    "emitente_razao_social": ("B", "Nome/Razão Social:"),
    "emitente_cpf_cnpj": ("B", "CPF/CNPJ:"),
    "emitente_endereco": ("B", "Endereço:"),
    "emitente_cidade": ("B", "Cidade:"),
    "emitente_uf": ("B", "UF:"),
    "avalista_nome": ("C", "Nome/Razão Social:"),
    "avalista_cpf_cnpj": ("C", "CPF/CNPJ:"),
    "avalista_endereco": ("C", "Endereço:"),
    "avalista_cidade": ("C", "Cidade:"),
    "avalista_uf": ("C", "UF:"),
    "dia_vencimento_parcelas": ("D", "Dia do vencimento das parcelas:"),
    "valor_parcela": ("D", "Valor da parcela:"),
    "quantidade_parcelas": ("D", "Quantidade de parcela:"),
    "valor_somatorio_parcelas": ("D", "Valor do somatório das parcelas:"),
    "vencimento_primeira_parcela": ("D", "Vencimento da 1ª parcela:"),
    "vencimento_ultima_parcela": ("D", "Vencimento da última parcela:"),
    "custo_efetivo_total_aa": ("D", "Custo Efetivo Total % a.a.:"),
    "taxa_juros_am": ("D", "Taxa de Juros % a.m.:"),
    "taxa_juros_aa": ("D", "Taxa de Juros % a.a.:"),
    "garantia_descricao": ("E", "Descrição:"),
    "garantia_valor": ("E", "Valor:"),
    "fiel_depositario_nome": ("E", "Fiel Depositário:"),
    "fiel_depositario_cpf_cnpj": ("E", "CPF/CNPJ:"),
    "fiel_depositario_cidade": ("E", "Cidade:"),
    "fiel_depositario_estado": ("E", "Estado:"),
}

# Componentes do fluxo: rótulo seguido de até dois números (R$ e %); vazio quando a linha não tem valor
FLUXO = {
    "valor_total_devido": "a)Valor total devido:",
    "valor_liberado_vendedor": "b)Valor liberado ao Vendedor:",
    "despesas_concessao": "c)Despesas vinculadas à concessão do crédito:",
    "tarifa_cadastro": "c1)Tarifa de cadastro:",
    "iof": "c2)IOF:",
    "seguro_prestamista": "c3)Seguro Prestamista:",
    "registro_garantia": "c4)Registro de Garantia:",
}

NUM = r"(\d[\d.]*,\d+)"


def ficha(pagina, regras):
    linhas = sorted(
        (l["bbox"][1], l["bbox"][0], "".join(s["text"] for s in l["spans"]).strip())
        for b in pagina.get_text("dict")["blocks"] for l in b.get("lines", [])
    )
    linhas = [(x, y, t) for y, x, t in linhas]  # ordem de leitura: de cima para baixo
    y_conjuge = next((y for _, y, t in linhas if t == "Dados do Cônjuge"), float("inf"))
    rotulos = tuple(r if isinstance(r, str) else r[1] for r in regras.values())
    achados = {}
    for campo, rotulo in regras.items():
        conjuge = not isinstance(rotulo, str)
        if conjuge:
            rotulo = rotulo[1]
        linha = next((l for l in linhas if l[2].startswith(rotulo) and (l[1] > y_conjuge) == conjuge), None)
        if not linha:
            continue
        x, y, texto = linha
        valor = texto[len(rotulo):].strip()
        if not valor:  # valor na linha de baixo, mesma coluna (±3pt), até ~20pt abaixo
            abaixo = [l for l in linhas if abs(l[0] - x) < 3 and 5 < l[1] - y < 20 and not l[2].startswith(rotulos)]
            valor = min(abaixo, key=lambda l: l[1])[2] if abaixo else ""
        achados[campo] = valor or None
    texto = pagina.get_text()
    m = re.search(r"AUTORIZAÇÃO PARA CONSULTA SCR\s*\n\s*(.+)", texto)
    if m:
        achados["autorizacao_scr_local_data"] = m.group(1).strip()
    return achados


def ccb(texto):
    achados = {}
    if m := re.search(r"CÉDULA DE CRÉDITO BANCÁRIO Nº\s*(\S+)", texto):
        achados["ccb_numero"] = m.group(1)
    if m := re.search(r"A - CREDORA:\s*(.+?),\s*CNPJ n\.\s*([\d./-]+),\s*com sede na\s*(.+?)\.?\s*Doravante", texto, re.S):
        achados["credora_razao_social"], achados["credora_cnpj"] = m.group(1).strip(), m.group(2)
        achados["credora_endereco"] = re.sub(r"\s+", " ", m.group(3)).strip()

    inicios = {m.group(1): m.start() for m in re.finditer(r"^\s*([A-F]) - [A-ZÇÃÉ]", texto, re.M)}
    fins = sorted(inicios.values()) + [len(texto)]
    secoes = {k: texto[v:next(f for f in fins if f > v)] for k, v in inicios.items()}

    for campo, (secao, rotulo) in CCB.items():
        if secao in secoes and (m := re.search(re.escape(rotulo) + r"[ \t]*(.*)", secoes[secao])):
            achados[campo] = m.group(1).strip() or None
    if "B" in secoes and "Representante Legal:" in secoes["B"]:  # PF: rótulo presente mas vazio
        m = re.search(r"Representante Legal:[ \t]*([\d./-]+)[ \t]+(.+)", secoes["B"])
        achados["emitente_representante_legal_cpf"] = m.group(1) if m else None
        achados["emitente_representante_legal_nome"] = m.group(2).strip() if m else None
    if "D" in secoes and "Forma de pagamento:" in secoes["D"]:
        m = re.search(r"^\s*X\s+(.+?)\s*$", secoes["D"], re.M)  # opção marcada com X
        achados["forma_pagamento"] = m.group(1) if m else None
    for campo, rotulo in FLUXO.items():
        if m := re.search(re.escape(rotulo) + rf"\s*{NUM}?\s*{NUM}?", texto):
            achados[campo], achados[f"{campo}_pct"] = m.group(1), m.group(2)
    if m := re.search(r"c5\)Descrição da Despesa:[ \t]*(.*)", texto):
        achados["descricao_despesa"] = re.sub(r"\(c5/a\)", "", m.group(1)).strip() or None
    return achados


def extrair(doc):
    """doc: documento pymupdf com as páginas a ler. Detecta cada página pelo título.

    Retorna (tipo, achados); tipo = "pessoa_juridica", "pessoa_fisica" ou None se não achar a ficha.
    """
    tipo, achados = None, {}
    for pagina in doc:
        texto = pagina.get_text()
        for titulo, (t, regras) in FICHAS.items():
            if titulo in texto:
                tipo = t
                achados.update(ficha(pagina, regras))
        if "CÉDULA DE CRÉDITO BANCÁRIO" in texto:
            achados.update(ccb(texto))
    return tipo, achados
