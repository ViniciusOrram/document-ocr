"""Mede a precisão da extração (MarkItDown + modelo do Ollama) contra benchmark/gabarito.json.

Uso: python benchmark/comparar.py <pasta_com_os_pdfs>   (usa OLLAMA_HOST, EXTRACT_MODEL e PAGINAS do .env)
"""
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI.parent))
import extrator  # noqa: E402


def norm(v):
    if v is None or str(v).strip() == "":
        return None
    v = str(v).casefold().replace("r$", "").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", v).strip(".")


def main():
    load_dotenv(AQUI.parent / ".env")
    pasta = Path(sys.argv[1])
    host = os.getenv("OLLAMA_HOST") or "http://localhost:11434"
    model = os.getenv("EXTRACT_MODEL") or "gemma3:4b"
    paginas = [int(p) for p in os.getenv("PAGINAS", "").replace(" ", "").split(",") if p] or None
    campos = json.loads((AQUI.parent / "campos.json").read_text(encoding="utf-8"))
    gabarito = json.loads((AQUI / "gabarito.json").read_text(encoding="utf-8"))
    print(f"Extração com {model}, páginas {paginas or 'todas'}\n")

    total_ok = total = 0
    erros = {}
    for nome, esperado in gabarito.items():
        texto, _ = extrator.markdown_pdf(pasta / nome, paginas)
        t = time.time()
        obtido, tokens = extrator.extrair_campos(texto, campos, host, model)
        erros[nome] = {k: {"esperado": e, "obtido": obtido.get(k)} for k, e in esperado.items() if norm(obtido.get(k)) != norm(e)}
        ok = len(esperado) - len(erros[nome])
        total_ok, total = total_ok + ok, total + len(esperado)
        print(f"{nome:<10} {time.time() - t:>7.1f}s  tokens={tokens}  acertos={ok}/{len(esperado)}")
    print(f"TOTAL acertos={total_ok}/{total} ({total_ok / total:.0%})\n\nErros por campo:")
    for nome, e in erros.items():
        for campo, v in e.items():
            print(f"  {nome:<10} {campo:<34} esperado={v['esperado']!r}  obtido={v['obtido']!r}")
    (AQUI / "resultado.json").write_text(json.dumps(erros, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
