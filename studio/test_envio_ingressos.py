from decimal import Decimal
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from .models import Purchase


def _compra(nome, email, status=Purchase.STATUS_APPROVED, notificada=False, chave="creatorday"):
    from django.utils import timezone
    return Purchase.objects.create(
        product_key=chave, product_name="Creator Day Experience", amount=Decimal("120"),
        customer_name=nome, customer_email=email, status=status,
        notified_at=timezone.now() if notificada else None,
    )


class EnviarIngressosTests(TestCase):
    def test_manda_so_para_pagantes_que_ainda_nao_receberam(self):
        paga = _compra("Ana", "ana@example.com")
        _compra("Bia", "bia@example.com", status=Purchase.STATUS_PENDING)
        _compra("Cris", "cris@example.com", notificada=True)
        _compra("Dani", "dani@example.com", chave="dashcreator")

        call_command("enviar_ingressos_creator_day", stdout=StringIO())

        self.assertEqual([m.to for m in mail.outbox], [["ana@example.com"]])
        paga.refresh_from_db()
        self.assertIsNotNone(paga.notified_at)

    def test_listar_nao_envia(self):
        _compra("Ana", "ana@example.com")
        saida = StringIO()
        call_command("enviar_ingressos_creator_day", "--listar", stdout=saida)
        self.assertEqual(mail.outbox, [])
        self.assertIn("ana@example.com", saida.getvalue())

    def test_rodar_de_novo_nao_duplica(self):
        _compra("Ana", "ana@example.com")
        call_command("enviar_ingressos_creator_day", stdout=StringIO())
        call_command("enviar_ingressos_creator_day", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_reenviar_manda_de_novo(self):
        _compra("Ana", "ana@example.com", notificada=True)
        call_command("enviar_ingressos_creator_day", "--reenviar", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
