"""Barra de etapas da página do lead no CRM (linha do tempo + Perdido à parte)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from studio.models import InfoLead
from studio.services import get_or_create_workspace_for_user


class BarraDeEtapasDoLeadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("layfeamorim", password="x")
        self.ws = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)

    def pagina(self, stage):
        lead = InfoLead.objects.create(workspace=self.ws, name="Ana", interest="Mentoria", stage=stage)
        return lead, self.client.get(reverse("crm_lead", args=[lead.pk])).content.decode()

    def test_etapas_anteriores_ficam_marcadas_e_a_atual_em_destaque(self):
        _, html = self.pagina(InfoLead.STAGE_PROPOSTA)
        self.assertEqual(html.count("lead-step is-done"), 3)  # Interesse, Primeiro Contato, Qualificação
        self.assertEqual(html.count("lead-step is-current"), 1)
        self.assertEqual(html.count("lead-step is-next"), 2)  # Negociação, Fechado
        self.assertIn('aria-current="step" title="Mover para Proposta Enviada"', html)
        self.assertIn("Marcar como perdido", html)
        self.assertNotIn("lead-stagebar is-lost", html)

    def test_perdido_fica_separado_e_marcado(self):
        _, html = self.pagina(InfoLead.STAGE_PERDIDO)
        self.assertIn("lead-stagebar is-lost", html)
        self.assertIn("lead-lost is-current", html)
        self.assertNotIn("lead-step is-done", html)
        self.assertNotIn("lead-step is-current", html)
        self.assertNotIn("Marcar como perdido", html)

    def test_cada_etapa_continua_mudando_o_lead_sem_perder_dados(self):
        lead, html = self.pagina(InfoLead.STAGE_PROSPEC)
        barra = html[html.index('class="lead-stagebar'):html.index('class="lead-grid"')]
        self.assertEqual(barra.count('<input type="hidden" name="stage"'), 7)
        self.assertEqual(barra.count('<input type="hidden" name="interest" value="Mentoria">'), 7)
        self.client.post(reverse("crm_lead_update", args=[lead.pk]),
                         {"name": lead.name, "interest": "Mentoria", "stage": InfoLead.STAGE_NEGOC})
        lead.refresh_from_db()
        self.assertEqual((lead.stage, lead.interest), (InfoLead.STAGE_NEGOC, "Mentoria"))
