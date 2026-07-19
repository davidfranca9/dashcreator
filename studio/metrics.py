"""Sistema de métricas de cliques/visitas nas landing pages.

- track(): endpoint público que recebe eventos das páginas estáticas (via sendBeacon).
- metrics_dashboard(): painel protegido (só staff) com gráficos e rankings por site.
"""

from __future__ import annotations

import json
from collections import Counter
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PageEvent

# Origens autorizadas a enviar eventos (os sites estáticos).
ALLOWED_TRACK_ORIGINS = {
    "https://layfeamorim.com",
    "https://www.layfeamorim.com",
    "https://thecreatorsclub.com.br",
    "https://www.thecreatorsclub.com.br",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}

VALID_SITES = {choice[0] for choice in PageEvent.SITE_CHOICES}
VALID_KINDS = {choice[0] for choice in PageEvent.KIND_CHOICES}
_BOT_MARKERS = ("bot", "spider", "crawl", "slurp", "headless", "preview", "monitor", "curl", "wget")

# ── Meta Ads ────────────────────────────────────────────────────────────────
# Identifica a visita como vinda do Meta (Facebook/Instagram) por três sinais:
# 1) fbclid na URL  — parâmetro que o próprio Meta adiciona ao clicar no anúncio
#    (sinal mais forte e automático);
# 2) utm_source=facebook/instagram/meta/fb — quando a campanha usa UTM;
# 3) referrer do facebook/instagram — tráfego vindo do app/site deles.
_META_FILTER = (
    Q(path__icontains="fbclid=")
    | Q(path__icontains="utm_source=facebook")
    | Q(path__icontains="utm_source=instagram")
    | Q(path__icontains="utm_source=meta")
    | Q(path__icontains="utm_source=fb&")
    | Q(referrer__icontains="facebook.com")
    | Q(referrer__icontains="instagram.com")
    | Q(referrer__icontains="fb.com")
)


def _utm_value(path: str, key: str) -> str:
    """Lê um parâmetro UTM do path gravado (o track.js salva pathname+search)."""
    if not path or "?" not in path:
        return ""
    try:
        return (parse_qs(urlparse(path).query).get(key) or [""])[0].strip()[:60]
    except (ValueError, TypeError):
        return ""


def _rank_by_utm(paths, key: str, fallback: str, limit: int = 10) -> list[dict]:
    counter = Counter(_utm_value(p, key) or fallback for p in paths)
    return [{"label": label, "n": n} for label, n in counter.most_common(limit)]


def _cors_headers(response: HttpResponse, origin: str) -> HttpResponse:
    if origin in ALLOWED_TRACK_ORIGINS:
        response["Access-Control-Allow-Origin"] = origin
    response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response["Access-Control-Allow-Headers"] = "Content-Type"
    response["Access-Control-Max-Age"] = "86400"
    response["Vary"] = "Origin"
    return response


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def track(request: HttpRequest) -> HttpResponse:
    origin = request.headers.get("Origin", "")

    if request.method == "OPTIONS":
        return _cors_headers(HttpResponse(status=204), origin)

    ua = request.headers.get("User-Agent", "")[:300]
    ua_lower = ua.lower()
    if any(marker in ua_lower for marker in _BOT_MARKERS):
        return _cors_headers(HttpResponse(status=204), origin)  # ignora bots silenciosamente

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return _cors_headers(HttpResponse(status=400), origin)

    site = str(payload.get("site", ""))[:20]
    kind = str(payload.get("kind", "pageview"))[:12]
    if site not in VALID_SITES or kind not in VALID_KINDS:
        return _cors_headers(HttpResponse(status=204), origin)

    PageEvent.objects.create(
        site=site,
        kind=kind,
        path=str(payload.get("path", ""))[:200],
        label=str(payload.get("label", ""))[:80],
        visitor=str(payload.get("visitor", ""))[:40],
        session=str(payload.get("session", ""))[:40],
        referrer=str(payload.get("referrer", ""))[:300],
        user_agent=ua,
    )
    return _cors_headers(HttpResponse(status=204), origin)


@login_required
def metrics_dashboard(request: HttpRequest) -> HttpResponse:
    # Autenticado mas sem permissão → 403 (evita loop de redirect com o login).
    if not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied("Acesso restrito às métricas.")

    site = request.GET.get("site", "layfe")
    if site not in VALID_SITES:
        site = "layfe"
    try:
        days = max(1, min(365, int(request.GET.get("days", 30))))
    except (TypeError, ValueError):
        days = 30

    since = timezone.now() - timezone.timedelta(days=days)
    base = PageEvent.objects.filter(site=site, created_at__gte=since)
    views = base.filter(kind="pageview")
    clicks = base.filter(kind="click")

    total_views = views.count()
    total_clicks = clicks.count()
    unique_visitors = views.values("visitor").distinct().count()

    # Série temporal de visitas por dia
    by_day = list(
        views.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )
    series_labels = [row["day"].strftime("%d/%m") for row in by_day]
    series_values = [row["n"] for row in by_day]

    # Rankings
    top_clicks = list(
        clicks.exclude(label="")
        .values("label")
        .annotate(n=Count("id"))
        .order_by("-n")[:15]
    )
    top_pages = list(
        views.values("path").annotate(n=Count("id")).order_by("-n")[:15]
    )

    max_click = top_clicks[0]["n"] if top_clicks else 0
    max_page = top_pages[0]["n"] if top_pages else 0

    # ── Painel Meta Ads ─────────────────────────────────────────────────────
    # Só o que dá pra saber pelo próprio site (o gasto/CPM fica no Gerenciador).
    meta_events = base.filter(_META_FILTER)
    meta_views_qs = meta_events.filter(kind="pageview")
    meta_views = meta_views_qs.count()
    meta_visitors = meta_views_qs.values("visitor").distinct().count()
    # Cliques contados por SESSÃO que entrou pelo Meta (mais fiel do que exigir
    # o fbclid na URL do clique, que se perde ao navegar).
    meta_sessions = meta_events.exclude(session="").values("session")
    meta_clicks = clicks.exclude(session="").filter(session__in=meta_sessions).count()
    meta_share = round(meta_views / total_views * 100) if total_views else 0
    meta_ctr = round(meta_clicks / meta_views * 100, 1) if meta_views else 0

    meta_paths = list(meta_views_qs.values_list("path", flat=True))
    meta_campaigns = _rank_by_utm(meta_paths, "utm_campaign", "(sem utm_campaign)")
    meta_creatives = _rank_by_utm(meta_paths, "utm_content", "(sem utm_content)")
    max_campaign = meta_campaigns[0]["n"] if meta_campaigns else 0
    max_creative = meta_creatives[0]["n"] if meta_creatives else 0

    meta_by_day = list(
        meta_views_qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )
    meta_day_map = {row["day"].strftime("%d/%m"): row["n"] for row in meta_by_day}
    meta_series_values = [meta_day_map.get(label, 0) for label in series_labels]

    context = {
        "site": site,
        "site_label": dict(PageEvent.SITE_CHOICES).get(site, site),
        "sites": PageEvent.SITE_CHOICES,
        "days": days,
        "total_views": total_views,
        "total_clicks": total_clicks,
        "unique_visitors": unique_visitors,
        "series_labels_json": json.dumps(series_labels),
        "series_values_json": json.dumps(series_values),
        "top_clicks": top_clicks,
        "top_pages": top_pages,
        "max_click": max_click,
        "max_page": max_page,
        "has_data": total_views > 0 or total_clicks > 0,
        # Meta Ads
        "meta_views": meta_views,
        "meta_visitors": meta_visitors,
        "meta_clicks": meta_clicks,
        "meta_share": meta_share,
        "meta_ctr": meta_ctr,
        "meta_campaigns": meta_campaigns,
        "meta_creatives": meta_creatives,
        "max_campaign": max_campaign,
        "max_creative": max_creative,
        "meta_series_values_json": json.dumps(meta_series_values),
        "has_meta": meta_views > 0,
    }
    return render(request, "studio/metrics.html", context)
