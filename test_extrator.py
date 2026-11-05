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
            n = extrator.processar(entrada, saida, {"cnpj": "CNPJ"}, "http://x", "gemma3:4b", [1, 3, 9])  # 9 não existe

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


if __name__ == "__main__":
    unittest.main()
