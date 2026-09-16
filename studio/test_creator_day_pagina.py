"""Página interna Creator Day: abas Lista de espera e Ingressos, só para o time."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from studio.models import EventWaitlistEntry, Purchase
from studio.services import get_or_create_workspace_for_user


class PaginaCreatorDayTests(TestCase):
    def setUp(self):
        self.layfe = get_user_model().objects.create_user("layfeamorim", password="x")
        get_or_create_workspace_for_user(self.layfe)

    def entrar(self, user):
        self.client.force_login(user)

    def test_conta_do_time_ve_a_pagina_e_o_item_no_menu(self):
        self.entrar(self.layfe)
        r = self.client.get(reverse("creator_day"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Lista de espera (0)")
        self.assertContains(r, "Ingressos (0)")
        self.assertContains(r, "Ninguém entrou na lista de espera ainda.")
        self.assertContains(self.client.get(reverse("profile")), reverse("creator_day"))

    def test_creator_de_fora_nao_ve(self):
        maria = get_user_model().objects.create_user("maria", password="x")
        get_or_create_workspace_for_user(maria)
        self.entrar(maria)
        self.assertEqual(self.client.get(reverse("creator_day")).status_code, 404)
        self.assertNotContains(self.client.get(reverse("profile")), reverse("creator_day"))

    def test_aba_lista_de_espera(self):
        EventWaitlistEntry.objects.create(event_key="creatorday", name="Marina Souza", email="marina@example.com",
                                          whatsapp="(71) 99999-8888", page="editorial")
        EventWaitlistEntry.objects.create(event_key="outro-evento", name="Outra Pessoa", email="o@example.com",
                                          whatsapp="(71) 98888-7777", page="site")
        self.entrar(self.layfe)
        r = self.client.get(reverse("creator_day"), {"tab": "lista"})
        self.assertContains(r, "Lista de espera (1)")
        self.assertContains(r, "Marina Souza")
        self.assertContains(r, "https://wa.me/5571999998888")
        self.assertContains(r, "Editorial")
        self.assertNotContains(r, "Outra Pessoa")

    def test_aba_ingressos_mostra_situacao_e_total_recebido(self):
        base = {"product_key": "creatorday", "product_name": "Creator Day Experience", "amount": Decimal("120.00")}
        Purchase.objects.create(**base, customer_name="Paga", customer_email="p@example.com",
                                status=Purchase.STATUS_APPROVED, payment_method="pix", mp_payment_id="1")
        Purchase.objects.create(**base, customer_name="Desistiu", customer_email="d@example.com")
        Purchase.objects.create(**base, customer_name="Pix Gerado", customer_email="x@example.com",
                                payment_method="pix", mp_payment_id="2")
        Purchase.objects.create(product_key="dashcreator", product_name="Dash Creator", amount=Decimal("134.90"),
                                customer_name="Cliente Dash", customer_email="c@example.com")
        self.entrar(self.layfe)
        r = self.client.get(reverse("creator_day"), {"tab": "ingressos"})
        self.assertContains(r, "Ingressos (3)")
        self.assertContains(r, "cd-tag--ok\">Pago")
        self.assertContains(r, "Não finalizou")
        self.assertContains(r, "Aguardando pagamento")
        self.assertContains(r, "R$ 120,00")
        self.assertNotContains(r, "Cliente Dash")
        kpis = r.context["kpis"]
        self.assertEqual((kpis["pagos"], kpis["em_aberto"], kpis["recebido"]), (1, 2, "R$ 120,00"))
