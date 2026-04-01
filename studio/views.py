from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetCompleteView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView
from django.db.models import Count
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils._os import safe_join
from django.views.decorators.http import require_POST

from .emails import send_signup_confirmation_email

from .forms import (
    AppPasswordResetForm,
    AppSetPasswordForm,
    EmailOrUsernameAuthenticationForm,
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
    prospection_snapshot,
    reports_snapshot,
    save_settings,
    settings_map,
    shell_context,
    start_follow_up_prospection,
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
    return render(request, "studio/jobs.html", context)


@login_required
def finance(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month")
    context = shell_context(
        "finance",
        workspace,
        "Financeiro",
        "Entradas, recebimentos e previsoes de caixa.",
        user=request.user,
        month_filter=month_filter,
    )
    context.update(finance_snapshot(workspace, month_filter))
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
