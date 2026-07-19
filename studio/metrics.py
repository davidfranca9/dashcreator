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

# ── Meta (Facebook / Instagram) ─────────────────────────────────────────────
# ATENÇÃO: isto identifica tráfego vindo do Meta em geral, inclui ORGÂNICO
# (link da bio, story, post, DM). O fbclid NÃO serve para separar anúncio:
# o Meta adiciona esse parâmetro em qualquer link clicado dentro dele.
# Para "pago" existe só um sinal confiável: a marcação de mídia paga que VOCÊ
# coloca no link do anúncio (utm_medium=paid). Ver _PAID_FILTER abaixo.
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


# Só conta como ANÚNCIO quando o link traz marcação de mídia paga. É o único
# sinal confiável: sem isso, é impossível distinguir clique em anúncio de
# clique no link da bio/story (ambos chegam com fbclid e referrer do Meta).
_PAID_FILTER = (
    Q(path__icontains="utm_medium=paid")
    | Q(path__icontains="utm_medium=cpc")
    | Q(path__icontains="utm_medium=ppc")
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


def _segment_stats(base, clicks, total_views, seg_filter, series_labels) -> dict:
    """Números de um recorte de tráfego (orgânico do Meta ou tráfego pago).

    Cliques são contados por SESSÃO que entrou pelo recorte, mais fiel do que
    exigir o parâmetro na URL do clique, que se perde ao navegar na página.
    """
    events = base.filter(seg_filter)
    views_qs = events.filter(kind="pageview")
    views = views_qs.count()
    sessions = events.exclude(session="").values("session")
    seg_clicks = clicks.exclude(session="").filter(session__in=sessions).count()
    paths = list(views_qs.values_list("path", flat=True))
    campaigns = _rank_by_utm(paths, "utm_campaign", "(sem utm_campaign)")
    creatives = _rank_by_utm(paths, "utm_content", "(sem utm_content)")
    by_day = {
        row["day"].strftime("%d/%m"): row["n"]
        for row in views_qs.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    }
    return {
        "views": views,
        "visitors": views_qs.values("visitor").distinct().count(),
        "clicks": seg_clicks,
        "share": round(views / total_views * 100) if total_views else 0,
        "ctr": round(seg_clicks / views * 100, 1) if views else 0,
        "campaigns": campaigns,
        "creatives": creatives,
        "max_campaign": campaigns[0]["n"] if campaigns else 0,
        "max_creative": creatives[0]["n"] if creatives else 0,
        "series": [by_day.get(label, 0) for label in series_labels],
        "has_data": views > 0,
    }


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

    # ── Dois recortes independentes: ORGÂNICO e TRÁFEGO PAGO ────────────────
    # Pago = link marcado com utm_medium=paid/cpc/ppc (único sinal confiável).
    # Orgânico = veio do Meta mas sem essa marcação (bio, story, post, DM).
    paid = _segment_stats(base, clicks, total_views, _META_FILTER & _PAID_FILTER, series_labels)
    organic = _segment_stats(base, clicks, total_views, _META_FILTER & ~_PAID_FILTER, series_labels)

    meta_views = paid["views"] + organic["views"]

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
        # Meta: dois painéis independentes
        "organic": organic,
        "paid": paid,
        "organic_series_json": json.dumps(organic["series"]),
        "paid_series_json": json.dumps(paid["series"]),
        # agregados (compatibilidade / visão geral)
        "meta_views": meta_views,
        "meta_paid_views": paid["views"],
        "meta_organic_views": organic["views"],
        "has_meta": meta_views > 0,
    }
    return render(request, "studio/metrics.html", context)
