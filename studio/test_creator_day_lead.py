"""Formulário das prévias do Creator Day -> lead no CRM da Layfe (coluna Interesse)."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from studio.models import InfoLead, InfoLeadEvent


class CreatorDayLeadTests(TestCase):
    def setUp(self):
        import studio.metrics as m
        m._LEAD_WORKSPACE_CACHE.clear()  # evita cache de workspace entre testes
        from studio.services import get_or_create_workspace_for_user
        self.layfe = get_user_model().objects.create_user("layfeamorim", password="x")
        self.ws = get_or_create_workspace_for_user(self.layfe)

    def _post(self, payload, **extra):
        return self.client.post(reverse("creator_day_lead"), data=json.dumps(payload),
                                content_type="text/plain;charset=utf-8", **extra)

    def _dados(self, **extra):
        dados = {"name": "Marina Souza", "email": "Marina@Example.com",
                 "whatsapp": "(71) 99999-8888", "page": "editorial"}
        dados.update(extra)
        return dados

    def test_cadastro_vira_lead_na_coluna_interesse(self):
        r = self._post(self._dados(), HTTP_ORIGIN="https://thecreatorsclub.com.br")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://thecreatorsclub.com.br")
        lead = InfoLead.objects.get(workspace=self.ws)
        self.assertEqual(lead.name, "Marina Souza")
        self.assertEqual(lead.email, "marina@example.com")
        self.assertEqual(lead.whatsapp, "(71) 99999-8888")
        self.assertEqual(lead.stage, InfoLead.STAGE_PROSPEC)
        self.assertEqual(lead.interest, "Creator Day Experience")
        self.assertEqual(lead.origin, "Site")
        self.assertIn("Editorial", lead.note)
        self.assertEqual(
            list(InfoLeadEvent.objects.filter(lead=lead).values_list("text", flat=True)),
            ["entrou na lista de espera pela página Editorial"],
        )

    def test_pagina_imersivo_fica_registrada(self):
        self._post(self._dados(page="imersivo"))
        self.assertIn("Imersivo", InfoLead.objects.get().note)

    def test_mesma_pessoa_nao_duplica_card(self):
        self._post(self._dados())
        self._post(self._dados(name="Marina de novo", whatsapp="(71) 98888-7777"))  # mesmo email
        self._post(self._dados(email="outro@example.com"))  # mesmo WhatsApp
        self.assertEqual(InfoLead.objects.count(), 1)
        self.assertEqual(InfoLeadEvent.objects.count(), 1)  # dentro de 6h nao repete historico

    def test_volta_depois_de_6h_registra_no_historico(self):
        self._post(self._dados())
        InfoLead.objects.update(updated_at=timezone.now() - timezone.timedelta(hours=7))
        self._post(self._dados(page="imersivo"))
        self.assertEqual(InfoLead.objects.count(), 1)
        textos = list(InfoLeadEvent.objects.values_list("text", flat=True))
        self.assertIn("entrou de novo na lista de espera pela página Imersivo", textos)

    def test_lead_de_outro_interesse_nao_bloqueia(self):
        InfoLead.objects.create(workspace=self.ws, name="Marina", email="marina@example.com",
                                interest="Mentoria HPC")
        self._post(self._dados())
        self.assertEqual(InfoLead.objects.filter(interest="Creator Day Experience").count(), 1)

    def test_dados_incompletos_sao_recusados(self):
        self.assertEqual(self._post(self._dados(name="")).status_code, 400)
        self.assertEqual(self._post(self._dados(email="sem-arroba")).status_code, 400)
        self.assertEqual(self._post(self._dados(whatsapp="99999-888")).status_code, 400)
        self.assertFalse(InfoLead.objects.exists())

    def test_honeypot_e_robo_nao_criam_lead(self):
        r = self._post(self._dados(site="http://spam"))
        self.assertEqual(r.status_code, 200)
        self._post(self._dados(), HTTP_USER_AGENT="python-requests/bot")
        self.assertFalse(InfoLead.objects.exists())

    def test_json_invalido_e_preflight(self):
        r = self.client.post(reverse("creator_day_lead"), data="nao e json", content_type="text/plain")
        self.assertEqual(r.status_code, 400)
        r = self.client.options(reverse("creator_day_lead"), HTTP_ORIGIN="https://thecreatorsclub.com.br")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://thecreatorsclub.com.br")
