"""Extrai campos configuráveis de PDFs via OCR (deepseek-ocr no Ollama) e grava um JSON por PDF."""
import base64
import json
import os
import re
import sys
from pathlib import Path

import pymupdf
import requests
from dotenv import load_dotenv

OCR_PROMPT = "<|grounding|>Convert the document to markdown."
TIMEOUT = 600  # OCR de página em CPU pode demorar


def ollama(host, model, prompt, images=None, fmt=None):
    # shortcut: num_ctx 8192 cabe ~2 páginas + 76 campos e o qwen2.5:14b na GPU de 12 GB (16384 estoura a VRAM); aumente se ler mais páginas
    payload = {"model": model, "prompt": prompt, "stream": False, "options": {"num_ctx": 8192, "temperature": 0}}
    if images:
        payload["images"] = images
    if fmt:
        payload["format"] = fmt
    r = requests.post(f"{host.rstrip('/')}/api/generate", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["response"]


def ocr_pdf(pdf, host, model, paginas=None):
    """paginas: números 1-based a processar; None = todas. Páginas inexistentes são ignoradas."""
    textos = []
    with pymupdf.open(pdf) as doc:
        for i in paginas or range(1, len(doc) + 1):
            if not 1 <= i <= len(doc):
                continue
            png = doc[i - 1].get_pixmap(dpi=200).tobytes("png")
            print(f"  página {i}/{len(doc)}")
            textos.append(ollama(host, model, OCR_PROMPT, images=[base64.b64encode(png).decode()]))
    return textos


def extrair_campos(texto, campos, host, model):
    schema = {
        "type": "object",
        "properties": {k: {"type": ["string", "null"]} for k in campos},
        "required": list(campos),
    }
    texto = re.sub(r"\w+\[\[[\d, ]+\]\]\s*", "", texto)  # remove as coordenadas do <|grounding|>, que confundem o modelo
    descricao = "\n".join(f"- {k}: {v}" for k, v in campos.items())
    prompt = (
        "Extraia do documento abaixo os seguintes campos e responda somente em JSON. "
        "Cada valor deve ser apenas o texto copiado exatamente como aparece no documento, sem comentários ou explicações. "
        "Não deduza nem copie valores de outros campos: se o campo não existir ou estiver vazio no documento, use null.\n"
        f"Campos:\n{descricao}\n\nDocumento:\n{texto}"
    )
    resultado = json.loads(ollama(host, model, prompt, fmt=schema))
    return {k: resultado.get(k) for k in campos}


def processar(entrada, saida, campos, host, ocr_model, extract_model, paginas=None):
    saida.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(p for p in entrada.iterdir() if p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"Nenhum PDF encontrado em {entrada}")
    for pdf in pdfs:
        print(f"Processando {pdf.name}")
        resultado = {"arquivo": pdf.name, "paginas": 0, "campos": None, "texto_ocr": None, "erro": None}
        try:
            textos = ocr_pdf(pdf, host, ocr_model, paginas)
            resultado["paginas"] = len(textos)
            resultado["texto_ocr"] = "\n\n".join(textos)
            resultado["campos"] = extrair_campos(resultado["texto_ocr"], campos, host, extract_model)
        except Exception as e:  # um PDF com problema não derruba o lote
            resultado["erro"] = f"{type(e).__name__}: {e}"
            print(f"  ERRO: {resultado['erro']}")
        destino = saida / f"{pdf.stem}.json"
        destino.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(pdfs)


def main():
    load_dotenv()
    host = os.getenv("OLLAMA_HOST") or "http://localhost:11434"
    ocr_model = os.getenv("OCR_MODEL", "deepseek-ocr")
    extract_model = os.getenv("EXTRACT_MODEL") or ocr_model
    entrada = Path(sys.argv[1] if len(sys.argv) > 1 else os.getenv("PASTA_ENTRADA", "entrada"))
    saida = Path(sys.argv[2] if len(sys.argv) > 2 else os.getenv("PASTA_SAIDA", "saida"))
    campos_arq = Path(os.getenv("ARQUIVO_CAMPOS", Path(__file__).with_name("campos.json")))
    if not entrada.is_dir():
        sys.exit(f"Pasta de entrada não encontrada: {entrada}")
    campos = json.loads(campos_arq.read_text(encoding="utf-8"))
    paginas = [int(p) for p in os.getenv("PAGINAS", "").replace(" ", "").split(",") if p] or None
    n = processar(entrada, saida, campos, host, ocr_model, extract_model, paginas)
    print(f"Concluído: {n} PDF(s) -> {saida}")


if __name__ == "__main__":
    main()
