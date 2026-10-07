"""Login: caixinha "Manter-me conectado" e o Dash aberto como app.

O app instalado abre direto em /dashboard/. Sem sessão, essa página dava erro 500
(relato de uma usuária em 07/10/2026); agora leva para o login, e quem marca a
caixinha fica 6 meses conectada.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .services import get_or_create_workspace_for_user

SENHA = "SenhaForte123!"


class ManterConectadoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("creator", email="creator@example.com", password=SENHA)
        get_or_create_workspace_for_user(self.user)

    def entrar(self, **extra):
        dados = {"username": "creator", "password": SENHA}
        dados.update(extra)
        return self.client.post(reverse("login"), dados)

    def test_marcando_fica_conectada_por_seis_meses(self):
        resposta = self.entrar(remember_me="1")
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE_REMEMBER)
        self.assertGreater(settings.SESSION_COOKIE_AGE_REMEMBER, 60 * 60 * 24 * 150)

    def test_sem_marcar_vale_o_prazo_normal(self):
        self.entrar()
        self.assertEqual(self.client.session.get_expiry_age(), settings.SESSION_COOKIE_AGE)

    def test_prazo_se_renova_a_cada_visita(self):
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST, "sem isso a sessão vence mesmo usando todo dia")

    def test_caixinha_aparece_marcada_na_tela(self):
        pagina = self.client.get(reverse("login"))
        self.assertContains(pagina, 'name="remember_me"')
        self.assertContains(pagina, "Manter-me conectado")
        self.assertContains(pagina, "checked")

    def test_app_instalado_abre_o_dashboard_e_cai_no_login_sem_sessao(self):
        # o manifesto do app abre /dashboard/
        manifesto = self.client.get("/static/studio/manifest.webmanifest")
        if manifesto.status_code == 200:
            self.assertIn("/dashboard/", manifesto.content.decode())
        resposta = self.client.get(reverse("dashboard"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("login"), resposta["Location"])

    def test_depois_do_login_volta_para_onde_queria_ir(self):
        resposta = self.client.post(f"{reverse('login')}?next={reverse('dashboard')}", {"username": "creator", "password": SENHA, "remember_me": "1"})
        self.assertRedirects(resposta, reverse("dashboard"), fetch_redirect_response=False)
