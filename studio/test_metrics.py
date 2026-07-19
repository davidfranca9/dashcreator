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


class PipelineIconsTest(TestCase):
    def test_prospection_renders_pipeline_icons(self):
        from studio.services import get_or_create_workspace_for_user
        User = get_user_model()
        u = User.objects.create_user("boss3", password="x", is_staff=True)
        get_or_create_workspace_for_user(u)
        c = Client(); c.login(username="boss3", password="x")
        resp = c.get(reverse("prospection"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("pipeline-kpi-icon", html)
        # deve ter pelo menos 6 <svg dentro dos icones (um por etapa)
        self.assertGreaterEqual(html.count('class="pipeline-kpi-icon'), 6)
        self.assertIn("<svg", html)


class MetaAdsPanelTests(TestCase):
    """Painel de Meta Ads no /metricas: identifica tráfego do Facebook/Instagram
    por fbclid, utm_source e referrer — sem precisar da API do Meta."""

    def setUp(self):
        get_user_model().objects.create_user("boss", password="x", is_staff=True)
        self.c = Client()
        self.c.login(username="boss", password="x")

    def _url(self):
        return reverse("metrics_dashboard") + "?site=dash&days=30"

    def test_detects_meta_traffic_by_fbclid_utm_and_referrer(self):
        # 3 visitas do Meta (uma por sinal) + 1 orgânica
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/?fbclid=ABC123", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/?utm_source=instagram&utm_campaign=lancamento", visitor="v2", session="s2")
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/", visitor="v3", session="s3", referrer="https://l.facebook.com/")
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/", visitor="v4", session="s4", referrer="https://google.com/")

        ctx = self.c.get(self._url()).context
        self.assertEqual(ctx["meta_views"], 3)
        self.assertEqual(ctx["meta_visitors"], 3)
        self.assertEqual(ctx["total_views"], 4)
        self.assertEqual(ctx["meta_share"], 75)
        self.assertTrue(ctx["has_meta"])

    def test_counts_cta_clicks_from_meta_sessions(self):
        # visita pelo Meta e depois clica no CTA (clique já sem o fbclid na URL)
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/?fbclid=X", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="click", label="cadastre-se", path="/dashcreator/", visitor="v1", session="s1")
        # visitante orgânico que também clica (não deve contar no Meta)
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/", visitor="v2", session="s2")
        PageEvent.objects.create(site="dash", kind="click", label="cadastre-se", path="/dashcreator/", visitor="v2", session="s2")

        ctx = self.c.get(self._url()).context
        self.assertEqual(ctx["meta_clicks"], 1)
        self.assertEqual(ctx["total_clicks"], 2)
        self.assertEqual(ctx["meta_ctr"], 100.0)

    def test_breaks_down_by_campaign_and_creative(self):
        PageEvent.objects.create(site="dash", kind="pageview", path="/d/?fbclid=1&utm_campaign=black&utm_content=video-a", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d/?fbclid=2&utm_campaign=black&utm_content=video-b", visitor="v2", session="s2")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d/?fbclid=3&utm_campaign=julho&utm_content=video-a", visitor="v3", session="s3")

        ctx = self.c.get(self._url()).context
        campaigns = {row["label"]: row["n"] for row in ctx["meta_campaigns"]}
        creatives = {row["label"]: row["n"] for row in ctx["meta_creatives"]}
        self.assertEqual(campaigns["black"], 2)
        self.assertEqual(campaigns["julho"], 1)
        self.assertEqual(creatives["video-a"], 2)

    def test_panel_renders_empty_state_without_meta_traffic(self):
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/", visitor="v1", session="s1")
        resp = self.c.get(self._url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Meta Ads")
        self.assertContains(resp, "Nenhuma visita do Meta ainda")
        self.assertFalse(resp.context["has_meta"])

    def test_organic_meta_traffic_is_not_counted_as_paid(self):
        """Link da bio / story / post chegam com fbclid e referrer do Meta, mas
        NÃO são anúncio. Só conta como pago quem tem utm_medium=paid."""
        # link da bio do Instagram (orgânico) — caso real que apareceu no painel
        PageEvent.objects.create(site="dash", kind="pageview", visitor="v1", session="s1",
                                 path="/dashcreator/?fbclid=AAA&utm_content=link_in_bio",
                                 referrer="https://l.instagram.com/")
        # story orgânico
        PageEvent.objects.create(site="dash", kind="pageview", visitor="v2", session="s2",
                                 path="/dashcreator/?fbclid=BBB", referrer="https://l.facebook.com/")
        # anúncio de verdade (link com marcação de mídia paga)
        PageEvent.objects.create(site="dash", kind="pageview", visitor="v3", session="s3",
                                 path="/dashcreator/?fbclid=CCC&utm_source=meta&utm_medium=paid&utm_campaign=julho")

        ctx = self.c.get(self._url()).context
        self.assertEqual(ctx["meta_views"], 3)          # os 3 vieram do Meta
        self.assertEqual(ctx["meta_paid_views"], 1)     # mas só 1 é anúncio
        self.assertEqual(ctx["meta_organic_views"], 2)  # bio + story = orgânico

    def test_no_ads_running_shows_zero_paid(self):
        """Cenário do usuário: nenhum anúncio rodando -> pago = 0."""
        for i in range(5):
            PageEvent.objects.create(site="dash", kind="pageview", visitor=f"v{i}", session=f"s{i}",
                                     path="/dashcreator/?fbclid=X&utm_content=link_in_bio",
                                     referrer="https://l.instagram.com/")
        ctx = self.c.get(self._url()).context
        self.assertEqual(ctx["meta_paid_views"], 0)
        self.assertEqual(ctx["meta_organic_views"], 5)
