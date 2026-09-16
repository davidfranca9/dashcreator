"""Central TCC em thecreatorsclub.com.br/central/.

A página é do domínio do clube, não do Dash: o nginx do site repassa
/central/ para o sistema (ver landing/nginx-default.conf), com o cabeçalho
X-Central-Proxy. Tem entrada própria, só para as contas do time, e o login
aqui não derruba a sessão do Dash (ver signals.enforce_single_active_session).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache

from .central import APP, central_snapshot
from .forms import EmailOrUsernameAuthenticationForm
from .services import is_internal_account

CENTRAL_PUBLICA = "https://thecreatorsclub.com.br/central/"


def _fora_do_dominio(request: HttpRequest) -> HttpResponse | None:
    """Quem abre /central/ direto no app vai para o endereço do clube."""
    if request.headers.get("X-Central-Proxy") or getattr(settings, "CENTRAL_ACESSO_DIRETO", settings.DEBUG):
        return None
    return redirect(CENTRAL_PUBLICA + request.path.removeprefix("/central/"))


def _do_time(user) -> bool:
    return bool(user and user.is_authenticated and is_internal_account(None, user))


@never_cache
def central_entrar(request: HttpRequest) -> HttpResponse:
    desvio = _fora_do_dominio(request)
    if desvio:
        return desvio
    destino = request.POST.get("next") or request.GET.get("next") or "/central/"
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts=None) or not destino.startswith("/central/"):
        destino = "/central/"
    if _do_time(request.user):
        return redirect(destino)

    form = EmailOrUsernameAuthenticationForm(request, data=request.POST or None)
    erro = ""
    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            if _do_time(user):
                login(request, user)
                return redirect(destino)
            erro = "Esta área é só do time do The Creators Club."
        else:
            erro = "E-mail, usuário ou senha incorretos."
    return render(request, "central/entrar.html", {"form": form, "erro": erro, "next": destino})


@never_cache
def central_sair(request: HttpRequest) -> HttpResponse:
    desvio = _fora_do_dominio(request)
    if desvio:
        return desvio
    logout(request)
    return redirect("/central/entrar/")


@never_cache
def central_painel(request: HttpRequest) -> HttpResponse:
    desvio = _fora_do_dominio(request)
    if desvio:
        return desvio
    if not _do_time(request.user):
        if request.user.is_authenticated:
            logout(request)
        return redirect("/central/entrar/")
    nome = request.user.get_full_name() or request.user.username
    contexto = central_snapshot()
    contexto.update({
        "usuario_nome": nome,
        "usuario_iniciais": "".join(parte[0] for parte in nome.split()[:2]).upper() or "TC",
        "app": APP,
    })
    return render(request, "central/painel.html", contexto)
