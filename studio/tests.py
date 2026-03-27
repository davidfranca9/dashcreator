import re
from datetime import date, timedelta

from django.contrib.sessions.models import Session
from django.core import mail
from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import AccessCode, ActiveUserSession, Project, Prospect
from .services import get_or_create_workspace_for_user


class DashboardSmokeTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        Prospect.objects.create(
            workspace=self.workspace,
            company="Nike",
            contact="Paula",
            stage="Prospeccao",
            proposal_value=1800,
            note="Primeiro contato",
            meeting_scheduled=True,
        )
        Project.objects.create(
            workspace=self.workspace,
            company="Shein",
            project_name="Pacote de videos",
            content_type="UGC Vertical",
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
        for name in ["dashboard", "prospection", "jobs", "finance", "reports", "settings"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)


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
