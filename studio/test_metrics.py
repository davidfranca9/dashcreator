from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse

from .models import PageEvent


class MetricsTests(TestCase):
    def test_track_creates_event(self):
        c = Client()
        payload = {"site": "layfe", "kind": "click", "label": "sou-marca", "path": "/", "visitor": "v1", "session": "s1"}
        resp = c.post(reverse("track"), data=json.dumps(payload), content_type="text/plain")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(PageEvent.objects.filter(site="layfe", kind="click", label="sou-marca").count(), 1)

    def test_track_rejects_invalid_site(self):
        c = Client()
        resp = c.post(reverse("track"), data=json.dumps({"site": "hacker", "kind": "pageview"}), content_type="text/plain")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(PageEvent.objects.count(), 0)

    def test_track_ignores_bots(self):
        c = Client(HTTP_USER_AGENT="Googlebot/2.1")
        c.post(reverse("track"), data=json.dumps({"site": "layfe", "kind": "pageview"}), content_type="text/plain")
        self.assertEqual(PageEvent.objects.count(), 0)

    def test_dashboard_requires_staff(self):
        resp = Client().get(reverse("metrics_dashboard"))
        self.assertEqual(resp.status_code, 302)  # anônimo → redireciona pro login

    def test_dashboard_non_staff_forbidden(self):
        User = get_user_model()
        User.objects.create_user("creator", password="x", is_staff=False)
        c = Client()
        c.login(username="creator", password="x")
        resp = c.get(reverse("metrics_dashboard"))
        self.assertEqual(resp.status_code, 403)  # logado sem permissão → 403 (sem loop)

    def test_dashboard_renders_with_and_without_data(self):
        User = get_user_model()
        User.objects.create_user("boss", password="x", is_staff=True)
        c = Client()
        c.login(username="boss", password="x")

        # vazio
        resp = c.get(reverse("metrics_dashboard") + "?site=tcc")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ainda sem dados")

        # com dados
        PageEvent.objects.create(site="tcc", kind="pageview", path="/", visitor="a")
        PageEvent.objects.create(site="tcc", kind="pageview", path="/", visitor="b")
        PageEvent.objects.create(site="tcc", kind="click", label="quero-fazer-parte", visitor="a")
        resp = c.get(reverse("metrics_dashboard") + "?site=tcc&days=30")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "quero-fazer-parte")
        self.assertContains(resp, "Visitas por dia")


class ReportsRedesignTests(TestCase):
    def setUp(self):
        from datetime import date
        from studio.services import get_or_create_workspace_for_user
        from studio.models import Project, Prospect, Niche, ServiceCategory
        User = get_user_model()
        self.user = User.objects.create_user("boss2", password="x", is_staff=True)
        self.workspace = get_or_create_workspace_for_user(self.user)
        niche = Niche.objects.create(workspace=self.workspace, name="Tech")
        category = ServiceCategory.objects.create(workspace=self.workspace, name="Consultoria de Marketing")
        Project.objects.create(
            workspace=self.workspace, company="Marca X", closing_source="Inbound",
            niche=niche, service_category=category, service_type="consultoria_marketing",
            project_name="Consultoria", content_type="", stage="Fechado", status="Briefing",
            total_value=3500, monthly_value=0, entry_value=0, received_value=0,
            deliverables_count=1, progress=0, close_date=date.today(), due_date=date.today(),
        )
        Project.objects.create(
            workspace=self.workspace, company="Marca Y", closing_source="Inbound",
            niche=niche, service_category=category, service_type="ugc_creator",
            project_name="UGC", content_type="", stage="Fechado", status="Briefing",
            total_value=460, monthly_value=0, entry_value=0, received_value=0,
            deliverables_count=1, progress=0, close_date=date.today(), due_date=date.today(),
        )
        Prospect.objects.create(workspace=self.workspace, company="Lead A", contact="@a", stage="Prospecção", contact_date=date.today())

    def test_snapshot_has_narrative(self):
        from studio.services import reports_snapshot
        snap = reports_snapshot(self.workspace, None)
        self.assertIn("strategic_reading", snap)
        self.assertIn("next_steps", snap)
        self.assertTrue(snap["strategic_reading"]["has_data"])
        self.assertTrue(len(snap["next_steps"]) >= 1)

    def test_reports_view_renders(self):
        c = Client(); c.login(username="boss2", password="x")
        resp = c.get(reverse("reports"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Leitura estratégica")
        self.assertContains(resp, "Próximos passos")
        self.assertContains(resp, "Evolução da prospecção")
        self.assertContains(resp, "Por tipo de serviço")
