"""Central TCC: plataforma interna com tudo do clube e números ao vivo."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from studio.models import EventWaitlistEntry, InfoProduct, InfoProductSale, Purchase
from studio.services import get_or_create_workspace_for_user


class CentralTests(TestCase):
    def setUp(self):
        self.layfe = get_user_model().objects.create_user("layfeamorim", password="x")
        self.ws = get_or_create_workspace_for_user(self.layfe)

    def abrir(self, user):
        self.client.force_login(user)
        return self.client.get(reverse("central"))

    def test_time_abre_a_central_com_todas_as_secoes(self):
        r = self.abrir(self.layfe)
        self.assertEqual(r.status_code, 200)
        for titulo in ("Visão geral", "Produtos e preços", "Vendas e inscrições", "Sites e links",
                       "Como fazer", "Sistema", "Tecnologia", "Pendências", "Números"):
            self.assertContains(r, titulo)
        self.assertContains(r, 'href="/central/"')  # item no menu
        self.assertContains(r, "Números ao vivo")

    def test_creator_de_fora_nao_ve(self):
        maria = get_user_model().objects.create_user("maria", password="x")
        get_or_create_workspace_for_user(maria)
        self.assertEqual(self.abrir(maria).status_code, 404)
        self.assertNotContains(self.client.get(reverse("profile")), 'href="/central/"')

    def test_numeros_ao_vivo_do_checkout_e_do_creator_day(self):
        base = {"product_name": "x", "customer_name": "Cliente", "customer_email": "c@example.com"}
        Purchase.objects.create(**base, product_key="dashcreator", amount=Decimal("134.90"),
                                status=Purchase.STATUS_APPROVED, mp_payment_id="1", payment_method="pix")
        Purchase.objects.create(**base, product_key="creatorday", amount=Decimal("120.00"))
        EventWaitlistEntry.objects.create(event_key="creatorday", name="Ana", email="a@example.com",
                                          whatsapp="(71) 99999-0000", page="editorial")
        r = self.abrir(self.layfe)
        ctx = r.context
        self.assertEqual(ctx["checkout"]["dashcreator"]["pagas"], 1)
        self.assertEqual(ctx["receita_checkout"], "R$ 134,90")
        self.assertEqual(ctx["checkout"]["creatorday"]["nao_finalizou"], 1)
        self.assertEqual(ctx["lista_espera"], 1)
        self.assertContains(r, "começaram a comprar o ingresso do Creator Day e ainda não pagaram")

    def test_precos_e_vendas_de_infoprodutos_da_layfe(self):
        mentoria = InfoProduct.objects.create(workspace=self.ws, name="Mentoria HPC", price=Decimal("397.00"))
        InfoProductSale.objects.create(workspace=self.ws, product=mentoria, buyer_name="Aluna",
                                       amount=Decimal("397.00"), sale_date="2026-09-01")
        r = self.abrir(self.layfe)
        produto = next(p for p in r.context["produtos"] if p["nome"] == "Mentoria HPC")
        self.assertEqual(produto["preco"], "R$ 397,00")
        self.assertIn("1 venda(s)", produto["vendas"])
        dash = next(p for p in r.context["produtos"] if p["nome"] == "Dash Creator")
        self.assertEqual(dash["preco"], "R$ 134,90")

    def test_pagina_sem_travessao_e_sem_segredo(self):
        html = self.abrir(self.layfe).content.decode()
        inicio = html.index("data-central")
        pagina = html[inicio:]
        self.assertNotIn("—", pagina)
        for proibido in ("senha:", "password=", "token=", "APP_USR-"):
            self.assertNotIn(proibido, pagina.lower() if proibido.islower() else pagina)
