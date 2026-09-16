"""Central TCC em thecreatorsclub.com.br/central/: entrada própria só do time,
fora do Dash, com números ao vivo."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from studio.models import EventWaitlistEntry, InfoProduct, InfoProductSale, Purchase
from studio.services import get_or_create_workspace_for_user

SENHA = "SenhaForte123!"


@override_settings(CENTRAL_ACESSO_DIRETO=True)
class CentralTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.layfe = U.objects.create_user("layfeamorim", email="layfe@example.com", password=SENHA)
        self.ws = get_or_create_workspace_for_user(self.layfe)
        self.maria = U.objects.create_user("maria", email="maria@example.com", password=SENHA)
        get_or_create_workspace_for_user(self.maria)

    def entrar(self, client, username):
        return client.post("/central/entrar/", {"username": username, "password": SENHA})

    def test_sem_login_vai_para_a_entrada(self):
        r = self.client.get("/central/")
        self.assertRedirects(r, "/central/entrar/", fetch_redirect_response=False)
        pagina = self.client.get("/central/entrar/")
        self.assertContains(pagina, "Entrar na Central")
        self.assertContains(pagina, 'name="csrfmiddlewaretoken"')

    def test_time_entra_e_ve_todas_as_secoes(self):
        r = self.entrar(self.client, "layfe@example.com")
        self.assertRedirects(r, "/central/", fetch_redirect_response=False)
        painel = self.client.get("/central/")
        self.assertEqual(painel.status_code, 200)
        for titulo in ("Visão geral", "Produtos e preços", "Vendas e inscrições", "Sites e links",
                       "Como fazer", "Sistema", "Tecnologia", "Pendências", "Números"):
            self.assertContains(painel, titulo)
        self.assertContains(painel, "/central/sair/")
        self.assertNotContains(painel, "nav-link-icon")  # nada do layout do Dash

    def test_creator_comum_nao_entra(self):
        r = self.entrar(self.client, "maria")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Esta área é só do time")
        self.assertRedirects(self.client.get("/central/"), "/central/entrar/", fetch_redirect_response=False)

    def test_senha_errada(self):
        r = self.client.post("/central/entrar/", {"username": "layfeamorim", "password": "errada"})
        self.assertContains(r, "incorretos")

    def test_destino_externo_e_ignorado(self):
        r = self.client.post("/central/entrar/", {"username": "layfeamorim", "password": SENHA, "next": "https://site-estranho.com/"})
        self.assertRedirects(r, "/central/", fetch_redirect_response=False)

    def test_central_nao_esta_mais_no_menu_do_dash(self):
        self.client.force_login(self.layfe)
        self.assertNotContains(self.client.get(reverse("profile")), "/central/")

    def test_entrar_na_central_nao_derruba_o_dash(self):
        david = get_user_model().objects.create_user("davidfranca9", password=SENHA)
        get_or_create_workspace_for_user(david)
        dash = Client()
        dash.post(reverse("login"), {"username": "davidfranca9", "password": SENHA})
        self.assertEqual(dash.get(reverse("profile")).status_code, 200)
        central = Client()
        self.entrar(central, "davidfranca9")
        self.assertEqual(central.get("/central/").status_code, 200)
        self.assertEqual(dash.get(reverse("profile")).status_code, 200)  # Dash continua logado

    def test_numeros_ao_vivo(self):
        base = {"product_name": "x", "customer_name": "Cliente", "customer_email": "c@example.com"}
        Purchase.objects.create(**base, product_key="dashcreator", amount=Decimal("134.90"),
                                status=Purchase.STATUS_APPROVED, mp_payment_id="1", payment_method="pix")
        Purchase.objects.create(**base, product_key="creatorday", amount=Decimal("120.00"))
        EventWaitlistEntry.objects.create(event_key="creatorday", name="Ana", email="a@example.com",
                                          whatsapp="(71) 99999-0000", page="editorial")
        mentoria = InfoProduct.objects.create(workspace=self.ws, name="Mentoria HPC", price=Decimal("397.00"))
        InfoProductSale.objects.create(workspace=self.ws, product=mentoria, buyer_name="Aluna",
                                       amount=Decimal("397.00"), sale_date="2026-09-01")
        self.entrar(self.client, "layfeamorim")
        r = self.client.get("/central/")
        ctx = r.context
        self.assertEqual(ctx["checkout"]["dashcreator"]["pagas"], 1)
        self.assertEqual(ctx["receita_checkout"], "R$ 134,90")
        self.assertEqual(ctx["cd_em_aberto"], 1)
        self.assertEqual(ctx["lista_espera"], 1)
        produto = next(p for p in ctx["produtos"] if p["nome"] == "Mentoria HPC")
        self.assertEqual(produto["preco"], "R$ 397,00")
        self.assertContains(r, "começaram a comprar o ingresso do Creator Day e ainda não pagaram")

    def test_sem_travessao(self):
        self.entrar(self.client, "layfeamorim")
        for url in ("/central/",):
            self.assertNotIn("—", self.client.get(url).content.decode())
        self.client.get("/central/sair/")
        self.assertNotIn("—", self.client.get("/central/entrar/").content.decode())

    def test_sair(self):
        self.entrar(self.client, "layfeamorim")
        self.assertRedirects(self.client.get("/central/sair/"), "/central/entrar/", fetch_redirect_response=False)
        self.assertRedirects(self.client.get("/central/"), "/central/entrar/", fetch_redirect_response=False)


class CentralForaDoDominioTests(TestCase):
    def test_abrir_direto_no_app_leva_ao_endereco_do_clube(self):
        r = self.client.get("/central/")
        self.assertRedirects(r, "https://thecreatorsclub.com.br/central/", fetch_redirect_response=False)
        r = self.client.get("/central/entrar/")
        self.assertRedirects(r, "https://thecreatorsclub.com.br/central/entrar/", fetch_redirect_response=False)

    def test_pelo_site_nao_redireciona(self):
        r = self.client.get("/central/entrar/", HTTP_X_CENTRAL_PROXY="1")
        self.assertEqual(r.status_code, 200)
