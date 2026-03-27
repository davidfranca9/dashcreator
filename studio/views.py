from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetCompleteView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

from .emails import send_signup_confirmation_email
from .forms import (
    AppPasswordResetForm,
    AppSetPasswordForm,
    EmailOrUsernameAuthenticationForm,
    ProjectForm,
    ProspectForm,
    SignUpForm,
    WorkspaceSettingsForm,
)
from .models import Project, Prospect
from .services import (
    dashboard_snapshot,
    finance_snapshot,
    get_or_create_workspace_for_user,
    jobs_snapshot,
    prospection_snapshot,
    reports_snapshot,
    save_settings,
    settings_map,
    shell_context,
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
    context = shell_context("dashboard", workspace, "Dashboard", "Visao executiva do negocio UGC.", action_label="Novo projeto", action_url="project_create")
    context.update(dashboard_snapshot(workspace, request.GET.get("range", "last_6_months")))
    return render(request, "studio/dashboard.html", context)


@login_required
def prospection(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context("prospection", workspace, "Prospeccao", "Leads, follow-ups e negociacoes em aberto.", action_label="Novo lead", action_url="prospect_create")
    context.update(prospection_snapshot(workspace))
    return render(request, "studio/prospection.html", context)


@login_required
def jobs(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context("jobs", workspace, "Trabalhos", "Projetos assinados e entregas em andamento.", action_label="Novo projeto", action_url="project_create")
    context.update(jobs_snapshot(workspace))
    return render(request, "studio/jobs.html", context)


@login_required
def finance(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context("finance", workspace, "Financeiro", "Entradas, recebimentos e previsoes de caixa.")
    context.update(finance_snapshot(workspace))
    return render(request, "studio/finance.html", context)


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context("reports", workspace, "Relatorios", "Indicadores estrategicos do negocio.")
    context.update(reports_snapshot(workspace))
    return render(request, "studio/reports.html", context)


@login_required
def settings(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    form = WorkspaceSettingsForm(request.POST or None, settings_values=settings_map(workspace))
    if request.method == "POST" and form.is_valid():
        save_settings(workspace, form.cleaned_data)
        messages.success(request, "Configuracoes atualizadas.")
        return redirect("settings")

    context = shell_context("settings", workspace, "Configuracoes", "Preferencias visuais e operacionais.")
    context.update({"form": form})
    return render(request, "studio/settings.html", context)


@login_required
def prospect_create(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    form = ProspectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        prospect = form.save(commit=False)
        prospect.workspace = workspace
        prospect.save()
        messages.success(request, "Lead salvo com sucesso.")
        return redirect("prospection")

    context = shell_context("prospection", workspace, "Novo lead", "Registre uma oportunidade comercial.")
    context.update({"form": form, "form_title": "Lead / prospeccao", "cancel_url": "prospection"})
    return render(request, "studio/prospect_form.html", context)


@login_required
def prospect_edit(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    form = ProspectForm(request.POST or None, instance=prospect)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Lead atualizado.")
        return redirect("prospection")

    context = shell_context("prospection", workspace, "Editar lead", "Ajuste os dados da oportunidade.")
    context.update({"form": form, "form_title": "Lead / prospeccao", "cancel_url": "prospection"})
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
        "project_name": f"Projeto {prospect.company}",
        "content_type": "UGC Vertical",
        "stage": "Fechado",
        "status": "Briefing",
        "total_value": prospect.proposal_value,
        "entry_value": prospect.proposal_value * 0.5,
        "received_value": 0,
        "deliverables_count": 3,
        "progress": 15,
    }
    form = ProjectForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.workspace = workspace
        project.save()
        prospect.delete()
        messages.success(request, "Lead convertido em projeto.")
        return redirect("jobs")

    context = shell_context("prospection", workspace, "Converter lead", "Transforme a oportunidade em projeto.")
    context.update({"form": form, "form_title": "Projeto", "cancel_url": "prospection"})
    return render(request, "studio/project_form.html", context)


@login_required
def project_create(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.workspace = workspace
        project.save()
        messages.success(request, "Projeto salvo com sucesso.")
        return redirect("jobs")

    context = shell_context("jobs", workspace, "Novo projeto", "Cadastre um novo trabalho.")
    context.update({"form": form, "form_title": "Projeto", "cancel_url": "jobs"})
    return render(request, "studio/project_form.html", context)


@login_required
def project_edit(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project, pk=pk, workspace=workspace)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Projeto atualizado.")
        return redirect("jobs")

    context = shell_context("jobs", workspace, "Editar projeto", "Ajuste valores, datas e status.")
    context.update({"form": form, "form_title": "Projeto", "cancel_url": "jobs"})
    return render(request, "studio/project_form.html", context)


@login_required
@require_POST
def project_delete(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project, pk=pk, workspace=workspace)
    project.delete()
    messages.success(request, "Projeto removido.")
    return redirect("jobs")
