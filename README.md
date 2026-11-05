# document-ocr

Lê todos os PDFs de uma pasta, converte as páginas em markdown com o [MarkItDown](https://github.com/microsoft/markitdown) e usa um modelo `gemma3` no Ollama (local por padrão) para extrair os campos definidos em `campos.json`. Gera um JSON por PDF.

Só funciona com PDF que tem texto digital. PDF digitalizado (imagem) é registrado com erro, porque o MarkItDown não faz OCR.

## Uso

```bash
pip install -r requirements.txt
ollama pull gemma3:4b
# crie um .env (opcional); padrão: Ollama local (localhost:11434) e gemma3:4b
python extrator.py          # ou: python extrator.py <pasta_entrada> <pasta_saida>
```

Variáveis do `.env`: `OLLAMA_HOST`, `EXTRACT_MODEL` (ex.: `gemma3:4b`, `gemma3:1b`), `PAGINAS` (ex.: `1,3`; vazio = todas), `PASTA_ENTRADA`, `PASTA_SAIDA`, `ARQUIVO_CAMPOS`.

Saída (`saida/<nome>.json`):

```json
{"arquivo": "nota.pdf", "paginas": 2, "campos": {"cnpj": "..."}, "tokens_extracao": 3700, "markdown": "...", "erro": null}
```

`tokens_extracao` é quantos tokens o modelo leu; `markdown` é o texto gerado pelo MarkItDown.

## Campos

Edite `campos.json`: chave = nome do campo no JSON, valor = descrição para o modelo.

## Dicas

- Ollama em outra máquina: lá ele precisa escutar na rede: `OLLAMA_HOST=0.0.0.0` e porta 11434 liberada.

## Teste

```bash
python -m unittest test_extrator.py
```

## Benchmark de precisão

`benchmark/comparar.py` extrai os campos dos PDFs listados em `benchmark/gabarito.json` (valores corretos digitados à mão) e mostra acertos e tokens. O gabarito e o resultado têm dados reais de clientes e ficam fora do git.

```bash
python benchmark/comparar.py <pasta_com_os_pdfs>
```
