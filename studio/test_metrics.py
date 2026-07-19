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
        self.assertContains(resp, "Quero fazer parte")
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
    """Dois painéis separados no /metricas: Orgânico (bio/story/post) e
    Tráfego pago (anúncio). Só conta como pago quando o link traz
    utm_medium=paid — fbclid e referrer do Meta aparecem no orgânico também."""

    def setUp(self):
        get_user_model().objects.create_user("boss", password="x", is_staff=True)
        self.c = Client()
        self.c.login(username="boss", password="x")

    def _resp(self):
        return self.c.get(reverse("metrics_dashboard") + "?site=dash&days=30")

    def test_detects_meta_traffic_by_fbclid_utm_and_referrer(self):
        PageEvent.objects.create(site="dash", kind="pageview", path="/d/?fbclid=ABC", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d/?utm_source=instagram", visitor="v2", session="s2")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d/", visitor="v3", session="s3", referrer="https://l.facebook.com/")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d/", visitor="v4", session="s4", referrer="https://google.com/")

        ctx = self._resp().context
        self.assertEqual(ctx["meta_views"], 3)   # 3 vieram do Meta
        self.assertEqual(ctx["total_views"], 4)  # o do Google não
        self.assertTrue(ctx["has_meta"])
        # nenhum traz utm_medium=paid -> tudo orgânico, nada de anúncio
        self.assertEqual(ctx["organic"]["views"], 3)
        self.assertEqual(ctx["paid"]["views"], 0)

    def test_organic_and_paid_do_not_mix(self):
        # bio do Instagram (orgânico) — caso real que apareceu no painel
        PageEvent.objects.create(site="dash", kind="pageview", visitor="v1", session="s1",
                                 path="/d/?fbclid=A&utm_content=link_in_bio", referrer="https://l.instagram.com/")
        # story (orgânico)
        PageEvent.objects.create(site="dash", kind="pageview", visitor="v2", session="s2",
                                 path="/d/?fbclid=B", referrer="https://l.facebook.com/")
        # anúncio de verdade (pago)
        PageEvent.objects.create(site="dash", kind="pageview", visitor="v3", session="s3",
                                 path="/d/?fbclid=C&utm_source=meta&utm_medium=paid&utm_campaign=julho&utm_content=video-a")

        ctx = self._resp().context
        self.assertEqual(ctx["organic"]["views"], 2)
        self.assertEqual(ctx["organic"]["visitors"], 2)
        self.assertEqual(ctx["paid"]["views"], 1)

        org_creatives = {r["raw"]: r["n"] for r in ctx["organic"]["creatives"]}
        paid_campaigns = {r["raw"]: r["n"] for r in ctx["paid"]["campaigns"]}
        self.assertEqual(org_creatives["link_in_bio"], 1)
        self.assertEqual(paid_campaigns["julho"], 1)
        # a campanha do anúncio NÃO pode vazar pro painel orgânico
        self.assertNotIn("julho", {r["raw"] for r in ctx["organic"]["campaigns"]})
        # e o nome exibido é o legível
        self.assertIn("Link na bio", {r["label"] for r in ctx["organic"]["creatives"]})

    def test_clicks_counted_per_segment(self):
        # orgânico: entra pela bio e clica no CTA (clique já sem parâmetro)
        PageEvent.objects.create(site="dash", kind="pageview", visitor="v1", session="s1",
                                 path="/d/?fbclid=A", referrer="https://l.instagram.com/")
        PageEvent.objects.create(site="dash", kind="click", label="cadastre-se", visitor="v1", session="s1", path="/d/")
        # pago: entra por anúncio e clica
        PageEvent.objects.create(site="dash", kind="pageview", visitor="v2", session="s2",
                                 path="/d/?utm_source=meta&utm_medium=paid")
        PageEvent.objects.create(site="dash", kind="click", label="cadastre-se", visitor="v2", session="s2", path="/d/")

        ctx = self._resp().context
        self.assertEqual(ctx["organic"]["clicks"], 1)
        self.assertEqual(ctx["paid"]["clicks"], 1)
        self.assertEqual(ctx["organic"]["ctr"], 100.0)

    def test_no_ads_running_shows_empty_paid_panel(self):
        """Cenário do usuário: só tráfego da bio, nenhum anúncio rodando."""
        for i in range(5):
            PageEvent.objects.create(site="dash", kind="pageview", visitor=f"v{i}", session=f"s{i}",
                                     path="/d/?fbclid=X&utm_content=link_in_bio", referrer="https://l.instagram.com/")
        resp = self._resp()
        self.assertEqual(resp.context["organic"]["views"], 5)
        self.assertEqual(resp.context["paid"]["views"], 0)
        self.assertFalse(resp.context["paid"]["has_data"])
        self.assertContains(resp, "Orgânico · Facebook / Instagram")
        self.assertContains(resp, "Nenhum anúncio rodando")


class PrettyLabelTests(TestCase):
    """Tradução dos rótulos técnicos para nomes que a pessoa entende."""

    def test_known_labels(self):
        from studio.metrics import _pretty_label
        self.assertEqual(_pretty_label("fazer-parte-header"), "Quero fazer parte (topo)")
        self.assertEqual(_pretty_label("quero-acompanhamento"), "Quero acompanhamento")
        self.assertEqual(_pretty_label("conhecer-dash"), "Conhecer o Dash")
        self.assertEqual(_pretty_label("link_in_bio"), "Link na bio")
        self.assertEqual(_pretty_label("ver-portfolio"), "Ver portfólio")

    def test_unknown_label_falls_back_readable(self):
        from studio.metrics import _pretty_label
        self.assertEqual(_pretty_label("botao-novo-qualquer"), "Botao novo qualquer")
        self.assertEqual(_pretty_label("promo_verao"), "Promo verao")
        # sufixo de posição vira parênteses
        self.assertEqual(_pretty_label("assinar-footer"), "Assinar (rodapé)")

    def test_placeholders_and_empty(self):
        from studio.metrics import _pretty_label
        self.assertEqual(_pretty_label("(sem utm_content)"), "Origem não identificada")
        self.assertEqual(_pretty_label("(sem utm_campaign)"), "Sem campanha marcada")
        self.assertEqual(_pretty_label(""), "Sem identificação")


class StoriesPanelTests(TestCase):
    """Painel de stories: identifica perfil e story pela #tag do link."""

    def setUp(self):
        get_user_model().objects.create_user("boss", password="x", is_staff=True)
        self.c = Client()
        self.c.login(username="boss", password="x")

    def _ctx(self):
        return self.c.get(reverse("metrics_dashboard") + "?site=dash&days=30").context

    def test_tag_parsing(self):
        from studio.metrics import _story_tag
        self.assertEqual(_story_tag("/dashcreator#layfe"), ("layfe", ""))
        self.assertEqual(_story_tag("/dashcreator#layfe.bastidores"), ("layfe", "bastidores"))
        self.assertEqual(_story_tag("/dashcreator?x=1#tcc.promo"), ("tcc", "promo"))
        # ancora de secao da propria pagina NAO e story
        self.assertIsNone(_story_tag("/dashcreator#modulos"))
        self.assertIsNone(_story_tag("/dashcreator#top"))
        self.assertIsNone(_story_tag("/dashcreator"))

    def test_separates_by_profile_and_story(self):
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#layfe.promo", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#layfe.promo", visitor="v2", session="s2")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#tcc.bastidores", visitor="v3", session="s3")
        # visita normal e ancora de secao nao entram
        PageEvent.objects.create(site="dash", kind="pageview", path="/d", visitor="v4", session="s4")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#modulos", visitor="v5", session="s5")

        st = self._ctx()["stories"]
        self.assertEqual(st["views"], 3)
        profiles = {r["raw"]: r["n"] for r in st["profiles"]}
        self.assertEqual(profiles["layfe"], 2)
        self.assertEqual(profiles["tcc"], 1)
        names = {r["label"] for r in st["stories"]}
        self.assertIn("@layfeamorim · promo", names)
        self.assertIn("@thecreatorssclubb · bastidores", names)

    def test_without_story_name_groups_by_day(self):
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#layfe", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#layfe", visitor="v2", session="s2")
        st = self._ctx()["stories"]
        self.assertEqual(st["views"], 2)
        # vira "layfe · dd/mm"
        self.assertTrue(any(r["label"].startswith("@layfeamorim · ") for r in st["stories"]))

    def test_counts_cta_clicks_from_story_sessions(self):
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#layfe", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="click", label="cadastre-se", path="/d", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d", visitor="v2", session="s2")
        PageEvent.objects.create(site="dash", kind="click", label="cadastre-se", path="/d", visitor="v2", session="s2")
        st = self._ctx()["stories"]
        self.assertEqual(st["clicks"], 1)
        self.assertEqual(st["ctr"], 100.0)

    def test_page_ranking_ignores_query_and_tag(self):
        """Paginas mais vistas agrupa pela pagina limpa."""
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/#layfe", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/?fbclid=X", visitor="v2", session="s2")
        PageEvent.objects.create(site="dash", kind="pageview", path="/dashcreator/", visitor="v3", session="s3")
        pages = {r["path"]: r["n"] for r in self._ctx()["top_pages"]}
        self.assertEqual(pages["/dashcreator/"], 3)

    def test_fixed_profile_registry(self):
        """Tags sao fixas: cada perfil tem a sua, e tag fora da lista
        aparece marcada como nao cadastrada (em vez de sumir)."""
        from studio.metrics import _profile_name, INSTAGRAM_PROFILES
        self.assertIn("layfe", INSTAGRAM_PROFILES)
        self.assertEqual(_profile_name("layfe"), "@layfeamorim")
        self.assertEqual(_profile_name("tcc"), "@thecreatorssclubb")
        self.assertIn("não cadastrada", _profile_name("layfee"))  # erro de digitacao

    def test_registered_profile_shows_handle(self):
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#layfe", visitor="v1", session="s1")
        PageEvent.objects.create(site="dash", kind="pageview", path="/d#layfee", visitor="v2", session="s2")
        st = self._ctx()["stories"]
        labels = {r["label"] for r in st["profiles"]}
        self.assertIn("@layfeamorim", labels)
        # a tag errada nao se mistura com a certa e fica visivel pra correcao
        self.assertTrue(any("não cadastrada" in l for l in labels))

    def test_tag_guide_lists_ready_links(self):
        PageEvent.objects.create(site="dash", kind="pageview", path="/d", visitor="v1", session="s1")
        resp = self.c.get(reverse("metrics_dashboard") + "?site=dash&days=30")
        guide = resp.context["stories"]["tag_guide"]
        urls = {g["tag"]: g["url"] for g in guide}
        self.assertEqual(urls["layfe"], "thecreatorsclub.com.br/dashcreator#layfe")
        self.assertContains(resp, "Suas tags fixas")
