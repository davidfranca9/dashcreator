"""Central TCC em thecreatorsclub.com.br/central/.

A página é do domínio do clube, não do Dash: o nginx do site repassa
/central/ para o sistema (ver landing/nginx-default.conf), com o cabeçalho
X-Central-Proxy. Tem entrada própria, só para as contas do time, e o login
aqui não derruba a sessão do Dash (ver signals.enforce_single_active_session).
"""
from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .central import APP, central_snapshot
from .evento import EVENTO, FornecedorForm, RoteiroForm, TarefaForm, criar_sugestao
from .forms import EmailOrUsernameAuthenticationForm
from .models import EventScheduleItem, EventSupplier, EventTask
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
        "usuario_primeiro_nome": nome.split()[0] if nome.split() else nome,
        "usuario_iniciais": "".join(parte[0] for parte in nome.split()[:2]).upper() or "TC",
        "app": APP,
    })
    return render(request, "central/painel.html", contexto)


# ------------------------------------------------------------ aba Creator Day
# tipo na URL -> (modelo, formulário, subaba de volta, mensagem ao salvar, mensagem ao excluir)
EDITAVEIS = {
    "fornecedor": (EventSupplier, FornecedorForm, "fornecedores", "Fornecedor salvo.", "Fornecedor excluído."),
    "tarefa": (EventTask, TarefaForm, "tarefas", "Tarefa salva.", "Tarefa excluída."),
    "roteiro": (EventScheduleItem, RoteiroForm, "roteiro", "Horário salvo.", "Horário excluído."),
}


def _acao_do_time(request: HttpRequest) -> HttpResponse | None:
    """Barreira das ações da aba Creator Day: domínio do clube, POST e conta do time."""
    desvio = _fora_do_dominio(request)
    if desvio:
        return desvio
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not _do_time(request.user):
        return redirect("/central/entrar/")
    return None


def _editavel(tipo: str):
    if tipo not in EDITAVEIS:
        raise Http404
    return EDITAVEIS[tipo]


def _volta(aba: str) -> HttpResponse:
    return redirect(f"/central/#evento/{aba}")


@never_cache
def central_evento_salvar(request: HttpRequest, tipo: str, pk: int | None = None) -> HttpResponse:
    barreira = _acao_do_time(request)
    if barreira:
        return barreira
    modelo, formulario, aba, salvo, _ = _editavel(tipo)
    instancia = get_object_or_404(modelo, pk=pk, event_key=EVENTO["chave"]) if pk else None
    form = formulario(request.POST, instance=instancia)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.event_key = EVENTO["chave"]
        obj.save()
        messages.success(request, salvo)
    else:
        erros = "; ".join(
            f"{(form.fields[campo].label or campo).capitalize() if campo in form.fields else 'Formulário'}: {' '.join(lista)}"
            for campo, lista in form.errors.items()
        )
        messages.error(request, f"Não salvou. {erros}")
    return _volta(aba)


@never_cache
def central_evento_excluir(request: HttpRequest, tipo: str, pk: int) -> HttpResponse:
    barreira = _acao_do_time(request)
    if barreira:
        return barreira
    modelo, _, aba, _, excluido = _editavel(tipo)
    get_object_or_404(modelo, pk=pk, event_key=EVENTO["chave"]).delete()
    messages.success(request, excluido)
    return _volta(aba)


@never_cache
def central_evento_tarefa_feita(request: HttpRequest, pk: int) -> HttpResponse:
    """Marca ou desmarca a tarefa. Pelo JavaScript responde JSON; sem ele, volta para a aba."""
    barreira = _acao_do_time(request)
    if barreira:
        return barreira
    tarefa = get_object_or_404(EventTask, pk=pk, event_key=EVENTO["chave"])
    tarefa.done = not tarefa.done
    tarefa.done_at = timezone.now() if tarefa.done else None
    tarefa.save(update_fields=["done", "done_at", "updated_at"])
    if request.headers.get("X-Central-Fetch"):
        tarefas = EventTask.objects.filter(event_key=EVENTO["chave"])
        return JsonResponse({"feita": tarefa.done, "feitas": tarefas.filter(done=True).count(), "total": tarefas.count()})
    return _volta("tarefas")


@never_cache
def central_evento_sugestao(request: HttpRequest, tipo: str) -> HttpResponse:
    barreira = _acao_do_time(request)
    if barreira:
        return barreira
    if tipo not in ("tarefas", "roteiro"):
        raise Http404
    criados = criar_sugestao(tipo)
    if criados:
        messages.success(request, f"{criados} itens sugeridos criados. Ajustem do jeito de vocês.")
    return _volta(tipo)
