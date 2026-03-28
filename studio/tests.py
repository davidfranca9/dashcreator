import re
from datetime import date, timedelta

from django.contrib.sessions.models import Session
from django.core import mail
from django.core.management import call_command
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from .forms import ProjectForm, ProspectForm
from .models import AccessCode, ActiveUserSession, Membership, Niche, Project, Prospect, ServiceCategory
from .services import dashboard_snapshot, get_or_create_workspace_for_user, jobs_snapshot, shell_context


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
        for name in ["dashboard", "prospection", "jobs", "finance", "reports", "settings", "profile"]:
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
        self.assertContains(response, "Follow-up")
        self.assertContains(response, "Ja tem 40 dias desde o seu ultimo trabalho para a marca Reserva")
        self.assertContains(response, "oi sumido?")

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
        self.assertContains(response, 'href="#follow-up-column"', html=False)
        self.assertContains(response, "Nunca mais lembrar da marca Reserva")

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
        self.assertEqual(
            form.fields["closing_source"].choices,
            [
                ("", "Selecione"),
                ("Inbound", "Inbound"),
                ("Prospeccao", "Prospecção"),
                ("Plataforma", "Plataforma"),
                ("Agencia", "Agencia"),
                ("Indicacao", "Indicacao"),
            ],
        )
        self.assertNotIn("progress", form.fields)

    def test_project_form_syncs_stage_with_status(self):
        delivered_form = ProjectForm(
            data={
                "company": "Insider",
                "closing_source": "Indicacao",
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
            company="O Boticário!!!",
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
        self.assertEqual(list(legend.keys()), ["Inbound", "Prospecção", "Indicação", "Plataforma", "Agência"])
        self.assertEqual(legend["Inbound"]["count"], 1)
        self.assertEqual(legend["Prospecção"]["count"], 1)
        self.assertEqual(legend["Indicação"]["count"], 1)
        self.assertEqual(legend["Plataforma"]["count"], 1)
        self.assertEqual(legend["Agência"]["count"], 1)

    def test_shell_context_applies_dark_theme_class_from_workspace_settings(self):
        self.workspace.settings.update_or_create(
            key="ui_dark_theme",
            defaults={"value": "1"},
        )

        context = shell_context("dashboard", self.workspace, "Dashboard", "Resumo", user=self.user)

        self.assertEqual(context["theme_class"], "theme-dark")
        self.assertEqual(context["workspace_membership"].user, self.user)

    def test_finance_page_filters_month_detail_by_due_date(self):
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
        self.assertEqual(response.context["stats"][0]["value"], "R$2.400")
        self.assertEqual(response.context["stats"][1]["value"], "R$1.600")
        self.assertEqual(response.context["stats"][2]["value"], "R$800")
        self.assertEqual(response.context["stats"][3]["value"], "10 dias")
        self.assertEqual(len(response.context["schedule"]), 1)

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
        self.assertEqual(response.context["stats"][2]["value"], "Indicacao")
        self.assertEqual(response.context["stats"][3]["value"], "Beleza")
        self.assertEqual(response.context["via_breakdown"][0]["amount_text"], "50%")
        self.assertEqual(response.context["source_mix"]["total"], 2)
        self.assertContains(response, "Via de fechamento")

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
        image_file = SimpleUploadedFile(
            "avatar.png",
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\rIDATx\x9cc`\x00\x01\x00\x00\x05\x00\x01"
                b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
            content_type="image/png",
        )

        response = self.client.post(reverse("profile"), {"photo": image_file}, follow=True)

        self.assertRedirects(response, reverse("profile"))
        membership = Membership.objects.get(user=self.user, workspace=self.workspace)
        self.assertTrue(membership.avatar_data.startswith("data:image/png;base64,"))
        self.assertNotContains(response, "Slug")
        self.assertNotContains(response, "Perfil de acesso")

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
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Seu cadastro foi feito no The Creators Club", mail.outbox[0].subject)
        self.assertIn("/login/", mail.outbox[0].body)

    def test_generate_access_codes_command_creates_paid_and_non_paid_codes(self):
        call_command("generate_access_codes", paid=2, non_paid=3, prefix="CLUB", length=6)

        self.assertEqual(AccessCode.objects.filter(audience=AccessCode.AUDIENCE_PAID).count(), 2)
        self.assertEqual(AccessCode.objects.filter(audience=AccessCode.AUDIENCE_NON_PAID).count(), 3)

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
