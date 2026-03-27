from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Q, QuerySet
from django.urls import reverse

from .constants import COMPANY_COLORS, DEFAULT_NICHE_NAMES, NAV_GROUPS, NAV_ITEMS, SETTINGS_GROUPS
from .models import Membership, Niche, Project, Prospect, Workspace, WorkspaceSetting


ZERO = Decimal("0")
SHORT_MONTH_NAMES = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}
FULL_MONTH_NAMES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}
SOURCE_MIX_COLORS = {
    "Inbound": "#4d8cff",
    "Prospecção": "#20b7a7",
    "Indicação": "#7f6fff",
    "Plataforma": "#f59a3d",
    "Agência": "#61748e",
}
SOURCE_MIX_ORDER = ["Inbound", "Prospecção", "Indicação", "Plataforma", "Agência"]


def currency(value: Decimal | int | float | None) -> str:
    amount = Decimal(value or 0)
    integer_value = int(amount.quantize(Decimal("1")))
    formatted = f"{integer_value:,.0f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R${formatted}"


def sum_money(values) -> Decimal:
    total = ZERO
    for value in values:
        total += Decimal(value or 0)
    return total


def normalize_company_name(raw_value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", str(raw_value or ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def normalize_closing_source(raw_value: str | None) -> str | None:
    normalized = normalize_company_name(raw_value)
    if not normalized:
        return None
    if "indic" in normalized:
        return "Indicação"
    if "agen" in normalized:
        return "Agência"
    if "plata" in normalized:
        return "Plataforma"
    if "prospec" in normalized or "outbound" in normalized:
        return "Prospecção"
    if "inbound" in normalized:
        return "Inbound"
    if normalized in {"instagram", "instagram dm", "whatsapp", "email", "site", "direct", "marketing", "social media"}:
        return "Inbound"
    return None


def company_palette(company: str) -> tuple[str, str, str]:
    if company in COMPANY_COLORS:
        return COMPANY_COLORS[company]

    palette_values = list(COMPANY_COLORS.values())
    return palette_values[sum(ord(char) for char in company) % len(palette_values)]


def short_date(raw_date: date) -> str:
    return f"{raw_date.day:02d} {SHORT_MONTH_NAMES[raw_date.month]}"


def month_label(raw_date: date) -> str:
    return f"{SHORT_MONTH_NAMES[raw_date.month]}/{raw_date.year % 100:02d}"


def long_month_label(raw_date: date) -> str:
    return f"{FULL_MONTH_NAMES[raw_date.month]} {raw_date.year}"


def month_value(raw_date: date) -> str:
    return raw_date.strftime("%Y-%m")


def parse_month_value(raw_value: str | None) -> date | None:
    if not raw_value:
        return None
    try:
        return date.fromisoformat(f"{raw_value}-01")
    except ValueError:
        return None


def format_days(value: float) -> str:
    if value == int(value):
        return f"{int(value)} dias"
    return f"{str(round(value, 1)).replace('.', ',')} dias"


def get_or_create_workspace_for_user(user: User) -> Workspace:
    membership = user.memberships.select_related("workspace").first()
    if membership:
        ensure_default_niches(membership.workspace)
        return membership.workspace

    workspace = Workspace.objects.create(name=f"{user.username or user.email or 'Studio'} Studio")
    Membership.objects.create(user=user, workspace=workspace, role=Membership.ROLE_OWNER)
    ensure_default_settings(workspace)
    ensure_default_niches(workspace)
    return workspace


def ensure_default_settings(workspace: Workspace) -> None:
    for group in SETTINGS_GROUPS:
        for row in group["rows"]:
            default_value = row["value"]
            if isinstance(default_value, bool):
                default_value = "1" if default_value else "0"
            WorkspaceSetting.objects.get_or_create(
                workspace=workspace,
                key=row["id"],
                defaults={"value": str(default_value)},
            )


def ensure_default_niches(workspace: Workspace) -> None:
    for name in DEFAULT_NICHE_NAMES:
        Niche.objects.get_or_create(
            workspace=workspace,
            name=name,
        )


def default_niche_queryset(workspace: Workspace, current_niche: Niche | None = None) -> QuerySet[Niche]:
    ensure_default_niches(workspace)
    base_filter = Q(name__in=DEFAULT_NICHE_NAMES)
    if current_niche and current_niche.pk:
        base_filter |= Q(pk=current_niche.pk)
    return Niche.objects.filter(workspace=workspace).filter(base_filter).order_by("name")


def default_niche_list(workspace: Workspace) -> list[Niche]:
    ensure_default_niches(workspace)
    niches_by_name = {
        item.name: item
        for item in Niche.objects.filter(workspace=workspace, name__in=DEFAULT_NICHE_NAMES)
    }
    return [niches_by_name[name] for name in DEFAULT_NICHE_NAMES if name in niches_by_name]


def settings_map(workspace: Workspace) -> dict[str, str]:
    ensure_default_settings(workspace)
    ensure_default_niches(workspace)
    return {item.key: item.value for item in workspace.settings.all()}


def save_settings(workspace: Workspace, cleaned_data: dict) -> None:
    for key, value in cleaned_data.items():
        stored_value = "1" if value is True else "0" if value is False else str(value)
        WorkspaceSetting.objects.update_or_create(
            workspace=workspace,
            key=key,
            defaults={"value": stored_value},
        )


def navigation(page_key: str) -> list[dict]:
    items = []
    for item in NAV_ITEMS:
        items.append({**item, "url": reverse(item["url_name"]), "active": item["key"] == page_key})
    return items


def navigation_groups(page_key: str) -> list[dict]:
    nav_items = {item["key"]: item for item in navigation(page_key)}
    groups = []
    for group in NAV_GROUPS:
        items = [nav_items[key] for key in group["keys"] if key in nav_items]
        if items:
            groups.append({"label": group["label"], "items": items})
    return groups


def shell_context(
    page_key: str,
    workspace: Workspace,
    title: str,
    subtitle: str,
    user: User | None = None,
    action_label: str | None = None,
    action_url: str | None = None,
) -> dict:
    workspace_settings = settings_map(workspace)
    workspace_membership = None
    if user and getattr(user, "is_authenticated", False):
        workspace_membership = user.memberships.select_related("workspace").filter(workspace=workspace).first()
    today = date.today()
    today_meetings = list(
        Prospect.objects.filter(
            workspace=workspace,
            meeting_scheduled=True,
            meeting_date=today,
        )
        .order_by("company", "contact")
    )
    follow_up_alerts = follow_up_candidates(workspace) if str(workspace_settings.get("ops_follow_up_reminders", "")).lower() in {"1", "true", "yes", "on"} else []
    return {
        "nav_items": navigation(page_key),
        "nav_groups": navigation_groups(page_key),
        "page_key": page_key,
        "page_title": title,
        "page_subtitle": subtitle,
        "header_action_label": action_label,
        "header_action_url": reverse(action_url) if action_url else None,
        "workspace": workspace,
        "workspace_membership": workspace_membership,
        "meeting_alerts": [
            {
                "id": item.id,
                "company": item.company,
                "contact": item.contact,
                "contact_type": item.contact_type,
            }
            for item in today_meetings
        ],
        "meeting_alert_date": today.strftime("%Y-%m-%d"),
        "follow_up_alerts": follow_up_alerts,
        "follow_up_alert_date": today.strftime("%Y-%m-%d"),
        "theme_class": "theme-dark" if str(workspace_settings.get("ui_dark_theme", "")).lower() in {"1", "true", "yes", "on"} else "",
    }


def _shift_month(base_date: date, months: int) -> date:
    absolute_month = (base_date.year * 12) + (base_date.month - 1) + months
    year = absolute_month // 12
    month = (absolute_month % 12) + 1
    return date(year, month, 1)


def revenue_context(projects: QuerySet[Project], revenue_range: str = "last_6_months") -> dict:
    current_year = date.today().year
    current_month = date.today().replace(day=1)
    month_starts = [date(current_year, month, 1) for month in range(1, 13)]
    totals = {item: ZERO for item in month_starts}
    chart_width = 960
    chart_height = 260
    chart_top = 12
    chart_bottom = 22
    chart_side_padding = 18

    for project in projects:
        month_start = project.close_date.replace(day=1)
        if month_start in totals:
            totals[month_start] += Decimal(project.total_value or 0)

    max_value = max([int(totals[item]) for item in month_starts] + [30000])
    usable_height = chart_height - chart_top - chart_bottom
    points = []
    for index, month_start in enumerate(month_starts):
        amount = int(totals[month_start])
        progress_ratio = (amount / max_value) if max_value else 0
        usable_width = chart_width - (chart_side_padding * 2)
        x_position = chart_side_padding if len(month_starts) == 1 else round(chart_side_padding + ((usable_width / (len(month_starts) - 1)) * index), 2)
        y_position = round(chart_height - chart_bottom - (progress_ratio * usable_height), 2)
        points.append(
            {
                "label": month_label(month_start),
                "amount": amount,
                "height": max(6 if amount else 2, int((amount / max_value) * 100)) if max_value else 0,
                "x": x_position,
                "y": y_position,
                "highlighted": month_start == current_month,
            }
        )

    steps = []
    for step in range(3, -1, -1):
        value = int(max_value * step / 3)
        steps.append({"label": currency(value)})

    line_path = " ".join(
        f"{'M' if index == 0 else 'L'} {point['x']} {point['y']}"
        for index, point in enumerate(points)
    )

    return {
        "points": points,
        "steps": steps,
        "path": line_path,
        "chart_width": chart_width,
        "chart_height": chart_height,
    }


def closing_source_mix(projects: list[Project]) -> dict:
    counts = {label: 0 for label in SOURCE_MIX_ORDER}
    for item in projects:
        label = normalize_closing_source(item.closing_source)
        if label in counts:
            counts[label] += 1

    total = sum(counts.values())
    legend = []
    gradient_parts = []
    start = 0.0
    for label in SOURCE_MIX_ORDER:
        count = counts[label]
        percentage = round((count / total) * 100) if total else 0
        color = SOURCE_MIX_COLORS[label]
        legend.append(
            {
                "label": label,
                "count": count,
                "percentage": percentage,
                "color": color,
            }
        )
        if total and count:
            span = (count / total) * 100
            end = start + span
            gradient_parts.append(f"{color} {start:.2f}% {end:.2f}%")
            start = end

    return {
        "total": total,
        "items": legend,
        "gradient": ", ".join(gradient_parts) if gradient_parts else "#dfe8f5 0% 100%",
    }


def follow_up_candidates(workspace: Workspace) -> list[dict]:
    today = date.today()
    projects = list(Project.objects.filter(workspace=workspace).order_by("-due_date", "-close_date", "-updated_at"))
    prospect_companies = {
        normalize_company_name(item)
        for item in Prospect.objects.filter(workspace=workspace).exclude(company__exact="").values_list("company", flat=True)
        if normalize_company_name(item)
    }
    latest_by_company: dict[str, Project] = {}
    for project in projects:
        company_key = normalize_company_name(project.company)
        if not company_key or company_key in latest_by_company:
            continue
        latest_by_company[company_key] = project

    candidates = []
    for company_key, project in latest_by_company.items():
        if company_key in prospect_companies or project.stage != "Entregue":
            continue
        days_since_last_job = (today - project.due_date).days
        if days_since_last_job < 30:
            continue
        color_a, color_b, accent = company_palette(project.company)
        candidates.append(
            {
                "kind": "follow_up",
                "company": project.company,
                "dismiss_key": company_key,
                "service_category": project.service_category_name,
                "last_delivery_text": short_date(project.due_date),
                "days_since_last_job": days_since_last_job,
                "note": f'Ja tem {days_since_last_job} dias desde o seu ultimo trabalho para a marca {project.company} que tal mandar um "oi sumido?"',
                "accent": accent,
                "colors": (color_a, color_b),
            }
        )

    candidates.sort(key=lambda item: (-item["days_since_last_job"], item["company"].casefold()))
    return candidates


def dashboard_snapshot(workspace: Workspace, revenue_range: str = "last_6_months") -> dict:
    projects = Project.objects.filter(workspace=workspace)
    active_projects = list(projects.filter(stage="Fechado").order_by("due_date"))
    delivered_projects = list(projects.filter(stage="Entregue").order_by("-due_date"))
    prospects = list(Prospect.objects.filter(workspace=workspace))
    current_month = date.today().replace(day=1)

    active_jobs = sum(item.deliverables_count for item in active_projects)
    company_names = set()
    for raw_name in projects.exclude(company__exact="").values_list("company", flat=True):
        normalized_name = normalize_company_name(raw_name)
        if normalized_name:
            company_names.add(normalized_name)
    for raw_name in Prospect.objects.filter(workspace=workspace).exclude(company__exact="").values_list("company", flat=True):
        normalized_name = normalize_company_name(raw_name)
        if normalized_name:
            company_names.add(normalized_name)
    clients_portfolio = len(company_names)
    active_company_names = set()
    for item in active_projects:
        normalized_name = normalize_company_name(item.company)
        if normalized_name:
            active_company_names.add(normalized_name)
    active_companies = len(active_company_names)
    monthly_revenue = sum_money(
        item.total_value
        for item in projects
        if item.close_date.year == current_month.year and item.close_date.month == current_month.month
    )
    total_closed = sum_money(item.total_value for item in active_projects)

    pipeline = [
        {"stage": "Prospecção", "count": sum(1 for item in prospects if item.stage == "Prospeccao"), "amount_text": "", "icon_label": "P", "accent": "#4d8cff", "progress": 54},
        {"stage": "Negociacao", "count": sum(1 for item in prospects if item.stage == "Negociacao"), "amount_text": "", "icon_label": "N", "accent": "#4d8cff", "progress": 33},
        {"stage": "Fechado", "count": len(active_projects), "amount_text": currency(total_closed), "icon_label": "F", "accent": "#2fb9ac", "progress": 72 if total_closed else 0},
        {"stage": "Entregue", "count": sum(item.deliverables_count for item in delivered_projects[:4]), "amount_text": currency(sum_money(item.total_value for item in delivered_projects[:4])), "icon_label": "E", "accent": "#aeb9c9", "progress": 59 if delivered_projects else 0},
    ]

    activities = []
    for item in active_projects[:2]:
        color_a, color_b, accent = company_palette(item.company)
        activities.append(
            {
                "service_category": item.service_category_name,
                "company": item.company,
                "progress": item.progress,
                "date": short_date(item.due_date),
                "colors": (color_a, color_b),
                "accent": accent,
            }
        )

    featured = None
    if active_projects:
        item = active_projects[0]
        color_a, color_b, accent = company_palette(item.company)
        featured = {
            "service_category": item.service_category_name,
            "company": item.company,
            "progress": item.progress,
            "due_text": short_date(item.due_date),
            "colors": (color_a, color_b),
            "accent": accent,
        }

    return {
        "stats": [
            {"title": "Carteira de Clientes", "value": str(clients_portfolio), "icon_label": "C"},
            {"title": "Carteira Ativa", "value": str(active_companies), "icon_label": "E"},
            {"title": "Trabalhos Ativos", "value": str(active_jobs), "icon_label": "T"},
            {"title": "Faturamento Mensal", "value": currency(monthly_revenue), "icon_label": "$"},
        ],
        "revenue": revenue_context(projects.order_by("close_date"), revenue_range),
        "pipeline": pipeline,
        "activities": activities,
        "featured": featured,
    }


def prospection_snapshot(workspace: Workspace) -> dict:
    prospects = list(Prospect.objects.filter(workspace=workspace))
    total = len(prospects) or 1
    meetings = sum(1 for item in prospects if item.meeting_scheduled)
    negotiation_count = sum(1 for item in prospects if item.stage == "Negociacao")
    follow_up_items = follow_up_candidates(workspace)

    columns = []
    for stage in ("Prospeccao", "Negociacao"):
        items = []
        for item in [candidate for candidate in prospects if candidate.stage == stage]:
            color_a, color_b, accent = company_palette(item.company)
            channels = []
            if item.email:
                channels.append({"label": "Email", "value": item.email})
            if item.instagram:
                channels.append({"label": "Instagram", "value": item.instagram})
            if item.whatsapp:
                channels.append({"label": "WhatsApp", "value": item.whatsapp})

            items.append(
                {
                    "kind": "prospect",
                    "id": item.id,
                    "company": item.company,
                    "contact": item.contact,
                    "contact_type": item.contact_type,
                    "contact_date": short_date(item.contact_date) if item.contact_date else "",
                    "meeting_date": short_date(item.meeting_date) if item.meeting_date else "",
                    "niche": item.niche.name if item.niche_id else "",
                    "note": item.note,
                    "meeting_scheduled": item.meeting_scheduled,
                    "channels": channels,
                    "accent": accent,
                    "colors": (color_a, color_b),
                }
            )
        columns.append({"title": "Prospecção" if stage == "Prospeccao" else stage, "items": items})
    columns.append({"title": "Follow-up", "items": follow_up_items})

    return {
        "stats": [
            {"title": "Novos Leads", "value": str(sum(1 for item in prospects if item.stage == "Prospeccao")), "icon_label": "L"},
            {"title": "Reunioes", "value": str(meetings), "icon_label": "R"},
            {"title": "Taxa de resposta", "value": f"{round((negotiation_count / total) * 100)}%", "icon_label": "%"},
            {"title": "Negociacao", "value": str(negotiation_count), "icon_label": "N"},
        ],
        "columns": columns,
    }


def empresas_snapshot(workspace: Workspace) -> dict:
    projects = list(Project.objects.filter(workspace=workspace).order_by("due_date"))
    active = [item for item in projects if item.stage == "Fechado"]
    today = date.today()
    upcoming_limit = today + timedelta(days=21)

    cards = []
    for item in projects:
        color_a, color_b, accent = company_palette(item.company)
        cards.append(
            {
                "id": item.id,
                "company": item.company,
                "service_category": item.service_category_name,
                "status": item.status,
                "total_value": currency(item.total_value),
                "progress": item.progress,
                "due_text": short_date(item.due_date),
                "colors": (color_a, color_b),
                "accent": accent,
                "stage": item.stage,
            }
        )

    active_company_names = {
        normalize_company_name(item.company)
        for item in active
        if normalize_company_name(item.company)
    }
    upcoming_deliveries = sum(1 for item in active if today <= item.due_date <= upcoming_limit)
    delivered_count = sum(1 for item in projects if item.stage == "Entregue")
    return {
        "stats": [
            {"title": "Carteira ativa", "value": str(len(active_company_names)), "icon_label": "E"},
            {"title": "Aguardando aprovacao", "value": str(sum(1 for item in active if item.status == "Aguardando cliente")), "icon_label": "A"},
            {"title": "Entregas proximas", "value": str(upcoming_deliveries), "icon_label": "P"},
            {"title": "Finalizado", "value": str(delivered_count), "icon_label": "F"},
        ],
        "active": [item for item in cards if item["stage"] == "Fechado"],
        "delivered": [item for item in cards if item["stage"] == "Entregue"][:4],
    }


def jobs_snapshot(workspace: Workspace) -> dict:
    snapshot = empresas_snapshot(workspace)
    snapshot["source_mix"] = closing_source_mix(list(Project.objects.filter(workspace=workspace)))
    return snapshot


def finance_snapshot(workspace: Workspace, month_filter: str | None = None) -> dict:
    active_projects = list(Project.objects.filter(workspace=workspace, stage="Fechado").order_by("due_date"))
    month_options = sorted({item.due_date.replace(day=1) for item in active_projects} | {date.today().replace(day=1)}, reverse=True)
    selected_month = parse_month_value(month_filter)
    if selected_month is None or selected_month.replace(day=1) not in month_options:
        current_month = date.today().replace(day=1)
        selected_month = current_month if current_month in month_options else month_options[0]
    selected_month = selected_month.replace(day=1)

    month_projects = [item for item in active_projects if item.due_date.year == selected_month.year and item.due_date.month == selected_month.month]
    forecast = sum_money(item.total_value for item in month_projects)
    received = sum_money(item.received_value for item in month_projects)
    receivable = max(forecast - received, ZERO)
    entry = sum_money(item.entry_value for item in month_projects)
    avg_collection_days = (
        round(sum(max((item.due_date - item.close_date).days, 1) for item in month_projects) / len(month_projects), 1)
        if month_projects
        else 0.0
    )

    schedule = []
    for item in month_projects:
        outstanding = max(Decimal(item.total_value) - Decimal(item.received_value), ZERO)
        if outstanding <= 0:
            continue
        _, _, accent = company_palette(item.company)
        schedule.append({"company": item.company, "kind": "Saldo" if item.received_value > 0 else "Entrada", "due": short_date(item.due_date), "amount": currency(outstanding), "status": "Pendente", "accent": accent})

    return {
        "month_choices": [{"value": month_value(item), "label": long_month_label(item)} for item in month_options],
        "selected_month": {"value": month_value(selected_month), "label": long_month_label(selected_month)},
        "stats": [
            {"title": "Previsao", "value": currency(forecast), "icon_label": "$"},
            {"title": "A receber", "value": currency(receivable), "icon_label": "A"},
            {"title": "Recebido", "value": currency(received), "icon_label": "+"},
            {"title": "Media de recebimento (45 dias)", "value": format_days(avg_collection_days), "icon_label": "M"},
        ],
        "schedule": schedule,
        "breakdown": [
            {"label": "Previsao do mes", "amount_text": currency(forecast), "progress": 100 if forecast else 0, "accent": "#20b7a7"},
            {"label": "Entrada prevista", "amount_text": currency(entry), "progress": round((entry / forecast) * 100) if forecast else 0, "accent": "#4d8cff"},
            {"label": "A receber", "amount_text": currency(receivable), "progress": round((receivable / forecast) * 100) if forecast else 0, "accent": "#7f6fff"},
            {"label": "Recebido", "amount_text": currency(received), "progress": round((received / forecast) * 100) if forecast else 0, "accent": "#f59a3d"},
        ],
    }


def reports_snapshot(workspace: Workspace, month_filter: str | None = None) -> dict:
    projects = list(Project.objects.filter(workspace=workspace))
    month_options = sorted({item.close_date.replace(day=1) for item in projects} | {date.today().replace(day=1)}, reverse=True)
    selected_month = parse_month_value(month_filter)
    if selected_month is None or selected_month.replace(day=1) not in month_options:
        current_month = date.today().replace(day=1)
        selected_month = current_month if current_month in month_options else month_options[0]
    selected_month = selected_month.replace(day=1)

    month_projects = [item for item in projects if item.close_date.year == selected_month.year and item.close_date.month == selected_month.month]
    volume = len(month_projects)
    total_closed = sum_money(item.total_value for item in month_projects)
    selected_month_label = long_month_label(selected_month)

    source_counts: dict[str, int] = {}
    niche_counts: dict[str, int] = {}
    for item in month_projects:
        source_label = (item.closing_source or "").strip() or "Nao informado"
        source_counts[source_label] = source_counts.get(source_label, 0) + 1
        niche_label = item.niche.name if item.niche_id else "Nao informado"
        niche_counts[niche_label] = niche_counts.get(niche_label, 0) + 1

    source_palette = ["#4d8cff", "#20b7a7", "#7f6fff", "#f59a3d", "#61748e", "#c765c7"]
    sorted_sources = sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))
    via_breakdown = []
    for index, (label, count) in enumerate(sorted_sources):
        percentage = round((count / volume) * 100) if volume else 0
        via_breakdown.append(
            {
                "label": label,
                "amount_text": f"{percentage}%",
                "progress": percentage,
                "accent": source_palette[index % len(source_palette)],
                "count_text": f"{count} trabalho{'s' if count != 1 else ''}",
            }
        )

    top_source_label, top_source_count = sorted_sources[0] if sorted_sources else ("Sem dados", 0)
    top_source_percentage = round((top_source_count / volume) * 100) if volume else 0
    top_niche_label, top_niche_count = (
        sorted(niche_counts.items(), key=lambda item: (-item[1], item[0]))[0]
        if niche_counts
        else ("Sem dados", 0)
    )

    return {
        "stats": [
            {"title": "Volume de trabalhos", "value": str(volume), "icon_label": "V"},
            {"title": "Total fechado", "value": currency(total_closed), "icon_label": "$"},
            {"title": "Via principal", "value": top_source_label, "icon_label": "%"},
            {"title": "Nicho lider", "value": top_niche_label, "icon_label": "N"},
        ],
        "month_choices": [{"value": month_value(item), "label": long_month_label(item)} for item in month_options],
        "selected_month": {"value": month_value(selected_month), "label": long_month_label(selected_month)},
        "via_breakdown": via_breakdown,
        "highlights": [
            {
                "title": "Via com mais fechamentos",
                "description": (
                    f"{top_source_label} respondeu por {top_source_percentage}% dos fechamentos de {selected_month_label.lower()}."
                    if volume
                    else f"Nenhum trabalho fechado em {selected_month_label.lower()}."
                ),
            },
            {
                "title": "Nicho que mais fechou",
                "description": (
                    f"{top_niche_label} liderou com {top_niche_count} trabalho{'s' if top_niche_count != 1 else ''} fechado{'s' if top_niche_count != 1 else ''} no mes."
                    if volume
                    else "Assim que voce cadastrar fechamentos, o nicho lider aparece aqui."
                ),
            },
            {
                "title": "Resumo do mes",
                "description": (
                    f"{volume} trabalho{'s' if volume != 1 else ''} fechados somando {currency(total_closed)} em {selected_month_label.lower()}."
                    if volume
                    else "Sem fechamentos no periodo selecionado."
                ),
            },
        ],
    }


def average_project_days(projects: list[Project]) -> float:
    values = [max((item.due_date - item.close_date).days, 1) for item in projects]
    return round(sum(values) / len(values), 1) if values else 0.0
