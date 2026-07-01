"""Sistema de métricas de cliques/visitas nas landing pages.

- track(): endpoint público que recebe eventos das páginas estáticas (via sendBeacon).
- metrics_dashboard(): painel protegido (só staff) com gráficos e rankings por site.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse, JsonResponse
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


@user_passes_test(lambda u: u.is_authenticated and u.is_staff)
def metrics_dashboard(request: HttpRequest) -> HttpResponse:
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
    }
    return render(request, "studio/metrics.html", context)
