"""Extrai campos configuráveis de PDFs e grava um JSON por PDF.

PDF -> markdown com o MarkItDown -> campos extraídos por um modelo gemma3 no Ollama.
"""
import io
import json
import os
import re
import sys
from pathlib import Path

import pymupdf
import requests
from dotenv import load_dotenv
from markitdown import MarkItDown

TIMEOUT = 1800  # extração de ~76 campos em CPU leva 5-7 min com o gemma3:4b
MIN_CARACTERES_POR_PAGINA = 50  # abaixo disso o PDF não tem camada de texto (digitalizado)


def ollama(host, model, prompt, fmt=None):
    # shortcut: num_ctx 8192 cabe ~2 páginas + 76 campos; aumente se ler mais páginas
    payload = {"model": model, "prompt": prompt, "stream": False, "options": {"num_ctx": 8192, "temperature": 0}}
    if fmt:
        payload["format"] = fmt
    r = requests.post(f"{host.rstrip('/')}/api/generate", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def markdown_pdf(pdf, paginas=None):
    """Converte as páginas pedidas (1-based; None = todas) em markdown com o MarkItDown. Retorna (markdown, nº de páginas)."""
    with pymupdf.open(pdf) as src, pymupdf.open() as sub:
        for i in paginas or range(1, len(src) + 1):
            if 1 <= i <= len(src):
                sub.insert_pdf(src, from_page=i - 1, to_page=i - 1)
        n, dados = len(sub), sub.tobytes()
    return MarkItDown().convert_stream(io.BytesIO(dados), file_extension=".pdf").text_content, n


def extrair_campos(texto, campos, host, model):
    schema = {
        "type": "object",
        "properties": {k: {"type": ["string", "null"]} for k in campos},
        "required": list(campos),
    }
    descricao = "\n".join(f"- {k}: {v}" for k, v in campos.items())
    prompt = (
        "Extraia do documento abaixo os seguintes campos e responda somente em JSON. "
        "Cada valor deve ser apenas o texto copiado exatamente como aparece no documento, sem comentários ou explicações. "
        "Não deduza nem copie valores de outros campos: se o campo não existir ou estiver vazio no documento, use null.\n"
        f"Campos:\n{descricao}\n\nDocumento:\n{texto}"
    )
    r = ollama(host, model, prompt, fmt=schema)
    resultado = json.loads(r["response"])
    return {k: resultado.get(k) for k in campos}, r.get("prompt_eval_count")


def processar(entrada, saida, campos, host, model, paginas=None):
    saida.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(p for p in entrada.iterdir() if p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"Nenhum PDF encontrado em {entrada}")
    for pdf in pdfs:
        print(f"Processando {pdf.name}")
        resultado = {"arquivo": pdf.name, "paginas": 0, "campos": None, "tokens_extracao": None, "markdown": None, "erro": None}
        try:
            texto, n = markdown_pdf(pdf, paginas)
            resultado["paginas"], resultado["markdown"] = n, texto
            if len(re.sub(r"\s", "", texto)) < MIN_CARACTERES_POR_PAGINA * max(n, 1):
                raise ValueError("PDF sem texto digital (provavelmente digitalizado); o MarkItDown não faz OCR")
            resultado["campos"], resultado["tokens_extracao"] = extrair_campos(texto, campos, host, model)
        except Exception as e:  # um PDF com problema não derruba o lote
            resultado["erro"] = f"{type(e).__name__}: {e}"
            print(f"  ERRO: {resultado['erro']}")
        destino = saida / f"{pdf.stem}.json"
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(pdfs)


def main():
    load_dotenv()
    host = os.getenv("OLLAMA_HOST") or "http://localhost:11434"
    model = os.getenv("EXTRACT_MODEL") or "gemma3:4b"
    entrada = Path(sys.argv[1] if len(sys.argv) > 1 else os.getenv("PASTA_ENTRADA", "entrada"))
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else os.getenv("PASTA_SAIDA", "saida"))
    campos_arq = Path(os.getenv("ARQUIVO_CAMPOS", Path(__file__).with_name("campos.json")))
    if not entrada.is_dir():
        sys.exit(f"Pasta de entrada não encontrada: {entrada}")
    campos = json.loads(campos_arq.read_text(encoding="utf-8"))
    paginas = [int(p) for p in os.getenv("PAGINAS", "").replace(" ", "").split(",") if p] or None
    n = processar(entrada, saida, campos, host, model, paginas)
    print(f"Concluído: {n} PDF(s) -> {saida}")


if __name__ == "__main__":
    main()
