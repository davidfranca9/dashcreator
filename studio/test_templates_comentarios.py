"""Comentário {# #} do Django só vale numa linha: quebrado em duas, aparece
como texto na tela (aconteceu no login em 16/09/2026)."""
import pathlib
import re

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class ComentariosDeTemplateTests(TestCase):
    def test_login_nao_mostra_comentario_na_tela(self):
        html = self.client.get(reverse("login")).content.decode()
        self.assertIn("Comprou e ainda não criou sua conta?", html)
        self.assertNotIn("{#", html)
        self.assertNotIn("#}", html)
        self.assertNotIn("nasce do codigo", html)

    def test_nenhum_template_tem_comentario_de_uma_linha_quebrado(self):
        raiz = pathlib.Path(settings.BASE_DIR)
        quebrados = []
        for app in ("studio", "desafio", "tcc_portal"):
            for arquivo in (raiz / app / "templates").rglob("*.html"):
                for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
                    if re.search(r"\{#(?!.*#\})", linha):
                        quebrados.append(f"{arquivo.relative_to(raiz)}:{numero}")
        self.assertEqual(quebrados, [], "Use {% comment %} para comentário em mais de uma linha")
