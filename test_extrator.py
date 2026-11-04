import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pymupdf

import extrator


def resposta(texto):
    r = mock.Mock()
    r.json.return_value = {"response": texto}
    return r


class TestExtrator(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.entrada, self.saida = self.tmp / "in", self.tmp / "out"
        self.entrada.mkdir()
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 72), "CNPJ 12.345.678/0001-90")
        doc.save(self.entrada / "a.pdf")
        (self.entrada / "quebrado.pdf").write_bytes(b"isso nao e pdf")

    def test_lote(self):
        campos = {"cnpj": "CNPJ", "valor": "Valor total"}

        def fake_post(url, json, timeout):
            if "images" in json:
                return resposta("text[[48, 244, 114, 259]]\nCNPJ 12.345.678/0001-90")
            self.assertIn("cnpj", json["format"]["properties"])
            self.assertNotIn("[[", json["prompt"])
            return resposta('{"cnpj": "12.345.678/0001-90", "valor": null}')

        with mock.patch.object(extrator.requests, "post", side_effect=fake_post):
            n = extrator.processar(self.entrada, self.saida, campos, "http://x", "ocr", "ocr")

        self.assertEqual(n, 2)
        ok = json.loads((self.saida / "a.json").read_text(encoding="utf-8"))
        self.assertEqual(ok["campos"], {"cnpj": "12.345.678/0001-90", "valor": None})
        self.assertEqual(ok["paginas"], 1)
        self.assertIsNone(ok["erro"])
        ruim = json.loads((self.saida / "quebrado.json").read_text(encoding="utf-8"))
        self.assertIsNotNone(ruim["erro"])

    def test_paginas_selecionadas(self):
        doc = pymupdf.open()
        for i in range(1, 5):
            doc.new_page().insert_text((72, 72), f"pagina {i}")
        pdf = self.tmp / "multi.pdf"
        doc.save(pdf)
        with mock.patch.object(extrator.requests, "post", return_value=resposta("x")) as post:
            textos = extrator.ocr_pdf(pdf, "http://x", "ocr", [1, 3, 9])  # 9 não existe
        self.assertEqual(len(textos), 2)
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
