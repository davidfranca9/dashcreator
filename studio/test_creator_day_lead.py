"""Formulário das prévias do Creator Day -> lista de espera do evento (fora do CRM)."""
import json

from django.test import TestCase
from django.urls import reverse

from studio.models import EventWaitlistEntry, InfoLead


class CreatorDayLeadTests(TestCase):
    def _post(self, payload, **extra):
        return self.client.post(reverse("creator_day_lead"), data=json.dumps(payload),
                                content_type="text/plain;charset=utf-8", **extra)

    def _dados(self, **extra):
        dados = {"name": "Marina Souza", "email": "Marina@Example.com",
                 "whatsapp": "(71) 99999-8888", "page": "editorial"}
        dados.update(extra)
        return dados

    def test_cadastro_entra_na_lista_de_espera_e_nao_no_crm(self):
        r = self._post(self._dados(), HTTP_ORIGIN="https://thecreatorsclub.com.br")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://thecreatorsclub.com.br")
        entrada = EventWaitlistEntry.objects.get()
        self.assertEqual(entrada.event_key, "creatorday")
        self.assertEqual(entrada.name, "Marina Souza")
        self.assertEqual(entrada.email, "marina@example.com")
        self.assertEqual(entrada.whatsapp, "(71) 99999-8888")
        self.assertEqual(entrada.page, "editorial")
        self.assertFalse(InfoLead.objects.exists())

    def test_pagina_desconhecida_vira_site(self):
        self._post(self._dados(page="outra"))
        self.assertEqual(EventWaitlistEntry.objects.get().page, "site")

    def test_mesma_pessoa_nao_repete_na_lista(self):
        self._post(self._dados())
        self._post(self._dados(name="Marina de novo", whatsapp="(71) 98888-7777"))  # mesmo email
        self._post(self._dados(email="outro@example.com"))  # mesmo WhatsApp
        self.assertEqual(EventWaitlistEntry.objects.count(), 1)

    def test_dados_incompletos_sao_recusados(self):
        self.assertEqual(self._post(self._dados(name="")).status_code, 400)
        self.assertEqual(self._post(self._dados(email="sem-arroba")).status_code, 400)
        self.assertEqual(self._post(self._dados(whatsapp="99999-888")).status_code, 400)
        self.assertFalse(EventWaitlistEntry.objects.exists())

    def test_honeypot_e_robo_nao_entram(self):
        r = self._post(self._dados(site="http://spam"))
        self.assertEqual(r.status_code, 200)
        self._post(self._dados(), HTTP_USER_AGENT="python-requests/bot")
        self.assertFalse(EventWaitlistEntry.objects.exists())

    def test_json_invalido_e_preflight(self):
        r = self.client.post(reverse("creator_day_lead"), data="nao e json", content_type="text/plain")
        self.assertEqual(r.status_code, 400)
        r = self.client.options(reverse("creator_day_lead"), HTTP_ORIGIN="https://thecreatorsclub.com.br")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r["Access-Control-Allow-Origin"], "https://thecreatorsclub.com.br")
