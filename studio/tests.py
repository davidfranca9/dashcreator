from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Project, Prospect
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
