from __future__ import annotations

import json
import mimetypes
import re
from datetime import date
from pathlib import Path
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetCompleteView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView
from django.db.models import Count
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils._os import safe_join
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .emails import send_signup_confirmation_email

from .forms import (
    AppPasswordResetForm,
    AppSetPasswordForm,
    EmailOrUsernameAuthenticationForm,
    FinanceEntryForm,
    ManagedOptionForm,
    ProfilePhotoForm,
    ProjectForm,
    ProspectForm,
    SignUpForm,
    WorkspaceBusinessForm,
    WorkspaceSettingsForm,
)
from .models import Project, Prospect, ServiceCategory
from .services import (
    confirm_follow_up_companies,
    dashboard_snapshot,
    default_niche_list,
    distribution_snapshot,
    dismiss_follow_up_company,
    finance_snapshot,
    get_or_create_workspace_for_user,
    jobs_snapshot_filtered,
    legal_snapshot,
    parse_month_value,
    prospection_snapshot,
    reports_snapshot,
    save_settings,
    settings_map,
    shell_context,
    start_follow_up_prospection,
    workspace_business_address_summary,
)


class AppLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True


class AppPasswordResetView(PasswordResetView):
    template_name = "registration/hubla_password_reset_form.html"
    email_template_name = "registration/hubla_password_reset_email.txt"
    subject_template_name = "registration/hubla_password_reset_subject.txt"
    form_class = AppPasswordResetForm
    success_url = reverse_lazy("password_reset_done")


class AppPasswordResetDoneView(PasswordResetDoneView):
    template_name = "registration/hubla_password_reset_done.html"


class AppPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "registration/hubla_password_reset_confirm.html"
    form_class = AppSetPasswordForm
    success_url = reverse_lazy("password_reset_complete")


class AppPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "registration/hubla_password_reset_complete.html"


def home(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def serve_media_file(request: HttpRequest, path: str) -> FileResponse:
    media_root = Path(django_settings.MEDIA_ROOT)

    try:
        absolute_path = Path(safe_join(str(media_root), path))
    except ValueError as exc:
        raise Http404("Arquivo invalido.") from exc

    if not absolute_path.is_file():
        raise Http404("Arquivo nao encontrado.")

    content_type, _ = mimetypes.guess_type(absolute_path.name)
    response = FileResponse(absolute_path.open("rb"), content_type=content_type or "application/octet-stream")
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _first_non_empty(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


@login_required
@require_POST
def business_zip_lookup(request: HttpRequest) -> JsonResponse:
    zip_code = re.sub(r"\D", "", request.POST.get("cep", ""))
    if len(zip_code) != 8:
        return JsonResponse({"ok": False, "error": "Informe um CEP valido com 8 digitos."}, status=400)

    if not django_settings.APIBRASIL_CEP_URL:
        return JsonResponse({"ok": False, "error": "Busca de CEP nao configurada no ambiente."}, status=503)

    headers = {"Accept": "application/json"}
    if django_settings.APIBRASIL_CEP_TOKEN:
        headers["Authorization"] = f"Bearer {django_settings.APIBRASIL_CEP_TOKEN}"
        headers["X-API-KEY"] = django_settings.APIBRASIL_CEP_TOKEN

    request_url = django_settings.APIBRASIL_CEP_URL.format(cep=zip_code)
    request_object = Request(request_url, headers=headers)

    try:
        with urlopen(request_object, timeout=django_settings.APIBRASIL_CEP_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError:
        return JsonResponse({"ok": False, "error": "Nao foi possivel consultar esse CEP agora."}, status=502)
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "A busca de CEP falhou. Tente novamente."}, status=502)

    data = payload
    if isinstance(payload, dict):
        for key in ("result", "data", "response"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                data = nested
                break

    if not isinstance(data, dict):
        data = {}

    if isinstance(payload, dict) and (payload.get("error") or payload.get("status") in {"ERROR", "error"}):
        return JsonResponse(
            {
                "ok": False,
                "error": _first_non_empty(
                    payload.get("message"),
                    data.get("message"),
                    "CEP nao encontrado.",
                ),
            },
            status=404,
        )

    street = _first_non_empty(
        data.get("street"),
        data.get("logradouro"),
        data.get("address"),
        data.get("endereco"),
    )
    if not street:
        return JsonResponse({"ok": False, "error": "Nao encontramos a rua desse CEP."}, status=404)
    normalized_zip_code = _first_non_empty(
        data.get("cep"),
        payload.get("cep") if isinstance(payload, dict) else "",
    ) or f"{zip_code[:5]}-{zip_code[5:]}"

    return JsonResponse(
        {
            "ok": True,
            "zip_code": normalized_zip_code,
            "street": street,
        }
    )


def _long_date_label(raw_date: date) -> str:
    months = {
        1: "janeiro",
        2: "fevereiro",
        3: "marco",
        4: "abril",
        5: "maio",
        6: "junho",
        7: "julho",
        8: "agosto",
        9: "setembro",
        10: "outubro",
        11: "novembro",
        12: "dezembro",
    }
    return f"{raw_date.day} de {months[raw_date.month]} de {raw_date.year}"


def _contract_placeholder(value: str | None, fallback: str = "________________") -> str:
    normalized = (value or "").strip()
    return normalized or fallback


def _project_contract_payload(workspace, user, project: Project) -> dict:
    creator_name = _contract_placeholder(user.get_full_name() or user.username)
    creator_email = _contract_placeholder(user.email)
    creator_address = _contract_placeholder(workspace_business_address_summary(workspace))
    creator_cnpj = _contract_placeholder(workspace.business_cnpj)
    creator_pix_key = _contract_placeholder(workspace.business_pis)
    company_name = _contract_placeholder(project.company)
    distribution_label = "TRAFEGO PAGO (ADS)" if project.content_distribution == "Ads" else "USO ORGANICO"
    mixed_distribution_label = "TRAFEGO PAGO (ADS) e USO ORGANICO" if project.content_distribution == "Ads" else "USO ORGANICO"
    service_name = _contract_placeholder(project.service_category_name)
    total_value = f"R$ {project.total_value:.2f}".replace(".", ",")
    entry_value = f"R$ {project.entry_value:.2f}".replace(".", ",")
    balance_value = f"R$ {(project.total_value - project.entry_value):.2f}".replace(".", ",")
    due_date_text = _long_date_label(project.due_date)
    close_date_text = _long_date_label(project.close_date)
    image_term = project.image_license_term_days or 90
    license_expires_on = project.image_usage_expires_on or project.due_date

    return {
        "creator_name": creator_name,
        "creator_email": creator_email,
        "creator_address": creator_address,
        "creator_cnpj": creator_cnpj,
        "creator_pix_key": creator_pix_key,
        "company_name": company_name,
        "company_cnpj": "________________",
        "company_address": "________________",
        "company_email": "________________",
        "service_name": service_name,
        "distribution_label": distribution_label,
        "mixed_distribution_label": mixed_distribution_label,
        "deliverables_count": project.deliverables_count,
        "total_value": total_value,
        "entry_value": entry_value,
        "balance_value": balance_value,
        "close_date_text": close_date_text,
        "due_date_text": due_date_text,
        "image_term": image_term,
        "license_expires_on_text": _long_date_label(license_expires_on),
    }


def _build_contract_pdf(workspace, user, project: Project) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    payload = _project_contract_payload(workspace, user, project)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=f"Contrato - {payload['company_name']}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1a2649"),
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "ContractSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1a2649"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ContractBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=14,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#24334d"),
        spaceAfter=6,
    )
    signature_style = ParagraphStyle(
        "ContractSignature",
        parent=body_style,
        alignment=TA_CENTER,
        spaceBefore=10,
    )

    story = [
        Paragraph("CONTRATO DE CRIACAO DE CONTEUDO UGC", title_style),
        Paragraph(
            (
                f"<b>Contratada:</b> {payload['creator_name']}, inscrita no CNPJ {payload['creator_cnpj']}, "
                f"Chave PIX {payload['creator_pix_key']}, endereco {payload['creator_address']}, e-mail {payload['creator_email']}.<br/>"
                f"<b>Contratante:</b> {payload['company_name']}, CNPJ {payload['company_cnpj']}, endereco {payload['company_address']}, "
                f"e-mail {payload['company_email']}."
            ),
            body_style,
        ),
        Paragraph("1. OBJETO DO CONTRATO", section_style),
        Paragraph(
            (
                f"O presente contrato tem como objeto a prestacao de servicos de criacao de conteudo UGC para "
                f"{payload['mixed_distribution_label']}, referentes ao trabalho <b>{payload['service_name']}</b>, "
                f"personalizado para a marca {payload['company_name']}."
            ),
            body_style,
        ),
        Paragraph("2. ENTREGAVEIS", section_style),
        Paragraph(
            (
                f"A contratada entregara <b>{payload['deliverables_count']} video(s)</b>, incluindo captacao, "
                f"edicao e entrega final ate <b>{payload['due_date_text']}</b>, conforme briefing alinhado entre as partes."
            ),
            body_style,
        ),
        Paragraph("3. OBRIGACOES DA CONTRATADA", section_style),
        Paragraph(
            (
                "A contratada se compromete a produzir conteudos originais, respeitar o briefing aprovado, "
                "realizar ajustes razoaveis dentro do escopo combinado e entregar o material final no prazo acordado."
            ),
            body_style,
        ),
        Paragraph("4. OBRIGACOES DA CONTRATANTE", section_style),
        Paragraph(
            (
                "A contratante se compromete a fornecer briefing, materiais de apoio, aprovacoes em tempo habil, "
                "bem como realizar os pagamentos nas condicoes definidas neste contrato."
            ),
            body_style,
        ),
        Paragraph("5. VIGENCIA E DIREITO DE USO DE IMAGEM", section_style),
        Paragraph(
            (
                f"O uso do conteudo em {payload['distribution_label']} tera inicio na entrega final do material. "
                f"Para Ads, o direito de uso de imagem fica concedido por <b>{payload['image_term']} dias</b>, "
                f"com vencimento previsto em <b>{payload['license_expires_on_text']}</b>. Renovacoes devem ser negociadas por termo aditivo."
            ),
            body_style,
        ),
        Paragraph("6. PAGAMENTO", section_style),
        Paragraph(
            (
                f"O valor total ajustado para o trabalho e de <b>{payload['total_value']}</b>, sendo "
                f"<b>{payload['entry_value']}</b> na entrada e <b>{payload['balance_value']}</b> no saldo final."
            ),
            body_style,
        ),
        Paragraph("7. DIREITOS AUTORAIS E CONFIDENCIALIDADE", section_style),
        Paragraph(
            (
                "A titularidade autoral do conteudo permanece com a criadora, sendo concedida apenas a licenca de uso "
                "necessaria para a finalidade contratada. As partes tambem se comprometem a manter sigilo sobre materiais, "
                "estrategias e informacoes trocadas neste projeto."
            ),
            body_style,
        ),
        Paragraph("8. DISPOSICOES GERAIS", section_style),
        Paragraph(
            (
                "Qualquer ajuste futuro devera ser formalizado por escrito. Este documento pode ser complementado com "
                "informacoes comerciais e juridicas adicionais da contratante antes da assinatura final."
            ),
            body_style,
        ),
        Spacer(1, 20),
        Paragraph(f"Salvador - BA, {payload['close_date_text']}.", body_style),
        Spacer(1, 26),
        Paragraph("__________________________________", signature_style),
        Paragraph(payload["creator_name"], signature_style),
        Spacer(1, 12),
        Paragraph("__________________________________", signature_style),
        Paragraph(payload["company_name"], signature_style),
    ]

    document.build(story)
    return buffer.getvalue()


def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        try:
            send_signup_confirmation_email(user, request)
            messages.success(request, "Conta criada com sucesso. Enviamos um email de confirmacao para voce.")
        except Exception:
            messages.warning(request, "Conta criada com sucesso, mas nao foi possivel enviar o email de confirmacao agora.")
        return redirect("dashboard")

    return render(request, "registration/signup.html", {"form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")


def _workspace(request: HttpRequest):
    return get_or_create_workspace_for_user(request.user)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month")
    context = shell_context(
        "dashboard",
        workspace,
        "Dashboard",
        "Visao executiva do negocio UGC.",
        user=request.user,
        action_label="Novo trabalho",
        action_url="project_create",
        month_filter=month_filter,
    )
    context.update(dashboard_snapshot(workspace, month_filter))
    return render(request, "studio/dashboard.html", context)


@login_required
def prospection(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context("prospection", workspace, "Prospecção", "Leads, follow-ups e negociacoes em aberto.", user=request.user, action_label="Novo lead", action_url="prospect_create")
    context.update(prospection_snapshot(workspace))
    return render(request, "studio/prospection.html", context)


@login_required
@require_POST
def follow_up_confirm(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    added_keys = confirm_follow_up_companies(workspace, request.POST.getlist("company_keys"))
    if added_keys:
        messages.success(request, "Marcas enviadas para o follow-up.")
    return redirect(f"{reverse('prospection')}#follow-up-column")


@login_required
@require_POST
def follow_up_dismiss(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    dismiss_follow_up_company(workspace, request.POST.get("company_key", ""))
    return redirect("prospection")


@login_required
@require_POST
def follow_up_start_prospection(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    prospect = start_follow_up_prospection(workspace, request.POST.get("company_key", ""))
    if prospect:
        messages.success(request, f"{prospect.company} voltou para Prospecção.")
    return redirect("prospection")


@login_required
def jobs(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month")
    active_section = request.GET.get("section", "").strip().lower()
    context = shell_context(
        "jobs",
        workspace,
        "Trabalhos",
        "Trabalhos assinados e entregas em andamento.",
        user=request.user,
        action_label="Novo trabalho",
        action_url="project_create",
        month_filter=month_filter,
    )
    context.update(
        jobs_snapshot_filtered(
            workspace,
            service_category_filter=request.GET.get("service_category"),
            progress_filter=request.GET.get("progress"),
            niche_filter=request.GET.get("niche"),
            search=request.GET.get("search"),
            month_filter=month_filter,
        )
    )
    if active_section not in {"overdue", "active", "delivered"}:
        active_section = ""
    context["active_jobs_section"] = active_section

    current_params = request.GET.copy()
    current_params.pop("section", None)
    context["jobs_show_all_url"] = f"{reverse('jobs')}?{current_params.urlencode()}" if current_params else reverse("jobs")
    for item in context["stats"]:
        section_params = current_params.copy()
        section_params["section"] = item["section"]
        item["url"] = f"{reverse('jobs')}?{section_params.urlencode()}"

    return render(request, "studio/jobs.html", context)


@login_required
def finance(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month") or request.POST.get("month")
    selected_month = parse_month_value(month_filter) if month_filter and month_filter != "all" else None
    today = date.today()
    initial_date = (
        today
        if selected_month is None or (selected_month.year == today.year and selected_month.month == today.month)
        else selected_month
    )
    incoming_form = FinanceEntryForm(prefix="incoming", initial={"occurred_on": initial_date})
    outgoing_form = FinanceEntryForm(prefix="outgoing", initial={"occurred_on": initial_date})

    if request.method == "POST":
        action = request.POST.get("finance_action")
        if action == "incoming":
            incoming_form = FinanceEntryForm(request.POST, prefix="incoming")
            if incoming_form.is_valid():
                entry = incoming_form.save(commit=False)
                entry.workspace = workspace
                entry.kind = "incoming"
                entry.save()
                messages.success(request, "Entrada registrada.")
                redirect_url = reverse("finance")
                if month_filter:
                    redirect_url = f"{redirect_url}?month={month_filter}"
                return redirect(redirect_url)
        elif action == "outgoing":
            outgoing_form = FinanceEntryForm(request.POST, prefix="outgoing")
            if outgoing_form.is_valid():
                entry = outgoing_form.save(commit=False)
                entry.workspace = workspace
                entry.kind = "outgoing"
                entry.save()
                messages.success(request, "Saida registrada.")
                redirect_url = reverse("finance")
                if month_filter:
                    redirect_url = f"{redirect_url}?month={month_filter}"
                return redirect(redirect_url)

    context = shell_context(
        "finance",
        workspace,
        "Financeiro",
        "Fluxo de caixa, despesas e saldo de recebiveis.",
        user=request.user,
        month_filter=month_filter,
    )
    context.update(finance_snapshot(workspace, month_filter))
    context.update(
        {
            "incoming_form": incoming_form,
            "outgoing_form": outgoing_form,
        }
    )
    return render(request, "studio/finance.html", context)


@login_required
def distribution(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context(
        "distribution",
        workspace,
        "Distribuicao",
        "Controle onde cada material vai rodar entre organico e ads.",
        user=request.user,
    )
    context.update(distribution_snapshot(workspace))
    return render(request, "studio/distribution.html", context)


@login_required
def legal(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context(
        "legal",
        workspace,
        "Juridico",
        "Acompanhe o direito de uso de imagem e os vencimentos de licenciamento.",
        user=request.user,
    )
    context.update(legal_snapshot(workspace))
    return render(request, "studio/legal.html", context)


@login_required
def legal_contract_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(
        Project.objects.filter(workspace=workspace, content_distribution="Ads"),
        pk=pk,
    )
    pdf_content = _build_contract_pdf(workspace, request.user, project)
    filename = slugify(f"contrato-{project.company}-{project.service_category_name}") or f"contrato-{project.pk}"
    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month")
    context = shell_context(
        "reports",
        workspace,
        "Relatorios",
        "Indicadores estrategicos do negocio.",
        user=request.user,
        month_filter=month_filter,
    )
    context.update(reports_snapshot(workspace, month_filter))
    return render(request, "studio/reports.html", context)


@login_required
def settings(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    settings_form = WorkspaceSettingsForm(
        request.POST if request.method == "POST" and request.POST.get("settings_action") == "preferences" else None,
        settings_values=settings_map(workspace),
    )
    service_category_form = ManagedOptionForm(
        request.POST if request.method == "POST" and request.POST.get("settings_action") == "add_service_category" else None,
        label="Nova categoria de servico",
        help_text="Cadastre aqui as categorias de servico para selecionar nos trabalhos.",
        prefix="service_category",
    )

    if request.method == "POST":
        action = request.POST.get("settings_action")
        if action == "preferences" and settings_form.is_valid():
            save_settings(workspace, settings_form.cleaned_data)
            messages.success(request, "Configuracoes atualizadas.")
            return redirect("settings")
        if action == "add_service_category" and service_category_form.is_valid():
            name = service_category_form.cleaned_data["name"].strip()
            service_category, created = ServiceCategory.objects.get_or_create(workspace=workspace, name=name)
            messages.success(request, "Categoria de servico cadastrada." if created else "Essa categoria ja existe.")
            return redirect("settings")
        if action == "delete_service_category":
            service_category = get_object_or_404(ServiceCategory, pk=request.POST.get("service_category_id"), workspace=workspace)
            if service_category.projects.exists():
                messages.warning(request, "Essa categoria ja foi usada em trabalhos e nao pode mais ser excluida.")
            else:
                service_category.delete()
                messages.success(request, "Categoria de servico removida.")
            return redirect("settings")

    context = shell_context("settings", workspace, "Configuracoes", "Preferencias visuais e operacionais.", user=request.user)
    context.update(
        {
            "form": settings_form,
            "service_category_form": service_category_form,
            "managed_niches": default_niche_list(workspace),
            "managed_service_categories": ServiceCategory.objects.filter(workspace=workspace).annotate(usage_count=Count("projects")).order_by("name"),
        }
    )
    return render(request, "studio/settings.html", context)


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    membership = request.user.memberships.select_related("workspace").filter(workspace=workspace).first()
    photo_form = ProfilePhotoForm()
    business_form = WorkspaceBusinessForm(instance=workspace)

    if request.method == "POST":
        action = request.POST.get("profile_action")
        if action == "photo":
            photo_form = ProfilePhotoForm(request.POST, request.FILES)
            if photo_form.is_valid() and membership:
                membership.avatar = photo_form.cleaned_data["photo"]
                membership.save(update_fields=["avatar", "updated_at"])
                messages.success(request, "Foto de perfil atualizada.")
                return redirect("profile")
        elif action == "business":
            business_form = WorkspaceBusinessForm(request.POST, instance=workspace)
            if business_form.is_valid():
                business_form.save()
                messages.success(request, "Dados empresariais atualizados.")
                return redirect("profile")

    context = shell_context("profile", workspace, "Perfil", "Dados cadastrais da conta e do workspace ativo.", user=request.user)
    context.update(
        {
            "membership": membership,
            "photo_form": photo_form,
            "business_form": business_form,
            "profile_sections": [
                {
                    "title": "Conta",
                    "items": [
                        {"label": "Usuario", "value": request.user.username or "-"},
                        {"label": "Email", "value": request.user.email or "-"},
                        {"label": "Data de cadastro", "value": request.user.date_joined.strftime("%d/%m/%Y")},
                        {"label": "Ultimo acesso", "value": request.user.last_login.strftime("%d/%m/%Y %H:%M") if request.user.last_login else "Primeiro acesso"},
                    ],
                },
                {
                    "title": "Workspace",
                    "items": [
                        {"label": "Workspace ativo", "value": workspace.name},
                    ],
                },
            ]
        }
    )
    return render(request, "studio/profile.html", context)


@login_required
def prospect_create(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    form = ProspectForm(request.POST or None, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        prospect = form.save(commit=False)
        prospect.workspace = workspace
        prospect.save()
        messages.success(request, "Lead salvo com sucesso.")
        return redirect("prospection")

    context = shell_context("prospection", workspace, "Novo lead", "Registre uma oportunidade comercial.", user=request.user)
    context.update({"form": form, "form_title": "Lead / prospecção", "cancel_url": "prospection"})
    return render(request, "studio/prospect_form.html", context)


@login_required
def prospect_edit(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    form = ProspectForm(request.POST or None, instance=prospect, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Lead atualizado.")
        return redirect("prospection")

    context = shell_context("prospection", workspace, "Editar lead", "Ajuste os dados da oportunidade.", user=request.user)
    context.update({"form": form, "form_title": "Lead / prospecção", "cancel_url": "prospection"})
    return render(request, "studio/prospect_form.html", context)


@login_required
@require_POST
def prospect_delete(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    prospect.delete()
    messages.success(request, "Lead removido.")
    return redirect("prospection")


@login_required
def prospect_convert(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    initial = {
        "company": prospect.company,
        "closing_source": "Prospeccao",
        "niche": prospect.niche,
        "service_category": None,
        "stage": "Fechado",
        "status": "Briefing",
        "received_value": 0,
        "deliverables_count": 3,
        "progress": 15,
        "meeting_scheduled": prospect.meeting_scheduled,
        "meeting_date": prospect.meeting_date,
        "note": prospect.note,
        "content_distribution": "",
        "image_license_term_days": None,
    }
    form = ProjectForm(request.POST or None, initial=initial, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.workspace = workspace
        project.save()
        prospect.delete()
        messages.success(request, "Lead convertido em trabalho.")
        if project.content_distribution == "Ads" and project.image_license_term_days:
            messages.info(request, "Direito de uso de imagem ativado. O Juridico vai avisar no vencimento.")
        return redirect("jobs")

    context = shell_context("prospection", workspace, "Converter lead", "Transforme a oportunidade em trabalho.", user=request.user)
    context.update({"form": form, "form_title": "Trabalho", "cancel_url": "prospection"})
    return render(request, "studio/project_form.html", context)


@login_required
def project_create(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    form = ProjectForm(request.POST or None, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.workspace = workspace
        project.save()
        messages.success(request, "Trabalho salvo com sucesso.")
        if project.content_distribution == "Ads" and project.image_license_term_days:
            messages.info(request, "Direito de uso de imagem ativado. O Juridico vai avisar no vencimento.")
        return redirect("jobs")

    context = shell_context("jobs", workspace, "Novo trabalho", "Cadastre um novo trabalho.", user=request.user)
    context.update({"form": form, "form_title": "Trabalho", "cancel_url": "jobs"})
    return render(request, "studio/project_form.html", context)


@login_required
def project_edit(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project, pk=pk, workspace=workspace)
    form = ProjectForm(request.POST or None, instance=project, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        project = form.save()
        messages.success(request, "Trabalho atualizado.")
        if project.content_distribution == "Ads" and project.image_license_term_days:
            messages.info(request, "Direito de uso de imagem ativado. O Juridico vai avisar no vencimento.")
        return redirect("jobs")

    context = shell_context("jobs", workspace, "Editar trabalho", "Ajuste valores, datas e status.", user=request.user)
    context.update({"form": form, "form_title": "Trabalho", "cancel_url": "jobs"})
    return render(request, "studio/project_form.html", context)


@login_required
@require_POST
def project_delete(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project, pk=pk, workspace=workspace)
    project.delete()
    messages.success(request, "Trabalho removido.")
    return redirect("jobs")
