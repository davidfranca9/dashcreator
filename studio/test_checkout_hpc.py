"""Checkout da Mentoria HPC (High Performance Creator): vaga confirmada por e-mail, sem código do Dash."""
import json
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .checkout import get_product
from .checkout_views import _approve_purchase
from .models import AccessCode, Purchase


def _compra(**extra):
    dados = {
        "product_key": "hpc",
        "product_name": "High Performance Creator",
        "amount": Decimal("597.00"),
        "customer_name": "Joana",
        "customer_email": "joana@example.com",
        "customer_cpf": "12345678909",
        "customer_phone": "(11) 98888-0000",
    }
    dados.update(extra)
    return Purchase.objects.create(**dados)


@override_settings(MERCADO_PAGO_PUBLIC_KEY="TEST-public-key", MERCADO_PAGO_ACCESS_TOKEN="TEST-access-token")
class CheckoutHpcTest(TestCase):
    def test_produto_de_597_sem_codigo_do_dash(self):
        produto = get_product("hpc")
        self.assertEqual(produto.price, Decimal("597.00"))
        self.assertEqual(produto.name, "High Performance Creator")
        self.assertTrue(produto.is_ticket)
        self.assertEqual((produto.success_path, produto.failure_path), ("/checkout/hpc/sucesso/", "/checkout/hpc/erro/"))
        self.assertEqual(produto.email_template, "mentoria")

    def test_preferencia_cobra_597_e_volta_para_as_paginas_da_hpc(self):
        enviado = {}

        class FakePreferenceApi:
            def create(self, payload):
                enviado.update(payload)
                return {"status": 201, "response": {"id": "pref_hpc"}}

        class FakeSdk:
            def preference(self):
                return FakePreferenceApi()

        with patch("studio.checkout_views._mp_sdk", return_value=FakeSdk()):
            response = self.client.post(
                reverse("checkout_preference"),
                data=json.dumps({
                    "product_key": "hpc",
                    "customer_name": "Joana",
                    "customer_email": "joana@example.com",
                    "customer_cpf": "123.456.789-09",
                    "customer_phone": "(11) 98888-0000",
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["amount"], 597.0)
        compra = Purchase.objects.get(customer_email="joana@example.com")
        self.assertEqual((compra.product_key, compra.product_name), ("hpc", "High Performance Creator"))
        self.assertEqual(enviado["items"][0]["unit_price"], 597.0)
        self.assertEqual(enviado["back_urls"]["success"], f"https://thecreatorsclub.com.br/checkout/hpc/sucesso/?p={compra.pk}")
        self.assertEqual(enviado["back_urls"]["failure"], f"https://thecreatorsclub.com.br/checkout/hpc/erro/?p={compra.pk}")

    def test_aprovar_manda_email_da_vaga_e_nao_gera_codigo(self):
        compra = _compra()
        _approve_purchase(compra, {"id": "pay_hpc", "payment_method_id": "master", "date_approved": "2026-09-22T12:00:00.000-03:00"})
        compra.refresh_from_db()
        self.assertEqual(compra.status, Purchase.STATUS_APPROVED)
        self.assertIsNone(compra.access_code)
        self.assertIsNotNone(compra.notified_at)
        self.assertEqual(AccessCode.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["joana@example.com"])
        self.assertEqual(email.subject, "Sua vaga na High Performance Creator está confirmada")
        self.assertIn("Encontros: 04 encontros ao vivo, às segundas, 19h", email.body)
        self.assertIn("Acesso: 45 dias", email.body)
        self.assertIn(f"Número do pedido: {compra.pk}", email.body)
        self.assertIn("WhatsApp", email.body)
        self.assertNotIn("ingresso", email.body.lower() + email.subject.lower())
        self.assertNotIn("—", email.body + email.subject)

    def test_creator_day_continua_com_o_email_do_ingresso(self):
        compra = _compra(product_key="creatorday", product_name="Creator Day Experience", amount=Decimal("120.00"))
        _approve_purchase(compra, {"id": "pay_cd", "payment_method_id": "pix"})
        self.assertEqual(mail.outbox[0].subject, "Seu ingresso do Creator Day Experience está confirmado")

    def test_aprovacao_repetida_manda_um_email_so(self):
        compra = _compra()
        _approve_purchase(compra, {"id": "pay_hpc", "payment_method_id": "pix"})
        _approve_purchase(compra, {"id": "pay_hpc", "payment_method_id": "pix"})
        self.assertEqual(len(mail.outbox), 1)

    def test_status_fica_pronto_quando_aprovado(self):
        compra = _compra(status=Purchase.STATUS_APPROVED)
        response = self.client.get(reverse("checkout_status"), {"purchase_id": compra.pk})
        self.assertEqual(response.json()["status"], "approved")
