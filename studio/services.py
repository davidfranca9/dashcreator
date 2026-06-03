from __future__ import annotations

import calendar
import json
import re
import unicodedata
from urllib.parse import urlencode
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db.models import Case, IntegerField, Q, QuerySet, Value, When
from django.urls import reverse

from .contact_types import infer_contact_type
from .constants import (
    CASH_BOX_ALLOCATION_SETTINGS,
    COMPANY_COLORS,
    DEFAULT_NICHE_NAMES,
    LEGACY_DEFAULT_NICHE_NAMES,
    NAV_GROUPS,
    NAV_ITEMS,
    SERVICE_TYPE_CHOICES,
    SETTINGS_GROUPS,
)
from .models import CashBox, FinanceEntry, FixedCost, Membership, Niche, Project, ProjectInstallment, Prospect, ServiceCategory, Workspace, WorkspaceSetting


ZERO = Decimal("0")
UGC_MANAGER_SERVICE_TYPE = "ugc_manager"
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
    3: "Março",
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
MONTH_FILTER_PAGE_KEYS = {"dashboard", "jobs", "finance", "reports", "prospection"}
ALL_MONTH_VALUE = "all"
SOURCE_MIX_COLORS = {
    "Inbound": "#4d8cff",
    "Prospec\u00e7\u00e3o": "#20b7a7",
    "Follow-up": "#6f7eff",
    "Indica\u00e7\u00e3o": "#7f6fff",
    "Plataforma": "#f59a3d",
    "Ag\u00eancia": "#61748e",
}
SOURCE_MIX_ORDER = ["Inbound", "Prospec\u00e7\u00e3o", "Follow-up", "Indica\u00e7\u00e3o", "Plataforma", "Ag\u00eancia"]


FOLLOW_UP_CONFIRMED_COMPANIES_KEY = "ops_follow_up_confirmed_companies"
FOLLOW_UP_DISMISSED_COMPANIES_KEY = "ops_follow_up_dismissed_companies"
AWAITING_APPROVAL_STATUS = "Aguardando aprovação"
OVERDUE_EXCLUDED_STATUSES = {AWAITING_APPROVAL_STATUS}


def currency(value: Decimal | int | float | None) -> str:
    amount = Decimal(value or 0).quantize(Decimal("0.01"))
    integer_part, cents = divmod(amount.copy_abs(), Decimal(1))
    sign = "-" if amount < 0 else ""
    integer_formatted = f"{int(integer_part):,.0f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if cents == 0:
        return f"{sign}R${integer_formatted}"
    cents_value = int((cents * 100).quantize(Decimal("1")))
    return f"{sign}R${integer_formatted},{cents_value:02d}"


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
    if normalized in {"nao se aplica", "na se aplica", "nao aplicavel", "sem aplicacao", "n a"}:
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


def normalize_closing_source(raw_value: str | None) -> str | None:
    normalized = normalize_company_name(raw_value)
    if not normalized:
        return None
    if normalized in {"nao se aplica", "na se aplica", "nao aplicavel", "sem aplicacao", "n a"}:
        return None
    if "indic" in normalized:
        return "Indica\u00e7\u00e3o"
    if "agen" in normalized:
        return "Ag\u00eancia"
    if "plata" in normalized:
        return "Plataforma"
    if "follow up" in normalized or "followup" in normalized:
        return "Follow-up"
    if "prospec" in normalized or "outbound" in normalized:
        return "Prospec\u00e7\u00e3o"
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


def payment_reference_date(project: Project) -> date:
    return project.payment_due_date or project.due_date


def whatsapp_contact_url(raw_phone: str | None) -> str:
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", raw_phone)
    if not digits:
        return ""
    if not digits.startswith("55") and len(digits) <= 11:
        digits = f"55{digits}"
    return f"https://wa.me/{digits}"


def google_calendar_event_url(title: str, event_date: date, details: str = "") -> str:
    next_day = event_date + timedelta(days=1)
    return "https://calendar.google.com/calendar/render?" + urlencode(
        {
            "action": "TEMPLATE",
            "text": title,
            "dates": f"{event_date.strftime('%Y%m%d')}/{next_day.strftime('%Y%m%d')}",
            "details": details,
        }
    )


def project_counts_as_overdue(project: Project, today: date | None = None) -> bool:
    reference_date = today or date.today()
    return (
        project.stage == "Fechado"
        and project.due_date < reference_date
        and project.status not in OVERDUE_EXCLUDED_STATUSES
    )


def user_display_name(user: User | None) -> str:
    if not user:
        return "criadora"
    return (user.first_name or user.get_full_name() or user.username or user.email or "criadora").split()[0]


def profile_display_name(workspace: Workspace, user: User | None = None) -> str:
    profile_name = (workspace.business_full_name or "").strip()
    if profile_name:
        return profile_name.split()[0]
    return user_display_name(user)


def image_usage_expires_on(project: Project) -> date | None:
    if project.content_distribution != "Ads" or not project.image_license_term_days:
        return None
    return project.due_date + timedelta(days=project.image_license_term_days)


def image_usage_term_label(project: Project) -> str:
    if not project.image_license_term_days:
        return ""
    return f"{project.image_license_term_days} dias"


def workspace_business_address_summary(workspace: Workspace) -> str:
    parts = []
    street_line = " ".join(
        part
        for part in [workspace.business_street, f"Nº {workspace.business_number}" if workspace.business_number else ""]
        if part
    ).strip()
    if street_line:
        parts.append(street_line)
    if workspace.business_complement:
        parts.append(workspace.business_complement)
    if workspace.business_zip_code:
        parts.append(f"CEP {workspace.business_zip_code}")
    if workspace.business_address:
        parts.append(workspace.business_address)
    return ", ".join(parts)


def distribution_label(project: Project) -> str:
    if project.content_distribution == "Nao se aplica":
        return "Não se aplica"
    return project.content_distribution or "Não definido"


def month_options_for_workspace(workspace: Workspace) -> list[date]:
    months = {date.today().replace(day=1)}
    for close_date, due_date, payment_due_date, meeting_date, contract_duration_months in Project.objects.filter(workspace=workspace).values_list(
        "close_date",
        "due_date",
        "payment_due_date",
        "meeting_date",
        "contract_duration_months",
    ):
        contract_month_count = max(1, int(contract_duration_months or 1))
        if close_date:
            months.add(close_date.replace(day=1))
            for month_index in range(1, contract_month_count):
                months.add(_shift_month(close_date.replace(day=1), month_index))
        if due_date:
            months.add(due_date.replace(day=1))
        if payment_due_date and contract_month_count <= 1:
            months.add(payment_due_date.replace(day=1))
        if meeting_date:
            months.add(meeting_date.replace(day=1))
    for due_date, paid_on in ProjectInstallment.objects.filter(workspace=workspace).values_list("due_date", "paid_on"):
        if due_date:
            months.add(due_date.replace(day=1))
        if paid_on:
            months.add(paid_on.replace(day=1))
    for occurred_on in FinanceEntry.objects.filter(workspace=workspace).exclude(occurred_on__isnull=True).values_list("occurred_on", flat=True):
        if occurred_on:
            months.add(occurred_on.replace(day=1))
    for contact_date, meeting_date, created_at in Prospect.objects.filter(workspace=workspace).values_list(
        "contact_date",
        "meeting_date",
        "created_at",
    ):
        if contact_date:
            months.add(contact_date.replace(day=1))
        if meeting_date:
            months.add(meeting_date.replace(day=1))
        if created_at:
            months.add(created_at.date().replace(day=1))
    return sorted(months)


def resolve_selected_month(month_filter: str | None, month_options: list[date]) -> date | None:
    if month_filter == ALL_MONTH_VALUE:
        return None
    selected_month = parse_month_value(month_filter)
    if selected_month is None or selected_month.replace(day=1) not in month_options:
        current_month = date.today().replace(day=1)
        selected_month = current_month if current_month in month_options else month_options[0]
    return selected_month.replace(day=1)


def month_choice_payload(month_options: list[date]) -> list[dict[str, str]]:
    return [{"value": ALL_MONTH_VALUE, "label": "Todos"}] + [
        {"value": month_value(item), "label": long_month_label(item)}
        for item in month_options
    ]


def selected_month_payload(selected_month: date | None) -> dict[str, str]:
    if selected_month is None:
        return {"value": ALL_MONTH_VALUE, "label": "Todos"}
    return {"value": month_value(selected_month), "label": long_month_label(selected_month)}


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


def _ordered_niche_queryset(queryset: QuerySet[Niche]) -> QuerySet[Niche]:
    custom_order = [
        When(name=name, then=Value(index))
        for index, name in enumerate(DEFAULT_NICHE_NAMES)
    ]
    return queryset.annotate(
        _default_order=Case(
            *custom_order,
            default=Value(len(DEFAULT_NICHE_NAMES)),
            output_field=IntegerField(),
        )
    ).order_by("_default_order", "name")


def ensure_default_niches(workspace: Workspace) -> None:
    for name in DEFAULT_NICHE_NAMES:
        Niche.objects.get_or_create(
            workspace=workspace,
            name=name,
        )
    Niche.objects.filter(
        workspace=workspace,
        name__in=LEGACY_DEFAULT_NICHE_NAMES,
    ).exclude(
        name__in=DEFAULT_NICHE_NAMES,
    ).filter(
        prospects__isnull=True,
        projects__isnull=True,
    ).delete()


def default_niche_queryset(workspace: Workspace, current_niche: Niche | None = None) -> QuerySet[Niche]:
    ensure_default_niches(workspace)
    base_filter = Q(name__in=DEFAULT_NICHE_NAMES)
    if current_niche and current_niche.pk:
        base_filter |= Q(pk=current_niche.pk)
    return _ordered_niche_queryset(Niche.objects.filter(workspace=workspace).filter(base_filter))


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


def _workspace_key_list(workspace: Workspace, setting_key: str) -> set[str]:
    raw_value = WorkspaceSetting.objects.filter(workspace=workspace, key=setting_key).values_list("value", flat=True).first()
    if not raw_value:
        return set()
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed = []
    return {normalize_company_name(item) for item in parsed if normalize_company_name(item)}


def _save_workspace_key_list(workspace: Workspace, setting_key: str, values: set[str]) -> None:
    WorkspaceSetting.objects.update_or_create(
        workspace=workspace,
        key=setting_key,
        defaults={"value": json.dumps(sorted(values))},
    )


def follow_up_state(workspace: Workspace) -> tuple[set[str], set[str]]:
    return (
        _workspace_key_list(workspace, FOLLOW_UP_CONFIRMED_COMPANIES_KEY),
        _workspace_key_list(workspace, FOLLOW_UP_DISMISSED_COMPANIES_KEY),
    )


def save_settings(workspace: Workspace, cleaned_data: dict) -> None:
    for key, value in cleaned_data.items():
        stored_value = "1" if value is True else "0" if value is False else str(value)
        WorkspaceSetting.objects.update_or_create(
            workspace=workspace,
            key=key,
            defaults={"value": stored_value},
        )


def _decimal_setting(settings_values: dict[str, str], key: str, default: Decimal) -> Decimal:
    raw_value = str(settings_values.get(key, default)).strip()
    if not raw_value:
        return default
    raw_value = raw_value.replace("R$", "").replace(" ", "")
    if "," in raw_value:
        raw_value = raw_value.replace(".", "").replace(",", ".")
    try:
        return max(Decimal(raw_value), ZERO)
    except Exception:
        return default


def _percentage_text(value: Decimal) -> str:
    amount = Decimal(value or 0).quantize(Decimal("0.01"))
    if amount == amount.to_integral():
        return f"{int(amount)}%"
    return f"{amount.normalize()}%".replace(".", ",")


def navigation(page_key: str, month_filter: str | None = None, badges: dict | None = None) -> list[dict]:
    badges = badges or {}
    items = []
    for item in NAV_ITEMS:
        url = reverse(item["url_name"])
        if month_filter and item["key"] in MONTH_FILTER_PAGE_KEYS:
            url = f"{url}?{urlencode({'month': month_filter})}"
        badge = badges.get(item["key"])
        items.append({**item, "url": url, "active": item["key"] == page_key, "badge": badge})
    return items


def navigation_groups(page_key: str, month_filter: str | None = None, badges: dict | None = None) -> list[dict]:
    nav_items = {item["key"]: item for item in navigation(page_key, month_filter, badges=badges)}
    groups = []
    for group in NAV_GROUPS:
        items = [nav_items[key] for key in group["keys"] if key in nav_items]
        if items:
            groups.append({"label": group["label"], "items": items})
    return groups


def overdue_projects_count(workspace: Workspace) -> int:
    return Project.objects.filter(
        workspace=workspace,
        stage="Fechado",
        due_date__lt=date.today(),
    ).exclude(status__in=OVERDUE_EXCLUDED_STATUSES).count()


def navigation_badges(workspace: Workspace, follow_up_count: int) -> dict:
    overdue = overdue_projects_count(workspace)
    return {
        "jobs": {"count": overdue, "tone": "danger"} if overdue else None,
        "prospection": {"count": follow_up_count, "tone": "info"} if follow_up_count else None,
    }


def shell_context(
    page_key: str,
    workspace: Workspace,
    title: str,
    subtitle: str,
    user: User | None = None,
    action_label: str | None = None,
    action_url: str | None = None,
    month_filter: str | None = None,
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
    follow_up_alerts = follow_up_popup_alerts(workspace) if str(workspace_settings.get("ops_follow_up_reminders", "")).lower() in {"1", "true", "yes", "on"} else []
    legal_alerts = legal_usage_alerts(workspace, user) if page_key == "legal" else []
    nav_badges = navigation_badges(workspace, follow_up_count=len(follow_up_alerts))
    user_display_name = ""
    if user and getattr(user, "is_authenticated", False):
        user_display_name = (user.get_full_name() or user.username or user.email or "").strip()
    return {
        "nav_items": navigation(page_key, month_filter, badges=nav_badges),
        "nav_groups": navigation_groups(page_key, month_filter, badges=nav_badges),
        "user_display_name": user_display_name,
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
                "contact_type": infer_contact_type(
                    item.contact_type,
                    email=item.email,
                    instagram=item.instagram,
                    whatsapp=item.whatsapp,
                ),
            }
            for item in today_meetings
        ],
        "meeting_alert_date": today.strftime("%Y-%m-%d"),
        "follow_up_alerts": follow_up_alerts,
        "follow_up_alert_date": today.strftime("%Y-%m-%d"),
        "legal_alerts": legal_alerts,
        "legal_alert_date": today.strftime("%Y-%m-%d"),
        "theme_class": "theme-dark" if str(workspace_settings.get("ui_dark_theme", "")).lower() in {"1", "true", "yes", "on"} else "",
    }


def _shift_month(base_date: date, months: int) -> date:
    absolute_month = (base_date.year * 12) + (base_date.month - 1) + months
    year = absolute_month // 12
    month = (absolute_month % 12) + 1
    return date(year, month, 1)


def _shift_date_month(base_date: date, months: int) -> date:
    absolute_month = (base_date.year * 12) + (base_date.month - 1) + months
    year = absolute_month // 12
    month = (absolute_month % 12) + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _date_in_month_with_day(month_start: date, day: int) -> date:
    month_day = min(day, calendar.monthrange(month_start.year, month_start.month)[1])
    return date(month_start.year, month_start.month, month_day)


def _project_contract_month_count(project: Project) -> int:
    return max(1, int(project.contract_duration_months or 1))


def _project_contract_start_month(project: Project) -> date:
    return project.close_date.replace(day=1)


def _project_recurring_months(project: Project) -> list[date]:
    start_month = _project_contract_start_month(project)
    return [_shift_month(start_month, index) for index in range(_project_contract_month_count(project))]


def _project_recurring_payment_day(project: Project) -> int:
    return (project.payment_due_date or project.close_date).day


def _project_recurring_payment_dates(project: Project) -> list[date]:
    payment_day = _project_recurring_payment_day(project)
    start_month = _project_contract_start_month(project)
    return [
        _date_in_month_with_day(_shift_month(start_month, index), payment_day)
        for index in range(_project_contract_month_count(project))
    ]


def _project_matches_recurring_payment_month(project: Project, month_start: date) -> bool:
    return any(payment_date.replace(day=1) == month_start for payment_date in _project_recurring_payment_dates(project))


def _project_matches_contract_month(project: Project, month_start: date) -> bool:
    duration = _project_contract_month_count(project)
    start_month = _project_contract_start_month(project)
    end_month = _shift_month(start_month, duration - 1)
    if duration > 1 and project.due_date:
        end_month = max(end_month, project.due_date.replace(day=1))
    return start_month <= month_start <= end_month


def _project_monthly_contract_value(project: Project) -> Decimal:
    monthly_value = Decimal(project.monthly_value or 0)
    if monthly_value > ZERO:
        return monthly_value
    return Decimal(project.total_value or 0)


def _project_cash_value(project: Project) -> Decimal:
    if project.service_type == UGC_MANAGER_SERVICE_TYPE:
        management_value = Decimal(project.monthly_value or 0)
        if management_value > ZERO:
            return management_value
    return Decimal(project.total_value or 0)


def _project_dashboard_single_revenue(project: Project) -> Decimal:
    if project.service_type == UGC_MANAGER_SERVICE_TYPE:
        return _project_cash_value(project)
    return Decimal(project.received_value or 0)


def _project_dashboard_revenue_for_month(project: Project, selected_month: date | None) -> Decimal:
    if selected_month is None:
        if _project_contract_month_count(project) > 1:
            return _project_monthly_contract_value(project) * _project_contract_month_count(project)
        return _project_dashboard_single_revenue(project)
    if _project_contract_month_count(project) > 1:
        return _project_monthly_contract_value(project) if _project_matches_recurring_payment_month(project, selected_month) else ZERO
    if project.close_date.year == selected_month.year and project.close_date.month == selected_month.month:
        return _project_dashboard_single_revenue(project)
    return ZERO


def revenue_context(projects: QuerySet[Project] | list[Project], selected_year: int | None = None) -> dict:
    current_year = selected_year or date.today().year
    current_month = date.today().replace(day=1)
    month_starts = [date(current_year, month, 1) for month in range(1, 13)]
    totals = {item: ZERO for item in month_starts}
    chart_width = 960
    chart_height = 260
    chart_top = 12
    chart_bottom = 22
    chart_side_padding = 18

    for project in projects:
        if _project_contract_month_count(project) > 1:
            amount = _project_monthly_contract_value(project)
            for payment_date in _project_recurring_payment_dates(project):
                month_start = payment_date.replace(day=1)
                if month_start in totals:
                    totals[month_start] += amount
            continue
        month_start = project.close_date.replace(day=1)
        if month_start in totals:
            totals[month_start] += _project_cash_value(project)

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


def prospect_activity_date(item: Prospect) -> date:
    return item.contact_date or item.created_at.date()


def add_months(month_start: date, step: int = 1) -> date:
    total_month = (month_start.year * 12) + month_start.month - 1 + step
    year = total_month // 12
    month = (total_month % 12) + 1
    return date(year, month, 1)


def prospection_evolution_context(workspace: Workspace, selected_month: date | None = None) -> dict:
    prospects = list(Prospect.objects.filter(workspace=workspace).order_by("contact_date", "created_at"))
    if not prospects:
        return {
            "points": [],
            "steps": [{"label": "3"}, {"label": "2"}, {"label": "1"}, {"label": "0"}],
            "path": "",
            "chart_width": 960,
            "chart_height": 260,
            "summary": [],
            "empty_message": "Ainda não há prospecções registradas para montar a evolução.",
        }

    filtered_dates = [
        prospect_activity_date(item)
        for item in prospects
        if selected_month is None
        or (
            prospect_activity_date(item).year == selected_month.year
            and prospect_activity_date(item).month == selected_month.month
        )
    ]
    if not filtered_dates:
        return {
            "points": [],
            "steps": [{"label": "3"}, {"label": "2"}, {"label": "1"}, {"label": "0"}],
            "path": "",
            "chart_width": 960,
            "chart_height": 260,
            "summary": [],
            "empty_message": "Sem prospecções no período selecionado.",
        }

    chart_width = 960
    chart_height = 260
    chart_top = 12
    chart_bottom = 22
    chart_side_padding = 18

    totals: dict[date, int] = {}
    if selected_month is None:
        first_month = min(filtered_dates).replace(day=1)
        last_month = max(filtered_dates).replace(day=1)
        month_cursor = first_month
        while month_cursor <= last_month:
            totals[month_cursor] = 0
            month_cursor = add_months(month_cursor)
        for item_date in filtered_dates:
            month_start = item_date.replace(day=1)
            totals[month_start] = totals.get(month_start, 0) + 1
        labels = {item: month_label(item) for item in totals}
    else:
        for item_date in sorted(set(filtered_dates)):
            totals[item_date] = 0
        for item_date in filtered_dates:
            totals[item_date] = totals.get(item_date, 0) + 1
        labels = {item: short_date(item) for item in totals}

    timeline = list(totals.keys())
    max_value = max(list(totals.values()) + [3])
    usable_height = chart_height - chart_top - chart_bottom
    usable_width = chart_width - (chart_side_padding * 2)

    points = []
    for index, point_date in enumerate(timeline):
        amount = totals[point_date]
        progress_ratio = (amount / max_value) if max_value else 0
        x_position = chart_side_padding if len(timeline) == 1 else round(chart_side_padding + ((usable_width / (len(timeline) - 1)) * index), 2)
        y_position = round(chart_height - chart_bottom - (progress_ratio * usable_height), 2)
        points.append(
            {
                "label": labels[point_date],
                "amount": amount,
                "x": x_position,
                "y": y_position,
            }
        )

    line_path = " ".join(
        f"{'M' if index == 0 else 'L'} {point['x']} {point['y']}"
        for index, point in enumerate(points)
    )
    steps = [{"label": str(int(max_value * step / 3))} for step in range(3, -1, -1)]

    unique_dates = sorted(set(filtered_dates))
    largest_gap_days = max(
        [(later - earlier).days for earlier, later in zip(unique_dates, unique_dates[1:])],
        default=0,
    )
    latest_activity = max(filtered_dates)
    peak_date, peak_count = max(totals.items(), key=lambda item: (item[1], item[0]))

    return {
        "points": points,
        "steps": steps,
        "path": line_path,
        "chart_width": chart_width,
        "chart_height": chart_height,
        "summary": [
            {"title": "Última prospecção", "value": short_date(latest_activity), "detail": f"{latest_activity.year}"},
            {"title": "Dias com atividade", "value": str(len(unique_dates)), "detail": "dias diferentes com prospecção"},
            {
                "title": "Maior intervalo",
                "value": f"{largest_gap_days} dias",
                "detail": "entre uma prospecção e outra" if len(unique_dates) > 1 else "ainda sem intervalo suficiente",
            },
            {
                "title": "Pico de volume",
                "value": f"{peak_count} lead{'s' if peak_count != 1 else ''}",
                "detail": f"em {labels[peak_date]}",
            },
        ],
        "empty_message": "",
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
                "is_zero": count == 0,
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
                "note": f'Já tem {days_since_last_job} dias desde o seu último trabalho para a marca {project.company}, que tal mandar um "oi sumido?"',
                "accent": accent,
                "colors": (color_a, color_b),
            }
        )

    candidates.sort(key=lambda item: (-item["days_since_last_job"], item["company"].casefold()))
    return candidates


def follow_up_popup_alerts(workspace: Workspace) -> list[dict]:
    confirmed_keys, dismissed_keys = follow_up_state(workspace)
    return [
        item
        for item in follow_up_candidates(workspace)
        if item["dismiss_key"] not in confirmed_keys and item["dismiss_key"] not in dismissed_keys
    ]


def confirmed_follow_up_items(workspace: Workspace) -> list[dict]:
    confirmed_keys, dismissed_keys = follow_up_state(workspace)
    return [
        item
        for item in follow_up_candidates(workspace)
        if item["dismiss_key"] in confirmed_keys and item["dismiss_key"] not in dismissed_keys
    ]


def legal_usage_items(workspace: Workspace, user: User | None = None) -> list[dict]:
    today = date.today()
    display_name = profile_display_name(workspace, user)
    projects = list(
        Project.objects.filter(workspace=workspace, content_distribution="Ads")
        .select_related("service_category", "niche")
        .order_by("due_date", "company")
    )
    items = []
    for project in projects:
        expires_on = image_usage_expires_on(project)
        if not expires_on:
            continue
        days_until_expiry = (expires_on - today).days
        color_a, color_b, accent = company_palette(project.company)
        reminder_message = (
            f'Oi, {display_name} O DIREITO DE USO DE IMAGEM DA MARCA {project.company} ESTÁ VENCENDO HOJE, '
            'QUE TAL MANDAR UMA MENSAGEM PARA VER COMO ESTÁ PERFORMANDO O SEU CRIATIVO?'
        )
        total_days = project.image_license_term_days or 0
        elapsed = max(total_days - max(days_until_expiry, 0), 0)
        progress_pct = round((elapsed / total_days) * 100) if total_days else 0
        if days_until_expiry < 0:
            urgency = "expired"
        elif days_until_expiry <= 30:
            urgency = "urgent"
        else:
            urgency = "ok"
        items.append(
            {
                "id": project.id,
                "company": project.company,
                "service_category": project.service_category_name,
                "distribution": distribution_label(project),
                "term_text": image_usage_term_label(project),
                "expires_on": expires_on,
                "expires_text": short_date(expires_on),
                "delivery_text": short_date(project.due_date),
                "start_text": short_date(project.due_date),
                "total_days": total_days,
                "progress_pct": progress_pct,
                "urgency": urgency,
                "days_until_expiry": days_until_expiry,
                "status_text": (
                    "Vence hoje"
                    if days_until_expiry == 0
                    else f"Vence em {days_until_expiry} dias"
                    if days_until_expiry > 0
                    else f"Expirou há {abs(days_until_expiry)} dias"
                ),
                "reminder_message": reminder_message,
                "google_calendar_url": google_calendar_event_url(
                    f"Vencimento de licenciamento - {project.company}",
                    expires_on,
                    reminder_message,
                ),
                "colors": (color_a, color_b),
                "accent": accent,
                "note": project.note,
            }
        )
    return items


def legal_contract_items(workspace: Workspace) -> list[dict]:
    projects = list(
        Project.objects.filter(workspace=workspace).exclude(contract_status=Project.CONTRACT_STATUS_DISMISSED)
        .select_related("service_category", "niche")
        .order_by("-close_date", "-due_date", "-updated_at")
    )
    items = []
    for project in projects:
        color_a, color_b, accent = company_palette(project.company)
        items.append(
            {
                "id": project.id,
                "company": project.company,
                "service_category": project.service_category_name,
                "distribution": distribution_label(project),
                "close_text": short_date(project.close_date),
                "delivery_text": short_date(project.due_date),
                "amount_text": currency(project.total_value),
                "deliverables_text": f"{project.deliverables_count} video{'s' if project.deliverables_count != 1 else ''}",
                "contract_status": project.contract_status,
                "contract_status_text": project.get_contract_status_display(),
                "company_legal_name": project.company_legal_name or project.company,
                "company_cnpj": project.company_cnpj,
                "company_address": project.company_address,
                "company_phone": project.company_phone,
                "colors": (color_a, color_b),
                "accent": accent,
                "note": project.note,
            }
        )
    return items


def legal_usage_alerts(workspace: Workspace, user: User | None = None) -> list[dict]:
    alerts = []
    for item in legal_usage_items(workspace, user):
        if item["days_until_expiry"] != 0:
            continue
        alerts.append(
            {
                **item,
                "popup_message": item["reminder_message"],
            }
        )
    return alerts


def confirm_follow_up_companies(workspace: Workspace, company_keys: list[str]) -> list[str]:
    eligible_keys = {item["dismiss_key"] for item in follow_up_candidates(workspace)}
    confirmed_keys, dismissed_keys = follow_up_state(workspace)
    added_keys = []
    for raw_key in company_keys:
        company_key = normalize_company_name(raw_key)
        if not company_key or company_key not in eligible_keys:
            continue
        if company_key not in confirmed_keys:
            added_keys.append(company_key)
        confirmed_keys.add(company_key)
        dismissed_keys.discard(company_key)
    _save_workspace_key_list(workspace, FOLLOW_UP_CONFIRMED_COMPANIES_KEY, confirmed_keys)
    _save_workspace_key_list(workspace, FOLLOW_UP_DISMISSED_COMPANIES_KEY, dismissed_keys)
    return added_keys


def dismiss_follow_up_company(workspace: Workspace, company_key: str) -> None:
    normalized_key = normalize_company_name(company_key)
    if not normalized_key:
        return
    confirmed_keys, dismissed_keys = follow_up_state(workspace)
    confirmed_keys.discard(normalized_key)
    dismissed_keys.add(normalized_key)
    _save_workspace_key_list(workspace, FOLLOW_UP_CONFIRMED_COMPANIES_KEY, confirmed_keys)
    _save_workspace_key_list(workspace, FOLLOW_UP_DISMISSED_COMPANIES_KEY, dismissed_keys)


def follow_up_source_project(workspace: Workspace, company_key: str) -> Project | None:
    normalized_key = normalize_company_name(company_key)
    if not normalized_key:
        return None

    if any(
        normalize_company_name(item) == normalized_key
        for item in Prospect.objects.filter(workspace=workspace).exclude(company__exact="").values_list("company", flat=True)
    ):
        return None

    latest_project = None
    for project in Project.objects.filter(workspace=workspace).order_by("-due_date", "-close_date", "-updated_at"):
        if normalize_company_name(project.company) == normalized_key:
            latest_project = project
            break

    if latest_project is None or latest_project.stage != "Entregue":
        return None

    if (date.today() - latest_project.due_date).days < 30:
        return None

    return latest_project


def start_follow_up_prospection(workspace: Workspace, company_key: str) -> Prospect | None:
    project = follow_up_source_project(workspace, company_key)
    if project is None:
        return None

    normalized_key = normalize_company_name(company_key)
    note = f"Retomada de follow-up apos ultimo trabalho entregue em {short_date(project.due_date)}."
    prospect = Prospect.objects.create(
        workspace=workspace,
        company=project.company,
        contact="Contato principal",
        contact_type="Follow-up",
        stage="Prospeccao",
        contact_date=date.today(),
        niche=project.niche,
        note=note,
    )

    confirmed_keys, dismissed_keys = follow_up_state(workspace)
    confirmed_keys.discard(normalized_key)
    dismissed_keys.discard(normalized_key)
    _save_workspace_key_list(workspace, FOLLOW_UP_CONFIRMED_COMPANIES_KEY, confirmed_keys)
    _save_workspace_key_list(workspace, FOLLOW_UP_DISMISSED_COMPANIES_KEY, dismissed_keys)
    return prospect


def dashboard_snapshot(workspace: Workspace, month_filter: str | None = None) -> dict:
    projects = list(Project.objects.filter(workspace=workspace).order_by("close_date", "due_date"))
    month_options = month_options_for_workspace(workspace)
    selected_month = resolve_selected_month(month_filter, month_options)
    if selected_month is None:
        active_projects = [item for item in projects if item.stage == "Fechado"]
        delivered_projects = [item for item in projects if item.stage == "Entregue"]
        prospects = list(Prospect.objects.filter(workspace=workspace))
    else:
        active_projects = [
            item
            for item in projects
            if item.stage == "Fechado" and _project_matches_contract_month(item, selected_month)
        ]
        delivered_projects = [
            item
            for item in projects
            if item.stage == "Entregue" and _project_matches_contract_month(item, selected_month)
        ]
        prospects = list(
            Prospect.objects.filter(
                workspace=workspace,
                contact_date__year=selected_month.year,
                contact_date__month=selected_month.month,
            )
        )

    # Brief Dash Creator 6.3: Trabalhos Ativos conta projetos (não soma
    # deliverables_count) e Carteira só considera quem tem trabalho cadastrado
    # (não inclui prospects). Contratos recorrentes contam em cada mes da
    # duracao configurada.
    active_jobs = len(active_projects)
    company_names = set()
    for item in active_projects + delivered_projects:
        normalized_name = normalize_company_name(item.company)
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
        _project_dashboard_revenue_for_month(item, selected_month)
        for item in projects
        if item.stage in {"Fechado", "Entregue"}
    )
    total_closed = sum_money(_project_cash_value(item) for item in active_projects)

    open_prospection_stages = {"Rascunho", "Prospeccao", "Aguardando retorno"}
    pipeline = [
        {"stage": "Prospecção", "count": sum(1 for item in prospects if item.stage in open_prospection_stages), "amount_text": "", "icon_label": "P", "accent": "#4d8cff", "progress": 54},
        {"stage": "Negociação", "count": sum(1 for item in prospects if item.stage == "Negociacao"), "amount_text": "", "icon_label": "N", "accent": "#4d8cff", "progress": 33},
        {"stage": "Fechado", "count": len(active_projects), "amount_text": currency(total_closed), "icon_label": "F", "accent": "#2fb9ac", "progress": 72 if total_closed else 0},
        {"stage": "Entregue", "count": sum(item.deliverables_count for item in delivered_projects[:4]), "amount_text": currency(sum_money(_project_cash_value(item) for item in delivered_projects[:4])), "icon_label": "E", "accent": "#aeb9c9", "progress": 59 if delivered_projects else 0},
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
            {"title": "Carteira de clientes", "value": str(clients_portfolio), "icon_label": "C", "icon": "users"},
            {"title": "Carteira ativa", "value": str(active_companies), "icon_label": "E", "icon": "star"},
            {"title": "Trabalhos ativos", "value": str(active_jobs), "icon_label": "T", "icon": "briefcase"},
            {"title": "Faturamento mensal", "value": currency(monthly_revenue), "icon_label": "$", "icon": "money", "tone": "success"},
        ],
        "month_choices": month_choice_payload(month_options),
        "selected_month": selected_month_payload(selected_month),
        "revenue": revenue_context(projects, selected_month.year if selected_month else None),
        "pipeline": pipeline,
        "activities": activities,
        "featured": featured,
    }


PIPELINE_STAGES = [
    ("Rascunho", "Rascunho", "draft"),
    ("Prospeccao", "Prospecção", "prospect"),
    ("Aguardando retorno", "Ag. retorno", "waiting"),
    ("Negociacao", "Negociação", "negotiation"),
    ("Fechado", "Fechados ✓", "closed"),
]


def _prospect_last_activity(item: Prospect) -> date:
    if item.last_activity_at:
        return item.last_activity_at.date()
    return item.contact_date or item.updated_at.date() if item.updated_at else item.created_at.date()


def auto_archive_stale_prospects(workspace: Workspace, today: date | None = None) -> int:
    """Move leads em Prospecção/Aguardando retorno parados +30 dias pro Banco
    de Marcas com status 'Sem retorno'. Roda preguiçosamente toda vez que o
    usuário abre a página."""
    from django.utils import timezone as _tz
    from .constants import PROSPECT_AUTO_ARCHIVE_DAYS
    today = today or date.today()
    cutoff = today - timedelta(days=PROSPECT_AUTO_ARCHIVE_DAYS)
    moved = 0
    qs = Prospect.objects.filter(
        workspace=workspace,
        archive_reason="",
        stage__in=["Prospeccao", "Aguardando retorno"],
    )
    for item in qs:
        if _prospect_last_activity(item) <= cutoff:
            item.archive_reason = "sem_retorno"
            item.archived_at = _tz.now()
            item.save(update_fields=["archive_reason", "archived_at", "updated_at"])
            moved += 1
    return moved


def _serialize_pipeline_prospect(item: Prospect) -> dict:
    today = date.today()
    last = _prospect_last_activity(item)
    days_since = (today - last).days
    color_a, color_b, accent = company_palette(item.company)
    channel = item.channel or ""
    if not channel:
        if item.instagram:
            channel = "Instagram DM"
        elif item.email:
            channel = "Email"
        elif item.whatsapp:
            channel = "WhatsApp"
    return {
        "id": item.id,
        "company": item.company,
        "contact": item.contact,
        "niche": item.niche.name if item.niche_id else "",
        "channel": channel,
        "instagram": item.instagram,
        "contact_date": short_date(item.contact_date) if item.contact_date else "",
        "meeting_date": short_date(item.meeting_date) if item.meeting_date else "",
        "note": item.note,
        "stage": item.stage,
        "days_since_last": days_since,
        "is_stale": days_since >= 28 and item.stage in {"Prospeccao", "Aguardando retorno"},
        "proposal_value": item.proposal_value,
        "accent": accent,
    }


def _serialize_archived_prospect(item: Prospect) -> dict:
    from .constants import PROSPECT_ARCHIVE_LABELS
    channel = item.channel or ("Instagram DM" if item.instagram else ("Email" if item.email else ""))
    return {
        "id": item.id,
        "company": item.company,
        "instagram": item.instagram,
        "niche": item.niche.name if item.niche_id else "",
        "channel": channel,
        "last_contact": short_date(item.contact_date) if item.contact_date else (short_date(item.archived_at.date()) if item.archived_at else ""),
        "status_key": item.archive_reason,
        "status_label": PROSPECT_ARCHIVE_LABELS.get(item.archive_reason, item.archive_reason),
    }


def prospection_snapshot(workspace: Workspace, month_filter: str | None = None, search: str | None = None) -> dict:
    auto_archive_stale_prospects(workspace)

    month_options = month_options_for_workspace(workspace)
    selected_month = resolve_selected_month(month_filter, month_options)
    search_term = (search or "").strip()
    normalized_search = search_term.casefold() if search_term else ""

    all_prospects = list(Prospect.objects.filter(workspace=workspace).select_related("niche"))

    def matches_month(item: Prospect) -> bool:
        if selected_month is None:
            return True
        target = _prospect_last_activity(item)
        return target.year == selected_month.year and target.month == selected_month.month

    def matches_search(company: str) -> bool:
        return (not normalized_search) or (normalized_search in (company or "").casefold())

    active = [p for p in all_prospects if not p.archive_reason and matches_month(p) and matches_search(p.company)]
    archived = [p for p in all_prospects if p.archive_reason and matches_search(p.company)]

    # KPIs do pipeline (todos abordados = ativos + arquivados; fechados = arquivo "fechado")
    total_addressed = len([p for p in all_prospects if matches_search(p.company)])
    total_closed = len([p for p in all_prospects if p.archive_reason == "fechado" and matches_search(p.company)])
    total_no_response = len([p for p in all_prospects if p.archive_reason == "sem_retorno" and matches_search(p.company)])
    conversion_rate = round((total_closed / total_addressed) * 100) if total_addressed else 0

    pipeline_columns = []
    visible_per_column = 2
    for stage_key, stage_label, stage_tone in PIPELINE_STAGES:
        if stage_key == "Fechado":
            items_raw = [p for p in all_prospects if p.archive_reason == "fechado" and matches_search(p.company)]
        else:
            items_raw = [p for p in active if p.stage == stage_key]
        items_raw.sort(key=lambda p: _prospect_last_activity(p), reverse=True)
        total = len(items_raw)
        items = [_serialize_pipeline_prospect(p) for p in items_raw[:visible_per_column]]
        overflow = max(total - visible_per_column, 0)
        pipeline_columns.append({
            "key": stage_key,
            "title": stage_label,
            "tone": stage_tone,
            "count": total,
            "items": items,
            "overflow": overflow,
        })

    stale_alert = [_serialize_pipeline_prospect(p) for p in active if (date.today() - _prospect_last_activity(p)).days >= 28 and p.stage in {"Prospeccao", "Aguardando retorno"}]

    archived_sorted = sorted(archived, key=lambda p: p.archived_at or p.updated_at, reverse=True)
    archived_rows = [_serialize_archived_prospect(p) for p in archived_sorted]

    return {
        "pipeline_stages": [
            {
                "key": col["key"],
                "title": col["title"],
                "tone": col["tone"],
                "count": col["count"],
            }
            for col in pipeline_columns
        ],
        "pipeline_columns": pipeline_columns,
        "conversion_rate": conversion_rate,
        "conversion_text": f"{total_closed} fechados de {total_addressed} abordagens",
        "total_addressed": total_addressed,
        "total_closed": total_closed,
        "total_no_response": total_no_response,
        "stale_alert": stale_alert,
        "archived_rows": archived_rows,
        "filters": {"search": search_term},
        "month_choices": month_choice_payload(month_options),
        "selected_month": selected_month_payload(selected_month),
        # legados pra não quebrar templates antigos / testes
        "stats": [
            {"title": "Rascunho", "value": str(sum(1 for p in active if p.stage == "Rascunho")), "icon_label": "R"},
            {"title": "Prospecção", "value": str(sum(1 for p in active if p.stage == "Prospeccao")), "icon_label": "P"},
            {"title": "Aguardando retorno", "value": str(sum(1 for p in active if p.stage == "Aguardando retorno")), "icon_label": "A"},
            {"title": "Negociação", "value": str(sum(1 for p in active if p.stage == "Negociacao")), "icon_label": "N"},
        ],
        "columns": [],  # legado
    }


def empresas_snapshot(
    workspace: Workspace,
    projects: list[Project] | None = None,
    overdue_projects: list[Project] | None = None,
    upcoming_projects: list[Project] | None = None,
    selected_month: date | None = None,
) -> dict:
    if projects is None:
        projects = list(
            Project.objects.filter(workspace=workspace)
            .select_related("service_category", "niche")
            .order_by("due_date")
        )
    active = [item for item in projects if item.stage == "Fechado"]
    today = date.today()
    upcoming_limit = today + timedelta(days=21)

    def serialize_job_card(item: Project) -> dict:
        color_a, color_b, accent = company_palette(item.company)
        expires_on = image_usage_expires_on(item)
        contact_url = whatsapp_contact_url(item.company_phone)
        days_overdue = (today - item.due_date).days if project_counts_as_overdue(item, today) else 0
        payment_due_date = item.payment_due_date
        if selected_month is not None and _project_contract_month_count(item) > 1:
            payment_due_date = (
                _date_in_month_with_day(selected_month, _project_recurring_payment_day(item))
                if _project_matches_recurring_payment_month(item, selected_month)
                else None
            )
        return {
            "id": item.id,
            "company": item.company,
            "service_category": item.service_category_name,
            "status": item.status,
            "total_value": currency(item.total_value),
            "progress": item.progress,
            "due_text": short_date(item.due_date),
            "payment_due_text": short_date(payment_due_date) if payment_due_date else "",
            "meeting_date_text": short_date(item.meeting_date) if item.meeting_date else "",
            "meeting_scheduled": item.meeting_scheduled,
            "distribution_text": distribution_label(item),
            "image_license_term_text": image_usage_term_label(item),
            "image_usage_expires_text": short_date(expires_on) if expires_on else "",
            "google_calendar_url": google_calendar_event_url(
                f"Reunião - {item.company}",
                item.meeting_date,
                f"Reunião agendada do trabalho {item.service_category_name} com {item.company}.",
            )
            if item.meeting_scheduled and item.meeting_date
            else "",
            "contact_url": contact_url,
            "days_overdue": days_overdue,
            "note": item.note,
            "colors": (color_a, color_b),
            "accent": accent,
            "stage": item.stage,
            "close_date": item.close_date,
            "due_date": item.due_date,
        }

    cards = [serialize_job_card(item) for item in projects]
    overdue_source = overdue_projects if overdue_projects is not None else [item for item in active if project_counts_as_overdue(item, today)]
    overdue_cards = [serialize_job_card(item) for item in overdue_source]

    active_cards = [item for item in cards if item["stage"] == "Fechado"]
    approval_cards = [item for item in active_cards if item["status"] == "Aguardando aprovação"]
    if upcoming_projects is not None:
        upcoming_cards = [serialize_job_card(item) for item in upcoming_projects]
    else:
        upcoming_cards = [
            item for item in active_cards
            if today <= item["due_date"] <= upcoming_limit
        ]
        if selected_month is not None:
            upcoming_cards = [
                item for item in upcoming_cards
                if item["due_date"].year == selected_month.year and item["due_date"].month == selected_month.month
            ]
    delivered_cards = sorted(
        [item for item in cards if item["stage"] == "Entregue"],
        key=lambda item: (item["due_date"], item["close_date"]),
        reverse=True,
    )
    upcoming_deliveries = len(upcoming_cards)
    delivered_count = len(delivered_cards)
    return {
        "stats": [
            {"title": "Trabalhos atrasados", "value": str(len(overdue_cards)), "icon_label": "!", "icon": "alert", "tone": "danger", "modal_id": "jobs-kpi-overdue"},
            {"title": "Aguardando aprovação", "value": str(len(approval_cards)), "icon_label": "A", "icon": "clock", "tone": "info", "modal_id": "jobs-kpi-approval"},
            {"title": "Entregas próximas", "value": str(upcoming_deliveries), "icon_label": "P", "icon": "calendar", "tone": "warning", "modal_id": "jobs-kpi-upcoming"},
            {"title": "Finalizado", "value": str(delivered_count), "icon_label": "F", "icon": "check", "tone": "success", "modal_id": "jobs-kpi-delivered"},
        ],
        "stat_lists": [
            {
                "modal_id": "jobs-kpi-overdue",
                "title": "Trabalhos atrasados",
                "description": "Entregas que já passaram da data e ainda precisam de atenção.",
                "items": sorted(overdue_cards, key=lambda item: item["due_date"]),
                "empty_message": "Nenhum trabalho atrasado no momento.",
            },
            {
                "modal_id": "jobs-kpi-approval",
                "title": "Aguardando aprovação",
                "description": "Jobs esperando retorno da marca para seguir.",
                "items": approval_cards,
                "empty_message": "Nenhum trabalho aguardando aprovação.",
            },
            {
                "modal_id": "jobs-kpi-upcoming",
                "title": "Entregas próximas",
                "description": "Trabalhos com entrega prevista para os próximos dias.",
                "items": sorted(upcoming_cards, key=lambda item: item["due_date"]),
                "empty_message": "Nenhuma entrega próxima cadastrada.",
            },
            {
                "modal_id": "jobs-kpi-delivered",
                "title": "Finalizado",
                "description": "Trabalhos ja entregues para consulta rapida.",
                "items": delivered_cards,
                "empty_message": "Nenhum trabalho finalizado ainda.",
            },
        ],
        "overdue": sorted(
            overdue_cards,
            key=lambda item: item["due_date"],
        ),
        "active": active_cards,
        "delivered": delivered_cards[:4],
    }


def jobs_snapshot(workspace: Workspace) -> dict:
    return jobs_snapshot_filtered(workspace)


def jobs_snapshot_filtered(
    workspace: Workspace,
    service_category_filter: str | None = None,
    progress_filter: str | None = None,
    niche_filter: str | None = None,
    search: str | None = None,
    month_filter: str | None = None,
) -> dict:
    month_options = month_options_for_workspace(workspace)
    selected_month = resolve_selected_month(month_filter, month_options)
    base_projects_query = Project.objects.filter(workspace=workspace).select_related("service_category", "niche")
    projects_query = base_projects_query

    if service_category_filter and service_category_filter.isdigit():
        projects_query = projects_query.filter(service_category_id=int(service_category_filter))

    if progress_filter == "andamento":
        projects_query = projects_query.filter(stage="Fechado")
    elif progress_filter == "entregue":
        projects_query = projects_query.filter(stage="Entregue")

    if niche_filter and niche_filter.isdigit():
        projects_query = projects_query.filter(niche_id=int(niche_filter))

    search_term = (search or "").strip()
    if search_term:
        projects_query = projects_query.filter(
            Q(company__icontains=search_term)
            | Q(service_category__name__icontains=search_term)
            | Q(project_name__icontains=search_term)
        )

    overdue_projects_query = projects_query if progress_filter != "entregue" else projects_query.none()
    upcoming_projects_query = projects_query if progress_filter != "entregue" else projects_query.none()
    if selected_month is not None:
        upcoming_projects_query = upcoming_projects_query.filter(
            due_date__year=selected_month.year,
            due_date__month=selected_month.month,
        )

    filtered_projects = list(projects_query.order_by("due_date"))
    if selected_month is not None:
        filtered_projects = [
            item
            for item in filtered_projects
            if _project_matches_contract_month(item, selected_month)
        ]
    overdue_projects = list(
        overdue_projects_query.filter(stage="Fechado", due_date__lt=date.today())
        .exclude(status__in=OVERDUE_EXCLUDED_STATUSES)
        .order_by("due_date")
    )
    upcoming_limit = date.today() + timedelta(days=21)
    upcoming_projects = list(
        upcoming_projects_query.filter(stage="Fechado", due_date__gte=date.today(), due_date__lte=upcoming_limit).order_by("due_date")
    )
    snapshot = empresas_snapshot(
        workspace,
        filtered_projects,
        overdue_projects=overdue_projects,
        upcoming_projects=upcoming_projects,
        selected_month=selected_month,
    )
    snapshot["source_mix"] = closing_source_mix(filtered_projects)
    snapshot["month_choices"] = month_choice_payload(month_options)
    snapshot["selected_month"] = selected_month_payload(selected_month)
    snapshot["filters"] = {
        "service_category": service_category_filter or "",
        "progress": progress_filter or "",
        "niche": niche_filter or "",
        "search": search_term,
        "service_categories": [
            {"value": str(item.pk), "label": item.name}
            for item in ServiceCategory.objects.filter(workspace=workspace).order_by("name")
        ],
        "niches": [
            {"value": str(item.pk), "label": item.name}
            for item in default_niche_list(workspace)
        ],
    }
    return snapshot


def distribution_snapshot(workspace: Workspace) -> dict:
    projects = list(
        Project.objects.filter(workspace=workspace)
        .select_related("service_category", "niche")
        .order_by("-updated_at", "-due_date")
    )
    grouped = {"Orgânico": [], "Ads": [], "Não se aplica": [], "Não definido": []}
    for project in projects:
        color_a, color_b, accent = company_palette(project.company)
        expires_on = image_usage_expires_on(project)
        bucket = distribution_label(project)
        grouped.setdefault(bucket, [])
        grouped[bucket].append(
            {
                "id": project.id,
                "company": project.company,
                "service_category": project.service_category_name,
                "distribution": bucket,
                "delivery_text": short_date(project.due_date),
                "term_text": image_usage_term_label(project),
                "expires_text": short_date(expires_on) if expires_on else "",
                "accent": accent,
                "colors": (color_a, color_b),
            }
        )

    ads_count = len(grouped["Ads"])
    organic_count = len(grouped["Orgânico"])
    return {
        "stats": [
            {"title": "Ads", "value": str(ads_count), "icon_label": "A", "icon": "monitor"},
            {"title": "Orgânico", "value": str(organic_count), "icon_label": "O", "icon": "edit"},
            {"title": "Licenciamento ativo", "value": str(sum(1 for item in legal_usage_items(workspace) if item["days_until_expiry"] >= 0)), "icon_label": "L", "icon": "shield"},
            {"title": "Vence hoje", "value": str(sum(1 for item in legal_usage_items(workspace) if item["days_until_expiry"] == 0)), "icon_label": "!", "icon": "clock", "tone": "warning"},
        ],
        "columns": [
            {"title": "Ads", "items": grouped["Ads"]},
            {"title": "Orgânico", "items": grouped["Orgânico"]},
            {"title": "Não se aplica", "items": grouped["Não se aplica"]},
            {"title": "Não definido", "items": grouped["Não definido"]},
        ],
    }


def legal_snapshot(workspace: Workspace, user: User | None = None) -> dict:
    items = legal_usage_items(workspace, user)
    contract_items = legal_contract_items(workspace)
    expiring_today = [item for item in items if item["days_until_expiry"] == 0]
    expiring_soon = [item for item in items if 0 < item["days_until_expiry"] <= 30]
    expired = [item for item in items if item["days_until_expiry"] < 0]
    active = [item for item in items if item["days_until_expiry"] >= 0]
    return {
        "stats": [
            {"title": "Contratos", "value": str(len(contract_items)), "icon_label": "C", "icon": "doc"},
            {"title": "Licenças ativas", "value": str(len(active)), "icon_label": "L", "icon": "shield"},
            {"title": "Vencendo hoje", "value": str(len(expiring_today)), "icon_label": "!", "icon": "clock", "tone": "danger"},
            {"title": "Próximos 30 dias", "value": str(len(expiring_soon)), "icon_label": "30", "icon": "alert", "tone": "warning"},
            {"title": "Expirados", "value": str(len(expired)), "icon_label": "E", "icon": "ban"},
        ],
        "contracts": contract_items,
        "records": items,
    }


def _project_installment_list(project: Project) -> list[ProjectInstallment]:
    cached = getattr(project, "_prefetched_objects_cache", {}).get("installments")
    if cached is not None:
        return list(cached)
    return list(project.installments.all())


def _project_finance_events(project: Project) -> list[dict]:
    installments = _project_installment_list(project)
    if installments:
        return [
            {
                "project": project,
                "kind": "Parcela",
                "amount": Decimal(item.amount or 0),
                "due_date": item.due_date,
                "paid": item.paid,
                "paid_on": item.paid_on or item.due_date,
            }
            for item in installments
            if Decimal(item.amount or 0) > ZERO
        ]

    events = []
    if _project_contract_month_count(project) > 1:
        monthly_amount = _project_monthly_contract_value(project)
        if monthly_amount <= ZERO:
            return events
        for index, payment_date in enumerate(_project_recurring_payment_dates(project), start=1):
            is_paid = payment_date <= date.today()
            if is_paid:
                events.append(
                    {
                        "project": project,
                        "kind": f"Mensalidade {index}",
                        "amount": monthly_amount,
                        "due_date": payment_date,
                        "paid": True,
                        "paid_on": payment_date,
                    }
                )
            else:
                events.append(
                    {
                        "project": project,
                        "kind": f"Mensalidade {index}",
                        "amount": monthly_amount,
                        "due_date": payment_date,
                        "paid": False,
                        "paid_on": None,
                    }
                )
        return events

    payment_date = payment_reference_date(project)
    total_amount = _project_cash_value(project)
    received_amount = min(Decimal(project.received_value or 0), total_amount)
    outstanding_amount = max(total_amount - received_amount, ZERO)
    if received_amount > ZERO:
        events.append(
            {
                "project": project,
                "kind": "Entrada",
                "amount": received_amount,
                "due_date": payment_date,
                "paid": True,
                "paid_on": payment_date,
            }
        )
    if outstanding_amount > ZERO:
        events.append(
            {
                "project": project,
                "kind": "Saldo" if received_amount > ZERO else "Entrada",
                "amount": outstanding_amount,
                "due_date": payment_date,
                "paid": False,
                "paid_on": None,
            }
        )
    return events


def _finance_event_reference_date(event: dict) -> date:
    return event["paid_on"] if event["paid"] and event["paid_on"] else event["due_date"]


def _fixed_cost_due_text(item: FixedCost) -> str:
    day = f"{item.due_day:02d}"
    if item.recurrence == FixedCost.RECURRENCE_ANNUAL:
        month_label = item.get_due_month_display()
        return f"Vence dia {day} de {month_label}, todo ano"
    return f"Vence dia {day} todo mês"


def finance_snapshot(workspace: Workspace, month_filter: str | None = None) -> dict:
    projects = list(Project.objects.filter(workspace=workspace).prefetch_related("installments").order_by("payment_due_date", "due_date"))
    finance_entries = list(
        FinanceEntry.objects.filter(workspace=workspace, kind=FinanceEntry.KIND_OUTGOING).order_by("-occurred_on", "-updated_at")
    )
    month_options = month_options_for_workspace(workspace)
    selected_month = resolve_selected_month(month_filter, month_options)
    finance_events = [event for project in projects for event in _project_finance_events(project)]
    month_events = (
        finance_events
        if selected_month is None
        else [
            item
            for item in finance_events
            if _finance_event_reference_date(item).year == selected_month.year
            and _finance_event_reference_date(item).month == selected_month.month
        ]
    )
    month_entries = (
        finance_entries
        if selected_month is None
        else [
            item for item in finance_entries if item.occurred_on.year == selected_month.year and item.occurred_on.month == selected_month.month
        ]
    )
    confirmed_incoming_events = [item for item in month_events if item["paid"]]
    incoming_total = sum_money(item["amount"] for item in confirmed_incoming_events)
    outgoing_total = sum_money(item.amount for item in month_entries)
    # "A receber" abrange todos os recebíveis futuros (em qualquer mês),
    # não apenas o mês filtrado, para refletir o caixa que ainda vai
    # entrar — incluindo parcelas mensais de contratos plurimensais.
    receivable_events = [
        item
        for item in finance_events
        if not item["paid"] and item["due_date"] >= date.today()
    ]
    receivable_balance = sum_money(item["amount"] for item in receivable_events)
    cash_balance = incoming_total - outgoing_total

    schedule = []
    for item in sorted(receivable_events, key=lambda event: (event["due_date"], event["project"].company.casefold())):
        project = item["project"]
        _, _, accent = company_palette(project.company)
        schedule.append(
            {
                "company": project.company,
                "kind": item["kind"],
                "due": short_date(item["due_date"]),
                "amount": currency(item["amount"]),
                "status": "Previsto",
                "accent": accent,
            }
        )

    ledger = [
        {
            "label": "Entrada",
            "description": f"Recebido no trabalho de {item['project'].company}",
            "date_text": short_date(_finance_event_reference_date(item)),
            "amount_text": currency(item["amount"]),
            "accent": "#20b7a7",
            "kind": "incoming",
            "entry_id": None,
            "can_edit": False,
            "sort_date": _finance_event_reference_date(item),
        }
        for item in confirmed_incoming_events
    ]
    ledger.extend(
        {
            "label": "Saida",
            "description": item.description or "Despesa / investimento",
            "date_text": short_date(item.occurred_on),
            "amount_text": currency(item.amount),
            "accent": "#c04d57",
            "kind": item.kind,
            "entry_id": item.pk,
            "can_edit": True,
            "sort_date": item.occurred_on,
        }
        for item in month_entries
    )
    ledger.sort(key=lambda item: item["sort_date"], reverse=True)
    for item in ledger:
        item.pop("sort_date", None)

    workspace_settings = settings_map(workspace)
    pro_labore_amount = _decimal_setting(workspace_settings, "ops_pro_labore_amount", Decimal("5000"))
    fixed_costs = list(FixedCost.objects.filter(workspace=workspace).order_by("kind", "name", "pk"))
    cash_boxes = list(CashBox.objects.filter(workspace=workspace).order_by("name", "pk"))
    fixed_tools = [item for item in fixed_costs if item.kind == FixedCost.KIND_TOOL]
    fixed_collaborators = [item for item in fixed_costs if item.kind == FixedCost.KIND_COLLABORATOR]
    # Custos anuais entram no total como 1/12 do valor anual, para
    # refletir o quanto precisa ser reservado por mês.
    fixed_tools_amount = sum((item.monthly_equivalent() for item in fixed_tools), ZERO)
    fixed_collaborators_amount = sum((item.monthly_equivalent() for item in fixed_collaborators), ZERO)
    fixed_cost_amount = fixed_tools_amount + fixed_collaborators_amount
    fixed_cost_remaining = max(fixed_cost_amount - incoming_total, ZERO)
    fixed_cost_covered = fixed_cost_remaining == ZERO
    pro_labore_available = max(incoming_total - fixed_cost_amount, ZERO)
    pro_labore_remaining = max(pro_labore_amount - pro_labore_available, ZERO)
    pro_labore_covered = pro_labore_remaining == ZERO
    distribution_remaining = max(pro_labore_amount + fixed_cost_amount - incoming_total, ZERO)
    distribution_complete = distribution_remaining == ZERO
    if not fixed_cost_covered:
        distribution_pending_text = f"faltam {currency(fixed_cost_remaining)} para cobrir o custo fixo"
    else:
        distribution_pending_text = f"faltam {currency(pro_labore_remaining)} para cobrir o pró-labore"
    distribution_base = max(incoming_total - pro_labore_amount - fixed_cost_amount, ZERO)
    reserve_config = CASH_BOX_ALLOCATION_SETTINGS["reserve"]
    investment_config = CASH_BOX_ALLOCATION_SETTINGS["investment"]
    reserve_percentage = _decimal_setting(
        workspace_settings,
        reserve_config["key"],
        Decimal(reserve_config["default"]),
    )
    investment_percentage = _decimal_setting(
        workspace_settings,
        investment_config["key"],
        Decimal(investment_config["default"]),
    )
    reserve_amount = (distribution_base * reserve_percentage / Decimal("100")).quantize(Decimal("0.01"))
    investment_amount = (distribution_base * investment_percentage / Decimal("100")).quantize(Decimal("0.01"))
    free_flow_base = max(distribution_base - reserve_amount - investment_amount, ZERO)
    custom_boxes_total = ZERO
    custom_box_items = []
    for box in cash_boxes:
        percentage = Decimal(box.allocation_percentage or 0)
        amount = (free_flow_base * percentage / Decimal("100")).quantize(Decimal("0.01"))
        percentage_text = f"{int(percentage)}%" if percentage == percentage.to_integral() else f"{percentage}%"
        custom_boxes_total += amount
        custom_box_items.append(
            {
                "id": box.pk,
                "name": box.name,
                "icon": box.icon or "ti-pig-money",
                "description": box.description or f"{percentage_text} do fluxo livre",
                "percentage": percentage_text,
                "amount": currency(amount),
                "progress": min(100, int(round(percentage))),
            }
        )
    free_flow_amount = max(free_flow_base - custom_boxes_total, ZERO)
    reserve_goal = Decimal("30000")
    reserve_progress = min(100, round((reserve_amount / reserve_goal) * 100)) if reserve_goal and reserve_amount else 0

    incoming_items = [
        {
            "company": item["project"].company,
            "detail": f"{short_date(_finance_event_reference_date(item))} · {item['kind']} · {item['project'].service_category_name}",
            "amount_text": f"+{currency(item['amount'])}",
            "status": "Recebido",
        }
        for item in confirmed_incoming_events
    ]
    outgoing_items = [
        {
            "id": item.pk,
            "description": item.description or "Despesa / investimento",
            "detail": f"{short_date(item.occurred_on)} · Saída avulsa",
            "amount_text": f"−{currency(item.amount)}",
        }
        for item in sorted(month_entries, key=lambda entry: entry.occurred_on, reverse=True)
    ]
    latest_movements = []
    for item in ledger[:5]:
        if item["kind"] == "incoming":
            latest_movements.append(
                {
                    "tone": "up",
                    "name": item["description"].replace("Recebido no trabalho de ", ""),
                    "detail": f"{item['date_text']} · {item['label']}",
                    "amount_text": f"+{item['amount_text']}",
                }
            )
        else:
            latest_movements.append(
                {
                    "tone": "down",
                    "name": item["description"],
                    "detail": f"{item['date_text']} · Saída",
                    "amount_text": f"−{item['amount_text']}",
                }
            )

    return {
        "month_choices": month_choice_payload(month_options),
        "selected_month": selected_month_payload(selected_month),
        "stats": [
            {"title": "Entradas", "value": currency(incoming_total), "icon_label": "+"},
            {"title": "Saídas", "value": currency(outgoing_total), "icon_label": "-"},
            {"title": "Saldo de recebíveis", "value": currency(receivable_balance), "icon_label": "R"},
            {"title": "Saldo", "value": currency(cash_balance), "icon_label": "$"},
        ],
        "schedule": schedule,
        "ledger": ledger,
        "finance_desktop": {
            "revenue_total": currency(incoming_total),
            "outgoing_total": currency(outgoing_total),
            "receivable_total": currency(receivable_balance),
            "cash_balance": currency(cash_balance),
            "pro_labore": currency(pro_labore_amount),
            "pro_labore_covered": pro_labore_covered,
            "pro_labore_remaining": currency(pro_labore_remaining),
            "pro_labore_status_text": "Coberto" if pro_labore_covered else f"Faltam {currency(pro_labore_remaining)}",
            "distribution_complete": distribution_complete,
            "fixed_cost_covered": fixed_cost_covered,
            "fixed_cost": currency(fixed_cost_amount),
            "fixed_cost_remaining": currency(fixed_cost_remaining),
            "fixed_cost_status_text": "Coberto" if fixed_cost_covered else f"Faltam {currency(fixed_cost_remaining)}",
            "distribution_pending_text": distribution_pending_text,
            "distribution_base": currency(distribution_base),
            "reserve": currency(reserve_amount),
            "reserve_percentage": _percentage_text(reserve_percentage),
            "reserve_progress": reserve_progress,
            "investment": currency(investment_amount),
            "investment_percentage": _percentage_text(investment_percentage),
            "custom_boxes": custom_box_items,
            "custom_boxes_total": currency(custom_boxes_total),
            "free_flow_base": currency(free_flow_base),
            "free_flow": currency(free_flow_amount),
            "incoming_items": incoming_items,
            "outgoing_items": outgoing_items,
            "latest_movements": latest_movements,
            "fixed_tools": [
                {
                    "id": item.pk,
                    "icon": item.icon or "ti-tool",
                    "name": item.name,
                    "due": _fixed_cost_due_text(item),
                    "amount": currency(item.amount),
                    "recurrence_label": item.get_recurrence_display(),
                }
                for item in fixed_tools
            ],
            "fixed_collaborators": [
                {
                    "id": item.pk,
                    "icon": item.icon or "ti-user",
                    "name": item.name,
                    "due": _fixed_cost_due_text(item),
                    "amount": currency(item.amount),
                    "recurrence_label": item.get_recurrence_display(),
                }
                for item in fixed_collaborators
            ],
            "fixed_tools_total": currency(fixed_tools_amount),
            "fixed_collaborators_total": currency(fixed_collaborators_amount),
        },
        "breakdown": [
            {"label": "Entradas dos trabalhos", "amount_text": currency(incoming_total), "progress": 100 if incoming_total else 0, "accent": "#20b7a7"},
            {"label": "Saídas registradas", "amount_text": currency(outgoing_total), "progress": round((outgoing_total / incoming_total) * 100) if incoming_total else 0, "accent": "#c04d57"},
            {"label": "Saldo de recebíveis", "amount_text": currency(receivable_balance), "progress": round((receivable_balance / (incoming_total + receivable_balance)) * 100) if (incoming_total + receivable_balance) else 0, "accent": "#7f6fff"},
            {"label": "Saldo do período", "amount_text": currency(cash_balance), "progress": round((cash_balance / incoming_total) * 100) if incoming_total and cash_balance > 0 else 0, "accent": "#4d8cff"},
        ],
    }


def _format_currency_delta(current: Decimal, previous: Decimal) -> dict | None:
    if not previous:
        return None
    delta = current - previous
    if delta == 0:
        return {"direction": "flat", "label": "estável vs mês anterior"}
    sign = "↑" if delta > 0 else "↓"
    return {
        "direction": "up" if delta > 0 else "down",
        "label": f"{sign} {currency(abs(delta))} vs mês anterior",
    }


def _format_count_delta(current: int, previous: int, noun: str = "trabalhos") -> dict | None:
    if not previous and not current:
        return None
    delta = current - previous
    if delta == 0:
        return {"direction": "flat", "label": "estável vs mês anterior"}
    sign = "↑" if delta > 0 else "↓"
    return {
        "direction": "up" if delta > 0 else "down",
        "label": f"{sign} {abs(delta)} {noun} vs mês anterior",
    }


def reports_snapshot(
    workspace: Workspace,
    month_filter: str | None = None,
    service_type_filter: str | None = None,
) -> dict:
    projects = list(Project.objects.filter(workspace=workspace))
    month_options = month_options_for_workspace(workspace)
    selected_month = resolve_selected_month(month_filter, month_options)

    def filter_by_month(items: list[Project], month: date | None, attr: str) -> list[Project]:
        if month is None:
            return items
        result = []
        for item in items:
            value = getattr(item, attr, None)
            if value is None:
                continue
            ref = value.date() if hasattr(value, "date") else value
            if ref.year == month.year and ref.month == month.month:
                result.append(item)
        return result

    all_month_projects = filter_by_month(projects, selected_month, "close_date")
    cadastrados_in_month = len(filter_by_month(projects, selected_month, "created_at"))

    # Distribuição por tipo de serviço (brief 5.2): tabela calculada SEMPRE
    # sobre o conjunto completo do mês, independente do filtro de sub-tab.
    type_label_lookup = dict(SERVICE_TYPE_CHOICES)
    type_buckets: dict[str, dict] = {}
    for item in all_month_projects:
        key = item.service_type or "outros"
        bucket = type_buckets.setdefault(key, {"count": 0, "revenue": ZERO})
        bucket["count"] += 1
        bucket["revenue"] += Decimal(item.total_value or 0)

    distribution_total_count = sum(b["count"] for b in type_buckets.values())
    distribution_total_revenue = sum_money(b["revenue"] for b in type_buckets.values())
    distribution_table = []
    for key in sorted(type_buckets, key=lambda k: -type_buckets[k]["revenue"]):
        bucket = type_buckets[key]
        ticket = bucket["revenue"] / bucket["count"] if bucket["count"] else ZERO
        distribution_table.append({
            "key": key,
            "label": type_label_lookup.get(key, key),
            "revenue": currency(bucket["revenue"]),
            "count": bucket["count"],
            "ticket_medio": currency(ticket),
        })
    distribution_table_total = {
        "count": distribution_total_count,
        "revenue": currency(distribution_total_revenue),
        "ticket_medio": currency(distribution_total_revenue / distribution_total_count) if distribution_total_count else currency(ZERO),
    }

    # Filtro de sub-tab (Geral mostra tudo; outros tipos restringem stats).
    active_type = service_type_filter if service_type_filter and service_type_filter != "geral" else None
    if active_type:
        month_projects = [item for item in all_month_projects if (item.service_type or "outros") == active_type]
    else:
        month_projects = all_month_projects

    # Sub-tabs disponíveis: Geral + cada tipo com pelo menos 1 trabalho no mês.
    service_type_tabs = [{
        "key": "geral",
        "label": "Geral",
        "count": distribution_total_count,
        "active": active_type is None,
    }]
    for entry in distribution_table:
        service_type_tabs.append({
            "key": entry["key"],
            "label": entry["label"],
            "count": entry["count"],
            "active": active_type == entry["key"],
        })

    volume = len(month_projects)
    total_closed = sum_money(item.total_value for item in month_projects)
    paid_closures = [item for item in month_projects if item.total_value]
    ticket_medio = total_closed / len(paid_closures) if paid_closures else ZERO
    selected_month_label = "todos os meses" if selected_month is None else long_month_label(selected_month)

    previous_month = _shift_month(selected_month, -1) if selected_month else None
    prev_all_month_projects = filter_by_month(projects, previous_month, "close_date") if previous_month else []
    if active_type:
        prev_month_projects = [item for item in prev_all_month_projects if (item.service_type or "outros") == active_type]
    else:
        prev_month_projects = prev_all_month_projects
    prev_volume = len(prev_month_projects)
    prev_total = sum_money(item.total_value for item in prev_month_projects)
    prev_paid = [item for item in prev_month_projects if item.total_value]
    prev_ticket = prev_total / len(prev_paid) if prev_paid else ZERO

    source_counts: dict[str, int] = {}
    niche_counts: dict[str, int] = {}
    for item in month_projects:
        source_label = normalize_closing_source(item.closing_source)
        if source_label:
            source_counts[source_label] = source_counts.get(source_label, 0) + 1
        niche_label = item.niche.name if item.niche_id else "Não informado"
        niche_counts[niche_label] = niche_counts.get(niche_label, 0) + 1

    source_palette = ["#4d8cff", "#20b7a7", "#7f6fff", "#f59a3d", "#61748e", "#c765c7"]
    sorted_sources = sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))
    via_breakdown = []
    for index, (label, count) in enumerate(sorted_sources):
        percentage = round((count / volume) * 100) if volume else 0
        if percentage == 0:
            continue
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
    prospection_flow = prospection_evolution_context(workspace, selected_month)

    has_any_project = bool(projects)
    has_active_in_month = any(item.stage == "Fechado" for item in (month_projects or projects))
    if not has_any_project:
        empty_state = {
            "case": "no_data_at_all",
            "title": "Comece a montar seu painel",
            "subtitle": "Cadastre seu primeiro trabalho para que os indicadores aqui ganhem vida.",
            "steps": [
                {"label": "Cadastrar um trabalho", "done": False, "cta_label": "Cadastrar agora", "cta_url": reverse("project_create")},
                {"label": "Registrar um fechamento", "done": False, "cta_label": "Ir para Trabalhos", "cta_url": reverse("jobs")},
                {"label": "Ver seus indicadores", "done": False, "locked": True},
            ],
            "previews": [
                "Volume de trabalhos · mostra quantos negócios fecharam no mês.",
                "Total fechado · soma o quanto entrou em receita confirmada.",
                "Ticket médio · ajuda a comparar volume com receita por trabalho.",
            ],
        }
    elif volume == 0 and has_active_in_month:
        empty_state = {
            "case": "no_closings_this_month",
            "banner_message": f"Nenhum fechamento registrado em {selected_month_label.lower()} ainda.",
            "cta_label": "Ir para Trabalhos",
            "cta_url": reverse("jobs"),
        }
    else:
        empty_state = {"case": "none"}

    return {
        "empty_state": empty_state,
        "stats": [
            {
                "title": "Volume de trabalhos",
                "value": str(volume),
                "subtitle": f"{cadastrados_in_month} cadastrado{'s' if cadastrados_in_month != 1 else ''} · {volume} com fechamento",
                "comparison": _format_count_delta(volume, prev_volume),
                "icon_label": "V",
            },
            {
                "title": "Total fechado",
                "value": currency(total_closed),
                "comparison": _format_currency_delta(total_closed, prev_total),
                "icon_label": "$",
            },
            {"title": "Via principal", "value": top_source_label, "icon_label": "%"},
            {"title": "Nicho líder", "value": top_niche_label, "icon_label": "N"},
            {
                "title": "Ticket médio",
                "value": currency(ticket_medio),
                "subtitle": f"sobre {len(paid_closures)} fechamento{'s' if len(paid_closures) != 1 else ''}" if paid_closures else "sem fechamentos no mês",
                "comparison": _format_currency_delta(ticket_medio, prev_ticket),
                "icon_label": "M",
            },
        ],
        "month_choices": month_choice_payload(month_options),
        "selected_month": selected_month_payload(selected_month),
        "prospection_flow": prospection_flow,
        "source_mix": closing_source_mix(month_projects),
        "via_breakdown": via_breakdown,
        "service_type_tabs": service_type_tabs,
        "active_service_type": active_type,
        "distribution_table": distribution_table,
        "distribution_table_total": distribution_table_total,
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
                    f"{top_niche_label} liderou com {top_niche_count} trabalho{'s' if top_niche_count != 1 else ''} fechado{'s' if top_niche_count != 1 else ''} no mês."
                    if volume
                    else "Assim que você cadastrar fechamentos, o nicho líder aparece aqui."
                ),
            },
            {
                "title": "Resumo do mês",
                "description": (
                    f"{volume} trabalho{'s' if volume != 1 else ''} fechados somando {currency(total_closed)} em {selected_month_label.lower()}."
                    if volume
                    else "Sem fechamentos no período selecionado."
                ),
            },
        ],
    }


def average_project_days(projects: list[Project]) -> float:
    values = [max((item.due_date - item.close_date).days, 1) for item in projects]
    return round(sum(values) / len(values), 1) if values else 0.0
