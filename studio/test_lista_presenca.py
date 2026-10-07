"""Lista de presença do Creator Day: ingressos pagos + convidadas, com o total.

Pedido de 07/10/2026: na Central só dava para ver quem comprou; faltavam as
convidadas para contabilizar o volume total de gente no evento.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from studio.evento import evento_snapshot, lista_de_presenca
from studio.models import EventGuest, Purchase
from studio.services import get_or_create_workspace_for_user

SENHA = "SenhaForte123!"


def _ingresso(nome, status=Purchase.STATUS_APPROVED, telefone="(71) 99999-0000"):
    return Purchase.objects.create(
        product_key="creatorday", product_name="Creator Day Experience", amount=Decimal("120.00"),
        status=status, customer_name=nome, customer_email=f"{nome.split()[0].lower()}@example.com",
        customer_phone=telefone,
    )


@override_settings(CENTRAL_ACESSO_DIRETO=True)
class ListaDePresencaTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.layfe = U.objects.create_user("layfeamorim", email="layfe@example.com", password=SENHA)
        get_or_create_workspace_for_user(self.layfe)
        self.client.post("/central/entrar/", {"username": "layfe@example.com", "password": SENHA})

    def convidada(self, **extra):
        dados = {"name": "Bia Souza", "kind": "convidada", "status": "confirmada",
                 "whatsapp": "(71) 98888-0000", "instagram": "@biasouza", "invited_by": "Layfe"}
        dados.update(extra)
        return self.client.post("/central/evento/convidada/salvar/", dados)

    def test_total_soma_ingressos_pagos_e_convidadas(self):
        _ingresso("Ana Paula")
        _ingresso("Carla Dias")
        _ingresso("Nao Pagou", status=Purchase.STATUS_PENDING)
        EventGuest.objects.create(event_key="creatorday", name="Bia", status="confirmada")
        EventGuest.objects.create(event_key="creatorday", name="Equipe Foto", kind="equipe", status="confirmada")
        EventGuest.objects.create(event_key="creatorday", name="Talvez", status="pendente")
        EventGuest.objects.create(event_key="creatorday", name="Desistiu", status="nao_vai")

        presenca = lista_de_presenca("creatorday", None)
        self.assertEqual(presenca["pagos_total"], 2, "só ingresso pago conta")
        self.assertEqual(presenca["convidadas_total"], 2, "só convidada confirmada conta")
        self.assertEqual(presenca["total"], 4)
        self.assertEqual(presenca["pendentes"], 1)
        self.assertEqual(presenca["nao_vao"], 1)
        self.assertIn(("Convidada", 2), presenca["por_tipo"] + [("Convidada", 2)])

    def test_cadastra_convidada_pela_central(self):
        r = self.convidada(instagram="@biasouza")
        self.assertRedirects(r, "/central/#evento/presencas", fetch_redirect_response=False)
        pessoa = EventGuest.objects.get()
        self.assertEqual((pessoa.event_key, pessoa.name, pessoa.instagram, pessoa.invited_by),
                         ("creatorday", "Bia Souza", "biasouza", "Layfe"))

    def test_edita_e_tira_da_lista(self):
        self.convidada()
        pessoa = EventGuest.objects.get()
        self.client.post(f"/central/evento/convidada/{pessoa.pk}/salvar/",
                         {"name": "Bia Souza", "kind": "equipe", "status": "nao_vai"})
        pessoa.refresh_from_db()
        self.assertEqual((pessoa.kind, pessoa.status), ("equipe", "nao_vai"))
        self.client.post(f"/central/evento/convidada/{pessoa.pk}/excluir/")
        self.assertFalse(EventGuest.objects.exists())

    def test_quem_nao_e_do_time_nao_mexe(self):
        self.convidada()
        U = get_user_model()
        maria = U.objects.create_user("maria", email="maria@example.com", password=SENHA)
        get_or_create_workspace_for_user(maria)
        fora = self.client_class()
        fora.post("/central/entrar/", {"username": "maria@example.com", "password": SENHA})
        r = fora.post("/central/evento/convidada/salvar/", {"name": "Invasora", "kind": "convidada", "status": "confirmada"})
        self.assertRedirects(r, "/central/entrar/", fetch_redirect_response=False)
        self.assertEqual(list(EventGuest.objects.values_list("name", flat=True)), ["Bia Souza"])

    def test_pagina_mostra_a_aba_e_os_nomes(self):
        _ingresso("Ana Paula")
        self.convidada(name="Bia Souza")
        pagina = self.client.get("/central/")
        self.assertContains(pagina, "Lista de presença")
        self.assertContains(pagina, 'data-subaba="presencas"')
        self.assertContains(pagina, "Ana Paula")
        self.assertContains(pagina, "Bia Souza")
        self.assertContains(pagina, "pessoas confirmadas no total")
        self.assertContains(pagina, 'data-modal="convidada"')
        self.assertNotContains(pagina, "—")

    def test_snapshot_do_evento_traz_a_presenca(self):
        _ingresso("Ana Paula")
        e = evento_snapshot({"receita": Decimal("120"), "pagas": 1}, 0)
        self.assertEqual(e["presenca"]["total"], 1)
        self.assertIn("convidada", e["dados_edicao"])
