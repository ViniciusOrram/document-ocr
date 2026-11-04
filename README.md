# document-ocr

Lê todos os PDFs de uma pasta, faz OCR de cada página com o `deepseek-ocr` rodando no Ollama (local por padrão) e gera um JSON por PDF com os campos definidos em `campos.json`.

## Uso

```bash
pip install -r requirements.txt
# crie um .env (opcional) — padrão: Ollama local (localhost:11434); para outra máquina, troque OLLAMA_HOST
python extrator.py          # ou: python extrator.py <pasta_entrada> <pasta_saida>
```

Saída (`saida/<nome>.json`):

```json
{"arquivo": "nota.pdf", "paginas": 1, "campos": {"cnpj_emitente": "..."}, "texto_ocr": "...", "erro": null}
```

## Campos

Edite `campos.json`: chave = nome do campo no JSON, valor = descrição para o modelo.

## Dicas

- Ollama em outra máquina: lá ele precisa escutar na rede: `OLLAMA_HOST=0.0.0.0` e porta 11434 liberada.
- Se os campos vierem ruins, defina `EXTRACT_MODEL` com um modelo de texto (ex.: `qwen2.5`) — o `deepseek-ocr` é bom em OCR, não em seguir instruções.

## Teste

```bash
python -m unittest test_extrator.py
```
