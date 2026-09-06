"""Sistema de métricas de cliques/visitas nas landing pages.

- track(): endpoint público que recebe eventos das páginas estáticas (via sendBeacon).
- metrics_dashboard(): painel protegido (só staff) com gráficos e rankings por site.
"""

from __future__ import annotations

import json
from collections import Counter
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PageEvent, Prospect

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


# Nomes legíveis para os rótulos técnicos gravados pelo tracking. O que não
# estiver aqui cai no fallback (troca traço/underline por espaço e capitaliza).
_FRIENDLY_LABELS = {
    # botões dos sites (data-track)
    "a-comunidade": "A comunidade",
    "cadastre-se": "Cadastre-se",
    "conhecer-dash": "Conhecer o Dash",
    "conhecer-planner": "Conhecer o Planner",
    "fazer-parte-header": "Quero fazer parte (topo)",
    "fazer-parte-hero": "Quero fazer parte (destaque)",
    "login": "Login",
    "quero-acompanhamento": "Quero acompanhamento",
    "sou-creator": "Sou creator",
    "sou-marca": "Sou marca",
    "ver-portfolio": "Ver portfólio",
    "whatsapp-marca": "WhatsApp da marca",
    # fluxo "Sou marca" (layfeamorim.com)
    "marca-quero-social": "Marca · Quero social",
    "marca-enviou-social": "Marca · ENVIOU o formulário social",
    "marca-enviar-proposta": "Marca · Enviar proposta por e-mail",
    # fluxo "Sou creator" (layfeamorim.com)
    "creator-lista-espera": "Creator · Abriu lista de espera",
    "creator-enviou-lista": "Creator · ENTROU na lista de espera",
    "creator-ver-cronograma": "Creator · Ver cronograma da mentoria",
    "creator-conhecer-app": "Creator · Conhecer o app",
    "creator-ver-planner": "Creator · Ver planner",
    "creator-conhecer-clube": "Creator · Conhecer o clube",
    # origens (utm_content)
    "link_in_bio": "Link na bio",
    "link-in-bio": "Link na bio",
    "linkinbio": "Link na bio",
    "bio": "Link na bio",
    "stories": "Stories",
    "story": "Stories",
    "post": "Post no feed",
    "reels": "Reels",
    "whatsapp": "WhatsApp",
}
# Sufixos que indicam ONDE na página estava o botão.
_POSITION_SUFFIX = {"header": "topo", "hero": "destaque", "footer": "rodapé", "final": "final", "menu": "menu"}
_PLACEHOLDER_LABELS = {
    "(sem utm_campaign)": "Sem campanha marcada",
    "(sem utm_content)": "Origem não identificada",
}


def _pretty_label(raw: str) -> str:
    """Converte o rótulo técnico ('fazer-parte-header') no nome que a pessoa
    entende ('Quero fazer parte (topo)')."""
    value = (raw or "").strip()
    if not value:
        return "Sem identificação"
    if value in _PLACEHOLDER_LABELS:
        return _PLACEHOLDER_LABELS[value]
    key = value.lower()
    if key in _FRIENDLY_LABELS:
        return _FRIENDLY_LABELS[key]
    parts = [p for p in key.replace("_", "-").split("-") if p]
    if not parts:
        return value
    suffix = ""
    if len(parts) > 1 and parts[-1] in _POSITION_SUFFIX:
        suffix = f" ({_POSITION_SUFFIX[parts.pop()]})"
    text = " ".join(parts)
    return text[:1].upper() + text[1:] + suffix


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
    return [
        {"label": _pretty_label(label), "raw": label, "n": n}
        for label, n in counter.most_common(limit)
    ]


# ── Stories do Instagram (#tag no link) ─────────────────────────────────────
# A pessoa põe no sticker de link do story uma URL terminada em #tag, ex.:
#   thecreatorsclub.com.br/dashcreator#layfe          (só o perfil)
#   thecreatorsclub.com.br/dashcreator#layfe.promo    (perfil + nome do story)
# Sem o nome do story, o painel separa por DIA, então cada story aparece
# sozinho mesmo sem inventar um nome novo a cada post.
#
# Âncoras de seção das próprias páginas NÃO podem virar tag de story.
_PAGE_ANCHORS = {
    "top", "modulos", "comunidade", "manifesto", "caminhos", "galeria",
    "organicos", "vendas", "arc-b", "arc-t", "cta", "depoimentos", "filosofia",
    "founder", "plano", "planos", "porque", "problema", "faq", "inicio",
}


# Registro FIXO de tags: uma tag por perfil do Instagram. Só o que estiver
# aqui é considerado perfil conhecido. Tag fora da lista continua sendo
# contada, porém marcada como "não cadastrada", para você notar erro de
# digitação em vez de perder a visita silenciosamente.
INSTAGRAM_PROFILES = {
    "layfe": "@layfeamorim",
    "tcc": "@thecreatorssclubb",
    "dash": "@dashhcreator_",
}

# Endereço base de cada site, usado para montar o link pronto de cada perfil.
SITE_BASE_URL = {
    "layfe": "layfeamorim.com",
    "tcc": "thecreatorsclub.com.br",
    "dash": "thecreatorsclub.com.br/dashcreator",
    "portfolio": "layfeamorim.com/portfolio",
}


def _profile_name(tag: str) -> str:
    """Nome de exibição do perfil a partir da tag fixa."""
    return INSTAGRAM_PROFILES.get(tag, f"#{tag} (não cadastrada)")


def _story_tag(path: str) -> tuple[str, str] | None:
    """Extrai (perfil, story) do #tag do link. None quando não há tag ou
    quando é âncora de seção da própria página."""
    if not path or "#" not in path:
        return None
    fragment = path.split("#", 1)[1].strip().lower()
    if not fragment or fragment in _PAGE_ANCHORS or fragment.startswith("_"):
        return None
    profile, _, story = fragment.partition(".")
    profile = profile.strip()[:40]
    if not profile:
        return None
    return profile, story.strip()[:40]


def _stories_stats(base, clicks, total_views) -> dict:
    """Visitas vindas de story, quebradas por perfil e por story."""
    rows = [
        (path, created_at, session)
        for path, created_at, session in base.filter(kind="pageview").values_list(
            "path", "created_at", "session"
        )
        if _story_tag(path)
    ]
    views = len(rows)
    by_profile = Counter()
    by_story = Counter()
    for path, created_at, _session in rows:
        profile, story = _story_tag(path)
        by_profile[profile] += 1
        # sem nome de story, separa por dia (cada post vira uma linha)
        nome = _profile_name(profile)
        key = f"{nome} · {story}" if story else f"{nome} · {created_at.strftime('%d/%m')}"
        by_story[key] += 1

    story_sessions = {s for _p, _c, s in rows if s}
    story_clicks = (
        clicks.exclude(session="").filter(session__in=story_sessions).count()
        if story_sessions
        else 0
    )
    visitors = (
        base.filter(kind="pageview", session__in=story_sessions).values("visitor").distinct().count()
        if story_sessions
        else 0
    )
    profiles = [
        {"label": _profile_name(p), "raw": p, "n": n, "known": p in INSTAGRAM_PROFILES}
        for p, n in by_profile.most_common(15)
    ]
    stories = [{"label": k, "raw": k, "n": n} for k, n in by_story.most_common(15)]
    return {
        "views": views,
        "visitors": visitors,
        "clicks": story_clicks,
        "share": round(views / total_views * 100) if total_views else 0,
        "ctr": round(story_clicks / views * 100, 1) if views else 0,
        "profiles": profiles,
        "stories": stories,
        "max_profile": profiles[0]["n"] if profiles else 0,
        "max_story": stories[0]["n"] if stories else 0,
        "has_data": views > 0,
    }


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
    top_clicks = [
        {"label": _pretty_label(row["label"]), "raw": row["label"], "n": row["n"]}
        for row in clicks.exclude(label="")
        .values("label")
        .annotate(n=Count("id"))
        .order_by("-n")[:15]
    ]
    # Agrupa pela página "limpa": sem ?query e sem #tag, senão cada fbclid
    # ou tag de story viraria uma linha diferente no ranking.
    _pages = Counter(
        (p or "/").split("?")[0].split("#")[0] or "/"
        for p in views.values_list("path", flat=True)
    )
    top_pages = [{"path": path, "n": n} for path, n in _pages.most_common(15)]

    max_click = top_clicks[0]["n"] if top_clicks else 0
    max_page = top_pages[0]["n"] if top_pages else 0

    # ── Dois recortes independentes: ORGÂNICO e TRÁFEGO PAGO ────────────────
    # Pago = link marcado com utm_medium=paid/cpc/ppc (único sinal confiável).
    # Orgânico = veio do Meta mas sem essa marcação (bio, story, post, DM).
    stories = _stories_stats(base, clicks, total_views)
    base_url = SITE_BASE_URL.get(site, "")
    stories["tag_guide"] = [
        {"tag": tag, "profile": nome, "url": f"{base_url}#{tag}"}
        for tag, nome in INSTAGRAM_PROFILES.items()
    ]
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
        "stories": stories,
        "organic_series_json": json.dumps(organic["series"]),
        "paid_series_json": json.dumps(paid["series"]),
        # agregados (compatibilidade / visão geral)
        "meta_views": meta_views,
        "meta_paid_views": paid["views"],
        "meta_organic_views": organic["views"],
        "has_meta": meta_views > 0,
    }
    return render(request, "studio/metrics.html", context)


# ── Lead do portfólio da Layfe → cai na Prospecção dela ─────────────────────
# Endpoint público chamado pelo popup do portfólio (layfeamorim.com/portfolio).
# Cria um Prospect na conta da Layfe, etapa "Qualificacao", canal "Portfólio".
_LEAD_WORKSPACE_CACHE = {}


def _layfe_workspace():
    """Resolve o workspace da Layfe (dono do portfólio). Cacheia em memória."""
    if "ws" in _LEAD_WORKSPACE_CACHE:
        return _LEAD_WORKSPACE_CACHE["ws"]
    user = get_user_model().objects.filter(username="layfeamorim").first()
    membership = user.memberships.select_related("workspace").first() if user else None
    ws = membership.workspace if membership else None
    if ws is not None:
        _LEAD_WORKSPACE_CACHE["ws"] = ws
    return ws


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def portfolio_lead(request: HttpRequest) -> HttpResponse:
    origin = request.headers.get("Origin", "")
    if request.method == "OPTIONS":
        return _cors_headers(HttpResponse(status=204), origin)

    ua = request.headers.get("User-Agent", "")[:300]
    if any(marker in ua.lower() for marker in _BOT_MARKERS):
        return _cors_headers(JsonResponse({"ok": True}), origin)  # bot: finge sucesso

    try:
        payload = json.loads((request.body or b"{}").decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return _cors_headers(JsonResponse({"ok": False}, status=400), origin)

    # Honeypot: campo invisível preenchido = robô.
    if str(payload.get("site", "")).strip():
        return _cors_headers(JsonResponse({"ok": True}), origin)

    name = str(payload.get("name", "")).strip()[:160]
    whatsapp = str(payload.get("whatsapp", "")).strip()[:40]
    if len(name) < 2 or sum(ch.isdigit() for ch in whatsapp) < 8:
        return _cors_headers(JsonResponse({"ok": False, "error": "dados incompletos"}, status=400), origin)

    company = str(payload.get("company", "")).strip()[:160] or "(marca não informada)"
    instagram = str(payload.get("instagram", "")).strip()[:160]
    message = str(payload.get("message", "")).strip()[:2000]

    workspace = _layfe_workspace()
    if workspace is None:
        return _cors_headers(JsonResponse({"ok": False}, status=503), origin)

    today = timezone.localdate()
    # Anti-duplicata: mesmo WhatsApp nas últimas 6h não cria de novo.
    recent = Prospect.objects.filter(
        workspace=workspace, whatsapp=whatsapp,
        created_at__gte=timezone.now() - timezone.timedelta(hours=6),
    ).exists()
    if not recent:
        note = f"Veio pelo portfólio (layfeamorim.com/portfolio)."
        if message:
            note += f"\n\nMensagem: {message}"
        Prospect.objects.create(
            workspace=workspace,
            company=company,
            contact=name,
            contact_type="Marca",
            # A marca veio ate a creator pelo portfolio, entao ja nasce com a
            # conversa aberta e um canal real: isso e' Qualificacao, nao
            # abordagem fria.
            stage="Qualificacao",
            contact_outcome="respondeu",
            contact_date=today,
            last_activity_at=timezone.now(),
            stage_changed_at=timezone.now(),
            whatsapp=whatsapp,
            instagram=instagram,
            channel="Portfólio",
            note=note,
        )
    return _cors_headers(JsonResponse({"ok": True}), origin)
