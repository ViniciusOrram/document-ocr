import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pymupdf

import extrator


class TestExtrator(unittest.TestCase):
    def test_lote(self):
        tmp = Path(tempfile.mkdtemp())
        entrada, saida = tmp / "in", tmp / "out"
        entrada.mkdir()
        doc = pymupdf.open()
        for i in range(1, 4):
            doc.new_page().insert_text((72, 72), f"Pagina {i} - Razao Social: EMPRESA EXEMPLO LTDA - CNPJ: 12.345.678/0001-90")
        doc.save(entrada / "digital.pdf")
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "Pag. 1")  # simula PDF digitalizado: quase sem texto
        doc.save(entrada / "digitalizado.pdf")
        (entrada / "quebrado.pdf").write_bytes(b"isso nao e pdf")

        r = mock.Mock()
        r.json.return_value = {"response": '{"cnpj": "12.345.678/0001-90"}', "prompt_eval_count": 123}
        with mock.patch.object(extrator.requests, "post", return_value=r) as post:
            n = extrator.processar(entrada, saida, {"contrato": {"cnpj": "CNPJ"}}, "http://x", "gemma3:4b", [1, 3, 9])  # 9 não existe

        self.assertEqual(n, 3)
        self.assertEqual(post.call_count, 1)  # só o PDF digital chega ao modelo
        enviado = post.call_args.kwargs["json"]
        self.assertEqual(enviado["model"], "gemma3:4b")
        self.assertIn("cnpj", enviado["format"]["properties"])
        self.assertIn("Pagina 1", enviado["prompt"])
        self.assertIn("Pagina 3", enviado["prompt"])
        self.assertNotIn("Pagina 2", enviado["prompt"])

        ler = lambda nome: json.loads((saida / f"{nome}.json").read_text(encoding="utf-8"))
        ok = ler("digital")
        self.assertEqual((ok["paginas"], ok["tokens_extracao"], ok["erro"]), (2, 123, None))
        self.assertEqual(ok["campos"], {"cnpj": "12.345.678/0001-90"})
        self.assertIn("Pagina 3", ok["markdown"])
        self.assertIn("sem texto digital", ler("digitalizado")["erro"])
        self.assertIsNotNone(ler("quebrado")["erro"])

    def test_regras_sem_llm(self):
        tmp = Path(tempfile.mkdtemp())
        entrada, saida = tmp / "in", tmp / "out"
        entrada.mkdir()
        doc = pymupdf.open()
        ficha = doc.new_page()
        ficha.insert_text((180, 85), "FICHA CADASTRAL PESSOA JURÍDICA")
        for x, y, t in [(31, 216, "CNPJ:"), (314, 216, "Atividade:"), (31, 230, "50.388.828/0001-37"),
                        (31, 244, "Endereço Comercial: R DIAMANTE")]:
            ficha.insert_text((x, y), t, fontsize=9)
        def ccb(representante):
            return "\n".join([
                "CÉDULA DE CRÉDITO BANCÁRIO Nº 00000069713",
                "B - EMITENTE:", "Cidade: UBERLANDIA",
                f" Doravante denominado(a) apenas EMITENTE Representante Legal: {representante}",
                "C - AVALISTA:", "Cidade:",
                "D - CARACTERÍSTICAS DO CRÉDITO", "Forma de pagamento:", "X  Boleto Bancário", "  Débito em conta",
                "a)Valor total devido:", "162.309,02", "100,00", "   c4)Registro de Garantia:", "(c4/a)",
                "E - GARANTIA", "Cidade: PORTO ALEGRE",
            ])

        doc.new_page().insert_text((30, 50), ccb("089.657.634-52  Polyana Pessoa"), fontsize=9)
        doc.save(entrada / "contrato_pj.pdf")
        # PF: outra ficha (o cônjuge repete "Nome Completo:" e "CPF:") e CCB com Representante Legal vazio
        pf = pymupdf.open()
        ficha = pf.new_page()
        ficha.insert_text((190, 85), "FICHA CADASTRAL PESSOA FÍSICA")
        for x, y, t in [(31, 186, "Nome Completo:"), (31, 200, "FULANO DE TAL"), (31, 214, "CPF:"), (31, 228, "111.111.111-11"),
                        (31, 427, "Dados do Cônjuge"), (31, 441, "Nome Completo:"), (371, 441, "CPF:"), (31, 455, "CICLANA")]:
            ficha.insert_text((x, y), t, fontsize=9)
        pf.new_page().insert_text((30, 50), ccb("  "), fontsize=9)
        pf.save(entrada / "contrato_pf.pdf")

        contrato = {
            "ccb_numero": "00000069713", "emitente_cidade": "UBERLANDIA", "fiel_depositario_cidade": "PORTO ALEGRE",
            "avalista_cidade": None, "forma_pagamento": "Boleto Bancário",
            "valor_total_devido": "162.309,02", "valor_total_devido_pct": "100,00", "registro_garantia": None,
        }
        rep = lambda nome, cpf: {"emitente_representante_legal_nome": nome, "emitente_representante_legal_cpf": cpf}
        pj = {"cnpj": "50.388.828/0001-37", "atividade": None, "endereco_comercial": "R DIAMANTE"}
        pf_esp = {"nome_completo": "FULANO DE TAL", "cpf": "111.111.111-11", "conjuge_nome": "CICLANA", "conjuge_cpf": None}
        grupos = {"pessoa_juridica": {k: k for k in pj}, "pessoa_fisica": {k: k for k in pf_esp},
                  "contrato": {k: k for k in {**contrato, **rep(0, 0)}}}
        with mock.patch.object(extrator.requests, "post") as post:
            extrator.processar(entrada, saida, grupos, "http://x", "m")

        for nome, tipo, esperado in [
            ("contrato_pj", "pessoa_juridica", {**pj, **contrato, **rep("Polyana Pessoa", "089.657.634-52")}),
            ("contrato_pf", "pessoa_fisica", {**pf_esp, **contrato, **rep(None, None)}),
        ]:
            res = json.loads((saida / f"{nome}.json").read_text(encoding="utf-8"))
            self.assertEqual((res["tipo"], res["erro"], res["campos_via_llm"]), (tipo, None, []))
            self.assertEqual(res["campos"], esperado)  # só os campos do próprio tipo + contrato
        self.assertEqual(post.call_count, 0)  # tudo achado: LLM nem é chamado


if __name__ == "__main__":
    unittest.main()
