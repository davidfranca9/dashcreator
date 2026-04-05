import re
import shutil
import tempfile
from unittest.mock import patch
from io import StringIO
from io import BytesIO
from datetime import date, timedelta

from django.contrib.sessions.models import Session
from django.core import mail
from django.core.management import call_command
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.core.management.base import CommandError
from django.urls import reverse
from PIL import Image

from .forms import ContractBrandForm, ProjectForm, ProspectForm
from .models import AccessCode, ActiveUserSession, FinanceEntry, Membership, Niche, Project, Prospect, ServiceCategory
from .services import dashboard_snapshot, get_or_create_workspace_for_user, jobs_snapshot, jobs_snapshot_filtered, shell_context
from .views import _contract_clause_five_text, _project_contract_payload


class DashboardSmokeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.niche = Niche.objects.get(workspace=self.workspace, name="Beleza")
        self.category = ServiceCategory.objects.create(workspace=self.workspace, name="Pacote de videos")
        Prospect.objects.create(
            workspace=self.workspace,
            company="Nike",
            contact="Paula",
            contact_type="Marketing",
            stage="Prospeccao",
            contact_date=date.today(),
            niche=self.niche,
            email="paula@nike.com",
            instagram="@nikebrasil",
            whatsapp="71999999999",
            proposal_value=1800,
            note="Primeiro contato",
            meeting_scheduled=True,
        )
        self.project = Project.objects.create(
            workspace=self.workspace,
            company="Shein",
            closing_source="Instagram",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote de videos",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=2400,
            entry_value=1200,
            received_value=800,
            deliverables_count=3,
            progress=35,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=10),
        )

    def test_dashboard_pages_load(self):
        self.client.force_login(self.user)
        for name in ["dashboard", "prospection", "jobs", "finance", "distribution", "legal", "reports", "settings", "profile"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, "workspace-chip-avatar-fallback")
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertNotContains(dashboard_response, 'nav-group-label">Perfil<', html=False)

    def test_workspace_uses_default_niches_and_can_create_reusable_service_category_from_settings(self):
        self.client.force_login(self.user)

        category_response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "add_service_category",
                "service_category-name": "Mentoria UGC",
            },
        )
        self.assertRedirects(category_response, reverse("settings"))
        category = ServiceCategory.objects.get(workspace=self.workspace, name="Mentoria UGC")

        prospect_response = self.client.post(
            reverse("prospect_create"),
            {
                "company": "Insider",
                "contact": "Julia",
                "contact_type": "Social media",
                "stage": "Prospeccao",
                "contact_date": date.today().isoformat(),
                "niche": self.niche.pk,
                "email": "julia@insider.com",
                "instagram": "@insiderstore",
                "whatsapp": "71911111111",
                "note": "Chegou pelo Instagram",
            },
        )
        self.assertRedirects(prospect_response, reverse("prospection"))
        self.assertTrue(Prospect.objects.filter(workspace=self.workspace, niche=self.niche).exists())

        project_response = self.client.post(
            reverse("project_create"),
            {
                "company": "Insider",
                "service_category": category.pk,
                "stage": "Fechado",
                "status": "Briefing",
                "total_value": "4000",
                "entry_value": "2000",
                "received_value": "0",
                "deliverables_count": "2",
                "progress": "20",
                "close_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=7)).isoformat(),
            },
        )
        self.assertRedirects(project_response, reverse("jobs"))
        self.assertTrue(Project.objects.filter(workspace=self.workspace, service_category=category).exists())

    def test_settings_can_delete_unused_service_category(self):
        self.client.force_login(self.user)
        category = ServiceCategory.objects.create(workspace=self.workspace, name="Categoria temporaria")

        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "delete_service_category",
                "service_category_id": category.pk,
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("settings"))
        self.assertFalse(ServiceCategory.objects.filter(pk=category.pk).exists())
        self.assertContains(response, "Categoria de serviço removida.")

    def test_settings_does_not_delete_used_service_category(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("settings"),
            {
                "settings_action": "delete_service_category",
                "service_category_id": self.category.pk,
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("settings"))
        self.assertTrue(ServiceCategory.objects.filter(pk=self.category.pk).exists())
        self.assertContains(response, "nao pode mais ser excluida")

    def test_prospect_edit_prefills_contact_date_in_iso_format(self):
        self.client.force_login(self.user)
        prospect = Prospect.objects.get(workspace=self.workspace, company="Nike")

        response = self.client.get(reverse("prospect_edit", args=[prospect.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{prospect.contact_date.isoformat()}"', html=False)

    def test_prospect_form_hides_estimated_value_until_conversion(self):
        form = ProspectForm(workspace=self.workspace)

        self.assertNotIn("proposal_value", form.fields)
        self.assertNotIn("new_niche", form.fields)
        self.assertEqual(form.fields["stage"].initial, "Rascunho")
        self.assertIn(("Rascunho", "Rascunho"), form.fields["stage"].choices)
        self.assertIn(("Aguardando retorno", "Aguardando retorno"), form.fields["stage"].choices)
        self.assertEqual(list(form.fields.keys())[:4], ["company", "contact_type", "contact", "stage"])
        self.assertTrue(form.fields["contact_type"].required)
        self.assertFalse(form.fields["contact"].required)

    def test_prospect_form_requires_meeting_date_when_meeting_is_scheduled(self):
        form = ProspectForm(
            data={
                "company": "Insider",
                "contact": "Julia",
                "contact_type": "Social media",
                "stage": "Prospeccao",
                "contact_date": date.today().isoformat(),
                "niche": "",
                "new_niche": "",
                "email": "julia@insider.com",
                "instagram": "@insiderstore",
                "whatsapp": "71911111111",
                "meeting_scheduled": "on",
                "meeting_date": "",
                "note": "Chegou pelo Instagram",
            },
            workspace=self.workspace,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("meeting_date", form.errors)

    def test_dashboard_pages_show_popup_for_today_meetings(self):
        Prospect.objects.create(
            workspace=self.workspace,
            company="Reserva",
            contact="Marina",
            contact_type="Instagram DM",
            stage="Negociacao",
            contact_date=date.today(),
            meeting_date=date.today(),
            niche=self.niche,
            email="marina@reserva.com",
            instagram="@reserva",
            whatsapp="71988887777",
            proposal_value=3200,
            note="Quente",
            meeting_scheduled=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reunioes de hoje")
        self.assertContains(response, "Reserva")

    def test_prospection_adds_follow_up_column_for_old_delivered_brand(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=45),
            due_date=date.today() - timedelta(days=40),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("prospection"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [column["title"] for column in response.context["columns"]],
            ["Rascunho", "Prospecção", "Aguardando retorno", "Negociação", "Follow-up"],
        )
        self.assertContains(response, "Follow-up")
        self.assertEqual(response.context["columns"][-1]["items"], [])

    def test_prospection_shows_follow_up_popup_for_old_delivered_brand(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=45),
            due_date=date.today() - timedelta(days=40),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("prospection"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hora de retomar contato")
        self.assertContains(response, "Reserva")
        self.assertContains(response, reverse("follow_up_confirm"))
        self.assertContains(response, reverse("follow_up_dismiss"))
        self.assertContains(response, "Nunca mais lembrar da marca Reserva")

    def test_follow_up_confirm_moves_popup_brands_to_follow_up_column(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=45),
            due_date=date.today() - timedelta(days=40),
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("follow_up_confirm"),
            {"company_keys": ["reserva"]},
            follow=True,
        )

        self.assertRedirects(response, f"{reverse('prospection')}#follow-up-column")
        self.assertContains(response, "Marcas enviadas para o follow-up.")
        self.assertEqual(len(response.context["columns"][-1]["items"]), 1)
        self.assertEqual(response.context["columns"][-1]["items"][0]["company"], "Reserva")
        self.assertEqual(response.context["follow_up_alerts"], [])

    def test_follow_up_dismiss_hides_brand_from_future_popups(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=45),
            due_date=date.today() - timedelta(days=40),
        )
        self.client.force_login(self.user)

        self.client.post(reverse("follow_up_dismiss"), {"company_key": "reserva"})
        response = self.client.get(reverse("prospection"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["follow_up_alerts"], [])
        self.assertEqual(response.context["columns"][-1]["items"], [])
        self.assertNotContains(response, "Nunca mais lembrar da marca Reserva")

    def test_follow_up_start_prospection_creates_new_lead_and_clears_follow_up(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=45),
            due_date=date.today() - timedelta(days=40),
        )
        self.client.force_login(self.user)
        self.client.post(reverse("follow_up_confirm"), {"company_keys": ["reserva"]})

        response = self.client.post(
            reverse("follow_up_start_prospection"),
            {"company_key": "reserva"},
            follow=True,
        )

        self.assertRedirects(response, reverse("prospection"))
        self.assertContains(response, "Reserva voltou para Prospecção.")
        lead = Prospect.objects.get(workspace=self.workspace, company="Reserva")
        self.assertEqual(lead.stage, "Prospeccao")
        self.assertEqual(lead.contact, "Contato principal")
        self.assertEqual(lead.contact_type, "Follow-up")
        self.assertEqual(response.context["columns"][-1]["items"], [])
        prospection_column = next(column for column in response.context["columns"] if column["title"] == "Prospecção")
        prospection_companies = [item["company"] for item in prospection_column["items"]]
        self.assertIn("Reserva", prospection_companies)

    def test_dashboard_does_not_show_follow_up_popup(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=45),
            due_date=date.today() - timedelta(days=40),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Nunca mais lembrar da marca Reserva")

    def test_project_form_uses_workspace_default_entry_rate_and_prefills_close_date(self):
        self.workspace.settings.update_or_create(
            key="ops_default_entry_rate",
            defaults={"value": "40%"},
        )

        form = ProjectForm(workspace=self.workspace)

        self.assertEqual(form.default_entry_rate, 40)
        self.assertEqual(form.fields["close_date"].initial, date.today())
        self.assertEqual(form.fields["deliverables_count"].label, "Quantidade de videos")
        self.assertIn("quantidade total de videos", form.fields["deliverables_count"].help_text)
        self.assertIn(("Inbound", "Inbound"), form.fields["closing_source"].choices)
        self.assertIn(("Prospeccao", "Prospecção"), form.fields["closing_source"].choices)
        self.assertIn(("Follow-up", "Follow-up"), form.fields["closing_source"].choices)
        self.assertIn(("Plataforma", "Plataforma"), form.fields["closing_source"].choices)
        self.assertIn(("Agencia", "Agência"), form.fields["closing_source"].choices)
        self.assertIn(("Indicacao", "Indicação"), form.fields["closing_source"].choices)
        self.assertIn(("Nao se aplica", "Não se aplica"), form.fields["closing_source"].choices)
        self.assertNotIn("progress", form.fields)
        self.assertIn(("Aguardando produto", "Aguardando produto"), form.fields["status"].choices)
        self.assertIn(("Organico", "Organico"), form.fields["content_distribution"].choices)
        self.assertIn(("Ads", "Ads"), form.fields["content_distribution"].choices)
        self.assertIn(("Nao se aplica", "Não se aplica"), form.fields["content_distribution"].choices)
        self.assertIn("payment_due_date", form.fields)
        self.assertIn("meeting_scheduled", form.fields)
        self.assertIn("meeting_date", form.fields)
        self.assertIn("note", form.fields)
        self.assertIn("image_license_term_days", form.fields)

    def test_project_form_syncs_stage_with_status(self):
        delivered_form = ProjectForm(
            data={
                "company": "Insider",
                "closing_source": "Indicacao",
                "content_distribution": "Organico",
                "niche": self.niche.pk,
                "service_category": self.category.pk,
                "stage": "Fechado",
                "status": "Entregue",
                "total_value": "4000",
                "entry_value": "2000",
                "received_value": "4000",
                "deliverables_count": "2",
                "close_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=7)).isoformat(),
            },
            workspace=self.workspace,
        )

        self.assertTrue(delivered_form.is_valid(), delivered_form.errors)
        delivered_project = delivered_form.save(commit=False)
        delivered_project.workspace = self.workspace
        delivered_project.save()
        self.assertEqual(delivered_project.stage, "Entregue")
        self.assertEqual(delivered_project.progress, 100)

        active_form = ProjectForm(
            data={
                "company": "Insider",
                "closing_source": "Indicacao",
                "content_distribution": "Organico",
                "niche": self.niche.pk,
                "service_category": self.category.pk,
                "stage": "Entregue",
                "status": "Briefing",
                "total_value": "4000",
                "entry_value": "2000",
                "received_value": "0",
                "deliverables_count": "2",
                "close_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=7)).isoformat(),
            },
            workspace=self.workspace,
        )

        self.assertTrue(active_form.is_valid(), active_form.errors)
        active_project = active_form.save(commit=False)
        active_project.workspace = self.workspace
        active_project.save()
        self.assertEqual(active_project.stage, "Fechado")
        self.assertEqual(active_project.progress, 0)

        meeting_form = ProjectForm(
            data={
                "company": "Insider",
                "closing_source": "Follow-up",
                "content_distribution": "Ads",
                "niche": self.niche.pk,
                "service_category": self.category.pk,
                "stage": "Fechado",
                "status": "Briefing",
                "total_value": "4000",
                "entry_value": "2000",
                "received_value": "0",
                "deliverables_count": "2",
                "image_license_term_days": "90",
                "payment_due_date": (date.today() + timedelta(days=15)).isoformat(),
                "meeting_scheduled": "on",
                "meeting_date": "",
                "close_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=7)).isoformat(),
                "note": "Observacao extra",
            },
            workspace=self.workspace,
        )

        self.assertFalse(meeting_form.is_valid())
        self.assertIn("meeting_date", meeting_form.errors)

        waiting_product_form = ProjectForm(
            data={
                "company": "Insider",
                "closing_source": "Indicacao",
                "content_distribution": "Organico",
                "niche": self.niche.pk,
                "service_category": self.category.pk,
                "stage": "Fechado",
                "status": "Aguardando produto",
                "total_value": "4000",
                "entry_value": "2000",
                "received_value": "0",
                "deliverables_count": "2",
                "close_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=7)).isoformat(),
            },
            workspace=self.workspace,
        )

        self.assertTrue(waiting_product_form.is_valid(), waiting_product_form.errors)
        waiting_product_project = waiting_product_form.save(commit=False)
        waiting_product_project.workspace = self.workspace
        waiting_product_project.save()
        self.assertEqual(waiting_product_project.stage, "Fechado")
        self.assertEqual(waiting_product_project.progress, 10)

        ads_without_term_form = ProjectForm(
            data={
                "company": "Insider",
                "closing_source": "Inbound",
                "content_distribution": "Ads",
                "niche": self.niche.pk,
                "service_category": self.category.pk,
                "stage": "Fechado",
                "status": "Briefing",
                "total_value": "3000",
                "entry_value": "1500",
                "received_value": "0",
                "deliverables_count": "2",
                "close_date": date.today().isoformat(),
                "due_date": (date.today() + timedelta(days=7)).isoformat(),
            },
            workspace=self.workspace,
        )

        self.assertFalse(ads_without_term_form.is_valid())
        self.assertIn("image_license_term_days", ads_without_term_form.errors)

    def test_distribution_and_legal_pages_reflect_ads_licensing(self):
        project = Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            content_distribution="Ads",
            image_license_term_days=90,
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=2,
            progress=0,
            close_date=date.today() - timedelta(days=90),
            due_date=date.today() - timedelta(days=90),
            note="Ads com licenciamento",
        )
        self.client.force_login(self.user)

        distribution_response = self.client.get(reverse("distribution"))
        legal_response = self.client.get(reverse("legal"))

        self.assertContains(distribution_response, "Ads")
        self.assertContains(distribution_response, "Reserva")
        self.assertContains(legal_response, "Contratos dos trabalhos")
        self.assertContains(legal_response, "Gerar contrato")
        self.assertContains(legal_response, "Direito de uso de imagem")
        self.assertContains(legal_response, "90 dias")
        self.assertContains(
            legal_response,
            "Oi, tester O DIREITO DE USO DE IMAGEM DA MARCA Reserva ESTÁ VENCENDO HOJE, QUE TAL MANDAR UMA MENSAGEM PARA VER COMO ESTÁ PERFORMANDO O SEU CRIATIVO?",
        )
        self.assertContains(legal_response, reverse("legal_contract_pdf", args=[project.pk]))

    def test_distribution_page_groups_nao_se_aplica(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            content_distribution="Nao se aplica",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=2,
            progress=0,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=5),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("distribution"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Não se aplica")
        self.assertContains(response, "Reserva")

    def test_legal_contract_pdf_downloads_generated_document(self):
        project = Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            content_distribution="Ads",
            image_license_term_days=180,
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=2,
            progress=0,
            close_date=date.today() - timedelta(days=5),
            due_date=date.today() + timedelta(days=5),
            note="Ads com licenciamento",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("legal_contract_pdf", args=[project.pk]),
            {
                "company_legal_name": "Reserva LTDA",
                "company_cnpj": "12.345.678/0001-99",
                "company_address": "Rua das Flores, 123",
                "company_phone": "(71) 99999-0000",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(".pdf", response["Content-Disposition"])
        pdf_bytes = b"".join(response.streaming_content) if hasattr(response, "streaming_content") else response.content
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        project.refresh_from_db()
        self.assertEqual(project.contract_status, Project.CONTRACT_STATUS_GENERATED)
        self.assertEqual(project.company_legal_name, "Reserva LTDA")
        self.assertEqual(project.company_cnpj, "12.345.678/0001-99")

    def test_contract_clause_five_uses_dynamic_ads_license_term(self):
        self.project.content_distribution = "Ads"
        self.project.image_license_term_days = 180
        self.project.save(update_fields=["content_distribution", "image_license_term_days", "updated_at"])

        payload = _project_contract_payload(self.workspace, self.user, self.project)
        clause = _contract_clause_five_text(payload)

        self.assertIn("06 (seis) meses", clause)
        self.assertIn("180 (cento e oitenta) dias", clause)
        self.assertIn("tráfego pago (ads)", clause)

    def test_legal_page_can_dismiss_contract_item(self):
        project = Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=2,
            progress=0,
            close_date=date.today() - timedelta(days=5),
            due_date=date.today() + timedelta(days=5),
        )
        self.client.force_login(self.user)

        response = self.client.post(reverse("legal_contract_dismiss", args=[project.pk]), follow=True)

        self.assertRedirects(response, reverse("legal"))
        project.refresh_from_db()
        self.assertEqual(project.contract_status, Project.CONTRACT_STATUS_DISMISSED)
        self.assertContains(response, "Contrato dispensado para Reserva.")
        self.assertNotContains(response, reverse("legal_contract_pdf", args=[project.pk]))

    def test_contract_payload_uses_name_configured_in_settings(self):
        self.workspace.settings.update_or_create(
            key="legal_contract_signer_name",
            defaults={"value": "Layfe Amorim"},
        )

        payload = _project_contract_payload(self.workspace, self.user, self.project)

        self.assertEqual(payload["creator_name"], "Layfe Amorim")
        self.assertIn("CRIAÇÃO DE CONTEÚDO UGC", payload["contract_title"])

    def test_contract_brand_form_formats_cnpj(self):
        form = ContractBrandForm(
            data={
                "company_legal_name": "BRND DISTRIBUIDORA LTDA",
                "company_cnpj": "50181021000129",
                "company_address": "Rua David Pereira Coimbra, 1-82",
                "company_phone": "(14) 99999-0000",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["company_cnpj"], "50.181.021/0001-29")

    @patch("studio.views.urlopen")
    def test_business_cnpj_lookup_autofills_brand_data(self, mocked_urlopen):
        self.client.force_login(self.user)
        mocked_urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"result":{"cnpj":"50181021000129","razao_social":"BRND DISTRIBUIDORA LTDA","logradouro":"Rua David Pereira Coimbra","numero":"1-82","bairro":"Jardim Rosas do Sul","municipio":"Bauru","uf":"SP","cep":"17030-690","telefone":"(14) 99123-4567"}}'
        )

        with self.settings(
            APIBRASIL_CNPJ_URL="https://api.apibrasil.example/cnpj/{cnpj}",
            APIBRASIL_CNPJ_TOKEN="token-teste",
        ):
            response = self.client.get(reverse("business_cnpj_lookup"), {"cnpj": "50181021000129"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "ok": True,
                "company_legal_name": "BRND DISTRIBUIDORA LTDA",
                "company_cnpj": "50.181.021/0001-29",
                "company_address": "Rua David Pereira Coimbra, 1-82, Jardim Rosas do Sul, Bauru - SP, CEP 17030-690",
                "company_phone": "(14) 99123-4567",
            },
        )

    def test_settings_page_shows_contract_signer_name_field(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nome no contrato")

    def test_dashboard_counts_unique_contracting_companies(self):
        Prospect.objects.create(
            workspace=self.workspace,
            company=" shein ",
            contact="Marina",
            contact_type="Instagram DM",
            stage="Prospeccao",
            contact_date=date.today(),
            niche=self.niche,
            email="marina@shein.com",
            instagram="@shein",
            whatsapp="71988887777",
            proposal_value=3200,
            note="Cliente repetido",
            meeting_scheduled=False,
        )
        Project.objects.create(
            workspace=self.workspace,
            company=" shein ",
            closing_source="Instagram",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=10),
        )

        snapshot = dashboard_snapshot(self.workspace)

        self.assertEqual(snapshot["stats"][0]["title"], "Carteira de Clientes")
        self.assertEqual(snapshot["stats"][1]["title"], "Carteira Ativa")
        self.assertEqual(snapshot["stats"][2]["title"], "Trabalhos Ativos")
        self.assertEqual(snapshot["stats"][3]["title"], "Faturamento Mensal")
        self.assertEqual(snapshot["stats"][0]["value"], "2")
        self.assertEqual(snapshot["stats"][1]["value"], "1")
        self.assertEqual(snapshot["stats"][2]["value"], "3")
        self.assertEqual(snapshot["stats"][3]["value"], "R$2.400")
        self.assertEqual(len(snapshot["revenue"]["points"]), 12)

    def test_dashboard_deduplicates_company_names_with_accents_and_punctuation(self):
        Prospect.objects.create(
            workspace=self.workspace,
            company="O BoticÃ¡rio!!!",
            contact="Julia",
            contact_type="Email",
            stage="Prospeccao",
            contact_date=date.today(),
            niche=self.niche,
            email="julia@boticario.com",
            instagram="@boticario",
            whatsapp="71911111111",
            note="Mesmo cliente com variacao no nome",
        )
        Project.objects.create(
            workspace=self.workspace,
            company="o boticario",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=1,
            progress=0,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=5),
        )

        snapshot = dashboard_snapshot(self.workspace)
        jobs = jobs_snapshot(self.workspace)

        self.assertEqual(snapshot["stats"][0]["value"], "3")
        self.assertEqual(jobs["stats"][0]["value"], "2")

    def test_jobs_snapshot_shows_delivered_total_as_finalizado(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Insider",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=10),
        )

        snapshot = jobs_snapshot(self.workspace)

        self.assertEqual(snapshot["stats"][0]["title"], "Carteira ativa")
        self.assertEqual(snapshot["stats"][3]["title"], "Finalizado")
        self.assertEqual(snapshot["stats"][3]["value"], "1")

    def test_jobs_page_filters_by_type_progress_niche_and_search(self):
        tech_niche = Niche.objects.get(workspace=self.workspace, name="Tech")
        second_category = ServiceCategory.objects.create(workspace=self.workspace, name="Stories")
        Project.objects.create(
            workspace=self.workspace,
            company="Insider",
            closing_source="Inbound",
            niche=tech_niche,
            service_category=second_category,
            project_name="Pacote extra",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=date.today() - timedelta(days=5),
            due_date=date.today() - timedelta(days=1),
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("jobs"),
            {
                "service_category": str(second_category.pk),
                "progress": "entregue",
                "niche": str(tech_niche.pk),
                "search": "insider",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Filtrar por Tipo")
        self.assertEqual(response.context["filters"]["service_category"], str(second_category.pk))
        self.assertEqual(response.context["filters"]["progress"], "entregue")
        self.assertEqual(response.context["filters"]["niche"], str(tech_niche.pk))
        self.assertEqual(response.context["filters"]["search"], "insider")
        self.assertEqual(len(response.context["active"]), 0)
        self.assertEqual(len(response.context["delivered"]), 1)
        self.assertEqual(response.context["delivered"][0]["company"], "Insider")

    def test_jobs_page_applies_global_month_filter_and_preserves_it_in_links(self):
        previous_month = (self.project.close_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        Project.objects.create(
            workspace=self.workspace,
            company="Insider",
            closing_source="Inbound",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote anterior",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=2,
            progress=0,
            close_date=previous_month,
            due_date=previous_month + timedelta(days=8),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("jobs"), {"month": self.project.close_date.strftime("%Y-%m")})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_month"]["value"], self.project.close_date.strftime("%Y-%m"))
        self.assertEqual(len(response.context["active"]), 1)
        self.assertEqual(response.context["active"][0]["company"], "Shein")
        self.assertContains(response, f'name="month" value="{self.project.close_date.strftime("%Y-%m")}"', html=False)
        self.assertContains(response, f'{reverse("finance")}?month={self.project.close_date.strftime("%Y-%m")}')

    def test_jobs_upcoming_deliveries_respect_delivery_month(self):
        current_month = date.today().replace(day=1)
        previous_month = (current_month - timedelta(days=1)).replace(day=1)
        Project.objects.create(
            workspace=self.workspace,
            company="Insider",
            closing_source="Inbound",
            niche=self.niche,
            service_category=self.category,
            project_name="Entrega abril",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=2,
            progress=0,
            close_date=previous_month + timedelta(days=5),
            due_date=date.today(),
        )

        previous_snapshot = jobs_snapshot_filtered(self.workspace, month_filter=previous_month.strftime("%Y-%m"))
        current_snapshot = jobs_snapshot_filtered(self.workspace, month_filter=current_month.strftime("%Y-%m"))

        self.assertEqual(len(previous_snapshot["stat_lists"][2]["items"]), 0)
        current_companies = [item["company"] for item in current_snapshot["stat_lists"][2]["items"]]
        self.assertIn("Insider", current_companies)

    def test_jobs_page_all_months_keeps_latest_deliveries(self):
        previous_month = (self.project.close_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        Project.objects.create(
            workspace=self.workspace,
            company="Insider",
            closing_source="Inbound",
            niche=self.niche,
            service_category=self.category,
            project_name="Entrega anterior",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=1800,
            entry_value=900,
            received_value=1800,
            deliverables_count=2,
            progress=100,
            close_date=previous_month,
            due_date=previous_month + timedelta(days=8),
        )
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Entrega recente",
            content_type="",
            stage="Entregue",
            status="Entregue",
            total_value=2200,
            entry_value=1100,
            received_value=2200,
            deliverables_count=3,
            progress=100,
            close_date=self.project.close_date,
            due_date=self.project.due_date + timedelta(days=2),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("jobs"), {"month": "all"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_month"]["value"], "all")
        self.assertEqual(len(response.context["delivered"]), 2)
        self.assertEqual(response.context["delivered"][0]["company"], "Reserva")
        self.assertEqual(response.context["delivered"][1]["company"], "Insider")

    def test_jobs_snapshot_highlights_overdue_projects_and_google_calendar(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Follow-up",
            niche=self.niche,
            service_category=self.category,
            project_name="Entrega atrasada",
            content_type="",
            stage="Fechado",
            status="Aguardando produto",
            total_value=2200,
            entry_value=1100,
            received_value=0,
            deliverables_count=3,
            progress=10,
            payment_due_date=date.today() + timedelta(days=20),
            meeting_scheduled=True,
            meeting_date=date.today() + timedelta(days=3),
            note="Pedir retorno da marca",
            close_date=date.today() - timedelta(days=20),
            due_date=date.today() - timedelta(days=2),
        )

        snapshot = jobs_snapshot(self.workspace)

        self.assertEqual(snapshot["stats"][0]["title"], "Trabalhos atrasados")
        self.assertEqual(snapshot["stats"][0]["value"], "1")
        self.assertEqual(snapshot["overdue"][0]["company"], "Reserva")
        self.assertTrue(snapshot["overdue"][0]["google_calendar_url"].startswith("https://calendar.google.com/calendar/render?"))
        self.assertTrue(snapshot["overdue"][0]["payment_due_text"])
        self.assertEqual(snapshot["overdue"][0]["note"], "Pedir retorno da marca")

    def test_jobs_kpis_open_subtle_modal_lists(self):
        self.client.force_login(self.user)

        snapshot = jobs_snapshot(self.workspace)
        self.assertEqual(snapshot["stats"][0]["modal_id"], "jobs-kpi-overdue")
        self.assertEqual(snapshot["stats"][1]["modal_id"], "jobs-kpi-approval")
        self.assertEqual(snapshot["stats"][2]["modal_id"], "jobs-kpi-upcoming")
        self.assertEqual(snapshot["stats"][3]["modal_id"], "jobs-kpi-delivered")

        response = self.client.get(reverse("jobs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-jobs-kpi-open="jobs-kpi-overdue"', html=False)
        self.assertContains(response, 'data-jobs-kpi-open="jobs-kpi-approval"', html=False)
        self.assertContains(response, 'data-jobs-kpi-open="jobs-kpi-upcoming"', html=False)
        self.assertContains(response, 'data-jobs-kpi-open="jobs-kpi-delivered"', html=False)
        self.assertContains(response, 'data-jobs-kpi-modal="jobs-kpi-overdue"', html=False)
        self.assertContains(response, 'data-jobs-kpi-modal="jobs-kpi-approval"', html=False)
        self.assertContains(response, 'data-jobs-kpi-modal="jobs-kpi-upcoming"', html=False)
        self.assertContains(response, 'data-jobs-kpi-modal="jobs-kpi-delivered"', html=False)
        self.assertContains(response, "Entregas que já passaram da data e ainda precisam de atenção.")

    def test_jobs_source_mix_uses_fixed_closing_source_legend(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Insider",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=1,
            progress=0,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=5),
        )
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Plataforma",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=1,
            progress=0,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=5),
        )
        Project.objects.create(
            workspace=self.workspace,
            company="Boticario",
            closing_source="Agencia",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=1,
            progress=0,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=5),
        )
        Project.objects.create(
            workspace=self.workspace,
            company="Natura",
            closing_source="Prospeccao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=1,
            progress=0,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=5),
        )

        snapshot = jobs_snapshot(self.workspace)
        legend = {item["label"]: item for item in snapshot["source_mix"]["items"]}

        self.assertEqual(snapshot["source_mix"]["total"], 5)
        self.assertEqual(list(legend.keys()), ["Inbound", "Prospecção", "Follow-up", "Indicação", "Plataforma", "Agência"])
        self.assertEqual(legend["Inbound"]["count"], 1)
        self.assertEqual(legend["Prospecção"]["count"], 1)
        self.assertEqual(legend["Follow-up"]["count"], 0)
        self.assertEqual(legend["Indicação"]["count"], 1)
        self.assertEqual(legend["Plataforma"]["count"], 1)
        self.assertEqual(legend["Agência"]["count"], 1)

    def test_jobs_source_mix_ignores_nao_se_aplica(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Avon",
            closing_source="Nao se aplica",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote extra",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1800,
            entry_value=900,
            received_value=0,
            deliverables_count=1,
            progress=0,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=5),
        )

        snapshot = jobs_snapshot(self.workspace)
        counts = [item["count"] for item in snapshot["source_mix"]["items"]]

        self.assertEqual(snapshot["source_mix"]["total"], 1)
        self.assertEqual(counts[0], 1)
        self.assertTrue(all(count == 0 for count in counts[1:]))

    def test_shell_context_applies_dark_theme_class_from_workspace_settings(self):
        self.workspace.settings.update_or_create(
            key="ui_dark_theme",
            defaults={"value": "1"},
        )

        context = shell_context("dashboard", self.workspace, "Dashboard", "Resumo", user=self.user)

        self.assertEqual(context["theme_class"], "theme-dark")
        self.assertEqual(context["workspace_membership"].user, self.user)

    def test_finance_page_filters_month_detail_by_due_date(self):
        FinanceEntry.objects.create(
            workspace=self.workspace,
            kind=FinanceEntry.KIND_OUTGOING,
            amount=320,
            occurred_on=self.project.due_date,
            description="Editor de video",
        )
        Project.objects.create(
            workspace=self.workspace,
            company="Insider",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote de videos",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=5000,
            entry_value=2500,
            received_value=1000,
            deliverables_count=2,
            progress=25,
            close_date=date.today() + timedelta(days=5),
            due_date=date.today() + timedelta(days=50),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("finance"), {"month": self.project.due_date.strftime("%Y-%m")})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_month"]["value"], self.project.due_date.strftime("%Y-%m"))
        self.assertEqual(response.context["stats"][0]["value"], "R$800")
        self.assertEqual(response.context["stats"][1]["value"], "R$320")
        self.assertEqual(response.context["stats"][2]["value"], "R$1.600")
        self.assertEqual(response.context["stats"][3]["value"], "R$480")
        self.assertEqual(len(response.context["ledger"]), 2)
        self.assertEqual(len(response.context["schedule"]), 1)

    def test_finance_page_prefers_payment_due_date_when_available(self):
        payment_due_date = date.today() + timedelta(days=45)
        project = Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote mensal",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=3200,
            entry_value=1600,
            received_value=0,
            deliverables_count=2,
            progress=25,
            payment_due_date=payment_due_date,
            close_date=date.today(),
            due_date=date.today() + timedelta(days=7),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("finance"), {"month": payment_due_date.strftime("%Y-%m")})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_month"]["value"], payment_due_date.strftime("%Y-%m"))
        self.assertEqual(len(response.context["schedule"]), 1)
        self.assertEqual(response.context["schedule"][0]["company"], "Reserva")

    def test_finance_page_uses_job_receipts_and_creates_outgoing_entries(self):
        self.client.force_login(self.user)

        page_response = self.client.get(reverse("finance"), {"month": self.project.due_date.strftime("%Y-%m")})
        self.assertContains(page_response, "Entradas")
        self.assertContains(page_response, "R$800")
        self.assertNotContains(page_response, "Registrar entrada")

        outgoing_response = self.client.post(
            reverse("finance"),
            {
                "finance_action": "outgoing",
                "month": self.project.due_date.strftime("%Y-%m"),
                "outgoing-amount": "250",
                "outgoing-occurred_on": self.project.due_date.isoformat(),
                "outgoing-description": "Locacao de estudio",
            },
            follow=True,
        )
        self.assertRedirects(outgoing_response, f"{reverse('finance')}?month={self.project.due_date.strftime('%Y-%m')}")
        self.assertEqual(FinanceEntry.objects.filter(workspace=self.workspace, kind=FinanceEntry.KIND_OUTGOING).count(), 1)
        self.assertContains(outgoing_response, "Saída registrada.")

    def test_dashboard_snapshot_respects_selected_global_month(self):
        previous_month = (self.project.close_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote anterior",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1500,
            entry_value=750,
            received_value=0,
            deliverables_count=1,
            progress=0,
            close_date=previous_month,
            due_date=previous_month + timedelta(days=12),
        )

        snapshot = dashboard_snapshot(self.workspace, previous_month.strftime("%Y-%m"))

        self.assertEqual(snapshot["selected_month"]["value"], previous_month.strftime("%Y-%m"))
        self.assertEqual(snapshot["stats"][0]["value"], "1")
        self.assertEqual(snapshot["stats"][1]["value"], "1")
        self.assertEqual(snapshot["stats"][2]["value"], "1")
        self.assertEqual(snapshot["stats"][3]["value"], "R$1.500")

    def test_global_month_choices_include_all_and_are_sorted_ascending(self):
        previous_month = (self.project.close_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        Project.objects.create(
            workspace=self.workspace,
            company="Reserva",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote anterior",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1500,
            entry_value=750,
            received_value=0,
            deliverables_count=1,
            progress=0,
            close_date=previous_month,
            due_date=previous_month + timedelta(days=12),
        )

        snapshot = dashboard_snapshot(self.workspace, "all")

        self.assertEqual(snapshot["selected_month"]["value"], "all")
        self.assertEqual(snapshot["month_choices"][0]["value"], "all")
        self.assertEqual(snapshot["month_choices"][0]["label"], "Todos")
        month_values = [item["value"] for item in snapshot["month_choices"][1:]]
        self.assertEqual(month_values, sorted(month_values))
        self.assertIn(previous_month.strftime("%Y-%m"), month_values)
        self.assertIn(self.project.close_date.strftime("%Y-%m"), month_values)
        self.assertEqual(snapshot["stats"][0]["value"], "3")

    def test_reports_page_shows_month_overview_with_via_and_top_niche(self):
        Project.objects.create(
            workspace=self.workspace,
            company="Insider",
            closing_source="Indicacao",
            niche=self.niche,
            service_category=self.category,
            project_name="Pacote de videos",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=5000,
            entry_value=2500,
            received_value=1000,
            deliverables_count=2,
            progress=25,
            close_date=self.project.close_date,
            due_date=self.project.due_date + timedelta(days=20),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("reports"), {"month": self.project.close_date.strftime("%Y-%m")})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_month"]["value"], self.project.close_date.strftime("%Y-%m"))
        self.assertEqual(response.context["stats"][0]["value"], "2")
        self.assertEqual(response.context["stats"][1]["value"], "R$7.400")
        self.assertEqual(response.context["stats"][2]["value"], "Inbound")
        self.assertEqual(response.context["stats"][3]["value"], "Beleza")
        self.assertEqual(response.context["via_breakdown"][0]["amount_text"], "50%")
        self.assertEqual(response.context["source_mix"]["total"], 2)
        self.assertContains(response, "Via de fechamento")

    def test_reports_page_shows_prospection_evolution_flow(self):
        previous_prospect_date = date.today() - timedelta(days=11)
        Prospect.objects.create(
            workspace=self.workspace,
            company="Reserva",
            contact="Marina",
            contact_type="Instagram DM",
            stage="Aguardando retorno",
            contact_date=previous_prospect_date,
            niche=self.niche,
            email="marina@reserva.com",
            instagram="@reserva",
            whatsapp="71988887777",
            note="Primeira tentativa",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("reports"), {"month": "all"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evolução da prospecção")
        self.assertContains(response, "Maior intervalo")
        self.assertContains(response, "11 dias")
        self.assertTrue(response.context["prospection_flow"]["points"])
        self.assertEqual(response.context["prospection_flow"]["summary"][2]["value"], "11 dias")

    def test_prospect_conversion_prefills_closing_source_and_niche(self):
        prospect = Prospect.objects.create(
            workspace=self.workspace,
            company="Reserva",
            contact="Marina",
            contact_type="Instagram DM",
            stage="Negociacao",
            contact_date=date.today(),
            niche=self.niche,
            email="marina@reserva.com",
            instagram="@reserva",
            whatsapp="71988887777",
            proposal_value=3200,
            note="Quente",
            meeting_scheduled=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("prospect_convert", args=[prospect.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["closing_source"], "Prospeccao")
        self.assertEqual(response.context["form"].initial["niche"], self.niche)
        self.assertNotIn("total_value", response.context["form"].initial)

    def test_settings_page_lists_managed_dropdown_options(self):
        ServiceCategory.objects.create(workspace=self.workspace, name="Pacote premium")
        self.client.force_login(self.user)

        response = self.client.get(reverse("settings"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pacote premium")
        self.assertContains(response, "Tech")
        self.assertContains(response, "Viagem")
        self.assertNotContains(response, "Adicionar nicho")

    def test_profile_page_accepts_photo_upload_and_hides_slug_and_role(self):
        self.client.force_login(self.user)
        temp_media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_media_root, ignore_errors=True)
        buffer = BytesIO()
        Image.new("RGBA", (1600, 1200), (255, 0, 0, 255)).save(buffer, format="PNG")
        image_file = SimpleUploadedFile("avatar.png", buffer.getvalue(), content_type="image/png")

        with self.settings(MEDIA_ROOT=temp_media_root):
            response = self.client.post(reverse("profile"), {"photo": image_file}, follow=True)

            self.assertRedirects(response, reverse("profile"))
            membership = Membership.objects.get(user=self.user, workspace=self.workspace)
            self.assertTrue(membership.avatar.name.startswith("ugc_fotos/"))
            self.assertTrue(membership.avatar.name.endswith(".jpg"))
            self.assertContains(response, membership.avatar.url)
            self.assertNotContains(response, "data:image/")
            with Image.open(membership.avatar.path) as stored_image:
                self.assertEqual(stored_image.format, "JPEG")
                self.assertLessEqual(stored_image.width, 1080)
                self.assertLessEqual(stored_image.height, 1080)

        self.assertNotContains(response, "Slug")
        self.assertNotContains(response, "Perfil de acesso")

    def test_profile_page_updates_business_data(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("profile"),
            {
                "profile_action": "business",
                "business_full_name": "Layfe Amorim",
                "business_zip_code": "41810-205",
                "business_street": "Rua das Palmeiras",
                "business_number": "100",
                "business_complement": "Sala 04",
                "business_cnpj": "12.345.678/0001-99",
                "business_pis": "123.45678.90-1",
                "instagram_url": "https://instagram.com/trivexugc",
                "tiktok_url": "https://tiktok.com/@trivexugc",
                "portfolio_url": "https://portfolio.trivex.com",
            },
            follow=True,
        )

        self.assertRedirects(response, reverse("profile"))
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.business_full_name, "Layfe Amorim")
        self.assertEqual(self.workspace.business_zip_code, "41810-205")
        self.assertEqual(self.workspace.business_street, "Rua das Palmeiras")
        self.assertEqual(self.workspace.business_number, "100")
        self.assertEqual(self.workspace.business_complement, "Sala 04")
        self.assertEqual(self.workspace.business_cnpj, "12.345.678/0001-99")
        self.assertEqual(self.workspace.business_pis, "123.45678.90-1")
        self.assertEqual(self.workspace.instagram_url, "https://instagram.com/trivexugc")
        self.assertContains(response, "Dados empresariais atualizados.")

    @patch("studio.views.urlopen")
    def test_profile_zip_lookup_returns_street_from_api_brasil_payload(self, mocked_urlopen):
        self.client.force_login(self.user)
        mocked_urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"result": {"cep": "41810-205", "logradouro": "Rua das Palmeiras"}}'
        )

        with self.settings(
            APIBRASIL_CEP_URL="https://api.apibrasil.example/cep/{cep}",
            APIBRASIL_CEP_TOKEN="token-teste",
        ):
            response = self.client.post(reverse("business_zip_lookup"), {"cep": "41810205"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "ok": True,
                "zip_code": "41810-205",
                "street": "Rua das Palmeiras",
            },
        )

    def test_profile_avatar_file_is_served_by_media_url(self):
        self.client.force_login(self.user)
        temp_media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_media_root, ignore_errors=True)
        buffer = BytesIO()
        Image.new("RGBA", (900, 900), (0, 80, 255, 255)).save(buffer, format="PNG")
        image_file = SimpleUploadedFile("avatar-producao.png", buffer.getvalue(), content_type="image/png")

        with self.settings(MEDIA_ROOT=temp_media_root, DEBUG=False):
            self.client.post(reverse("profile"), {"photo": image_file}, follow=True)
            membership = Membership.objects.get(user=self.user, workspace=self.workspace)

            media_response = self.client.get(membership.avatar.url)

        self.assertEqual(media_response.status_code, 200)
        self.assertEqual(media_response["Content-Type"], "image/jpeg")
        self.assertIn("max-age=86400", media_response["Cache-Control"])
        streamed_content = b"".join(media_response.streaming_content)
        self.assertGreater(len(streamed_content), 0)

    def test_profile_and_settings_pages_show_internal_navigation(self):
        self.client.force_login(self.user)

        profile_response = self.client.get(reverse("profile"))
        settings_response = self.client.get(reverse("settings"))

        self.assertContains(profile_response, reverse("profile"))
        self.assertContains(profile_response, reverse("settings"))
        self.assertContains(profile_response, "profile-nav-link active")
        self.assertContains(settings_response, reverse("profile"))
        self.assertContains(settings_response, reverse("settings"))
        self.assertContains(settings_response, "profile-nav-link active")


class AuthenticationFlowsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="creatorhub",
            email="creatorhub@example.com",
            password="SenhaSegura123!",
        )

    def test_login_accepts_email_and_persists_session_after_redirect(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": "SenhaSegura123!"},
        )

        self.assertRedirects(response, reverse("dashboard"))

        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))

    def test_password_reset_sends_email_and_allows_setting_new_password(self):
        response = self.client.post(reverse("password_reset"), {"email": self.user.email})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        reset_email = mail.outbox[0]
        self.assertIn("Redefina sua senha no The Creators Club", reset_email.subject)

        match = re.search(r"http://testserver(?P<path>/\S+)", reset_email.body)
        self.assertIsNotNone(match)
        reset_path = match.group("path")

        confirm_response = self.client.get(reset_path, follow=True)
        self.assertEqual(confirm_response.status_code, 200)

        final_reset_path = confirm_response.request["PATH_INFO"]
        complete_response = self.client.post(
            final_reset_path,
            {"new_password1": "NovaSenhaSegura456!", "new_password2": "NovaSenhaSegura456!"},
            follow=True,
        )

        self.assertRedirects(complete_response, reverse("password_reset_complete"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NovaSenhaSegura456!"))

        login_response = self.client.post(
            reverse("login"),
            {"username": self.user.email, "password": "NovaSenhaSegura456!"},
        )
        self.assertRedirects(login_response, reverse("dashboard"))

    def test_password_reset_does_not_send_email_for_inactive_user(self):
        inactive_user = User.objects.create_user(
            username="inativo",
            email="inativo@example.com",
            password="SenhaSegura123!",
            is_active=False,
        )

        response = self.client.post(reverse("password_reset"), {"email": inactive_user.email})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_login_does_not_require_code_for_account_without_bound_code(self):
        new_user = User.objects.create_user(
            username="semcodigo",
            email="semcodigo@example.com",
            password="SenhaSegura123!",
        )

        login_response = self.client.post(
            reverse("login"),
            {"username": new_user.email, "password": "SenhaSegura123!"},
        )
        self.assertRedirects(login_response, reverse("dashboard"))

    def test_signup_requires_unused_access_code_and_binds_it_to_new_user(self):
        signup_code = AccessCode.objects.create(code="TCC-P-SIGN001", audience=AccessCode.AUDIENCE_PAID)

        response = self.client.post(
            reverse("signup"),
            {
                "full_name": "Layfe Amorim",
                "username": "novocriador",
                "email": "novocriador@example.com",
                "workspace_name": "Studio Novo",
                "access_code": signup_code.code.lower(),
                "password1": "SenhaSegura123!",
                "password2": "SenhaSegura123!",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        signup_code.refresh_from_db()
        self.assertIsNotNone(signup_code.assigned_user)
        self.assertEqual(signup_code.assigned_user.username, "novocriador")
        self.assertEqual(signup_code.assigned_user.get_full_name(), "Layfe Amorim")
        self.assertEqual(signup_code.assigned_user.memberships.first().workspace.business_full_name, "Layfe Amorim")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Seu cadastro foi feito no The Creators Club", mail.outbox[0].subject)
        self.assertIn("/login/", mail.outbox[0].body)

    def test_generate_access_codes_command_creates_paid_and_non_paid_codes(self):
        call_command("generate_access_codes", paid=2, non_paid=3, prefix="CLUB", length=6)

        self.assertEqual(AccessCode.objects.filter(audience=AccessCode.AUDIENCE_PAID).count(), 2)
        self.assertEqual(AccessCode.objects.filter(audience=AccessCode.AUDIENCE_NON_PAID).count(), 3)

    def test_benchmark_workspace_command_prints_metrics(self):
        workspace = get_or_create_workspace_for_user(self.user)
        output = StringIO()

        call_command("benchmark_workspace", workspace=workspace.slug, repeat=1, stdout=output)

        content = output.getvalue()
        self.assertIn(f"Workspace: {workspace.name} ({workspace.slug})", content)
        self.assertIn("dashboard_snapshot:", content)
        self.assertIn("prospection_snapshot:", content)
        self.assertIn("jobs_snapshot_filtered:", content)
        self.assertIn("finance_snapshot:", content)
        self.assertIn("reports_snapshot:", content)

    def test_benchmark_workspace_command_requires_identifier(self):
        with self.assertRaises(CommandError):
            call_command("benchmark_workspace")

    def test_second_login_invalidates_previous_session(self):
        first_client = Client()
        second_client = Client()

        first_response = first_client.post(
            reverse("login"),
            {"username": self.user.email, "password": "SenhaSegura123!"},
        )
        self.assertRedirects(first_response, reverse("dashboard"))
        first_session_key = first_client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=first_session_key).exists())

        second_response = second_client.post(
            reverse("login"),
            {"username": self.user.email, "password": "SenhaSegura123!"},
        )
        self.assertRedirects(second_response, reverse("dashboard"))
        second_session_key = second_client.session.session_key

        self.assertNotEqual(first_session_key, second_session_key)
        self.assertFalse(Session.objects.filter(session_key=first_session_key).exists())
        self.assertTrue(Session.objects.filter(session_key=second_session_key).exists())
        self.assertEqual(
            ActiveUserSession.objects.get(user=self.user).session_key,
            second_session_key,
        )

        old_session_response = first_client.get(reverse("dashboard"))
        self.assertEqual(old_session_response.status_code, 302)
        self.assertIn(reverse("login"), old_session_response["Location"])

    def test_layfeamorim_allows_multiple_active_sessions(self):
        privileged_user = User.objects.create_user(
            username="layfeamorim",
            email="layfeamorim@example.com",
            password="SenhaSegura123!",
        )
        get_or_create_workspace_for_user(privileged_user)
        first_client = Client()
        second_client = Client()

        first_response = first_client.post(
            reverse("login"),
            {"username": privileged_user.username, "password": "SenhaSegura123!"},
        )
        self.assertRedirects(first_response, reverse("dashboard"))
        first_session_key = first_client.session.session_key
        self.assertTrue(Session.objects.filter(session_key=first_session_key).exists())

        second_response = second_client.post(
            reverse("login"),
            {"username": privileged_user.username, "password": "SenhaSegura123!"},
        )
        self.assertRedirects(second_response, reverse("dashboard"))
        second_session_key = second_client.session.session_key

        self.assertNotEqual(first_session_key, second_session_key)
        self.assertTrue(Session.objects.filter(session_key=first_session_key).exists())
        self.assertTrue(Session.objects.filter(session_key=second_session_key).exists())
        self.assertFalse(ActiveUserSession.objects.filter(user=privileged_user).exists())

        first_dashboard = first_client.get(reverse("dashboard"))
        second_dashboard = second_client.get(reverse("dashboard"))
        self.assertEqual(first_dashboard.status_code, 200)
        self.assertEqual(second_dashboard.status_code, 200)


