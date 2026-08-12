from __future__ import annotations

import json
from datetime import date
from functools import wraps

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, dumps, loads
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import (
    Aluna,
    Aula,
    ChecklistItem,
    ChecklistMarcado,
    ComentarioAula,
    Config,
    Desafio,
    DesafioStatus,
    Duvida,
    Entrega,
    Evolucao,
    Material,
    ProgressoAula,
    RespostaDuvida,
    Tarefa,
    TarefaConcluida,
    normalizar_codigo,
    normalizar_email,
)

TOKEN_SALT = "tcc-portal-auth"
TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # 30 dias


def _json(data, status: int = 200) -> JsonResponse:
    return JsonResponse(data, status=status, safe=False)


def _erro(msg: str, status: int = 400) -> JsonResponse:
    return _json({"erro": msg}, status=status)


def _body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _make_token(payload: dict) -> str:
    return dumps(payload, salt=TOKEN_SALT, compress=True)


def _read_token(request: HttpRequest):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        return None
    raw = header[len("Bearer "):].strip()
    try:
        return loads(raw, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def auth_required(view):
    """Injeta request.tcc_role ('mentor'|'aluna') e request.tcc_aluna (Aluna|None)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        payload = _read_token(request)
        if not payload:
            return _erro("Sessão expirada ou inválida. Entre novamente.", 401)
        if payload.get("role") == "mentor":
            request.tcc_role = "mentor"
            request.tcc_aluna = None
        elif payload.get("role") == "aluna":
            aluna = Aluna.objects.filter(pk=payload.get("id")).first()
            if not aluna or aluna.status in (Aluna.STATUS_PAUSADA, Aluna.STATUS_ARQUIVADA):
                return _erro("Acesso não está mais ativo. Fale com a mentora.", 401)
            request.tcc_role = "aluna"
            request.tcc_aluna = aluna
        else:
            return _erro("Sessão inválida.", 401)
        return view(request, *args, **kwargs)

    return wrapper


def mentor_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if getattr(request, "tcc_role", None) != "mentor":
            return _erro("Só a mentora pode fazer isso.", 403)
        return view(request, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------- auth ----

@csrf_exempt
@require_http_methods(["POST"])
def mentor_login(request):
    body = _body(request)
    senha = str(body.get("senha", ""))
    if senha != settings.TCC_PORTAL_ADMIN_PASSWORD:
        return _erro("Senha incorreta.", 401)
    return _json({"token": _make_token({"role": "mentor"})})


@csrf_exempt
@require_http_methods(["POST"])
def aluna_login(request):
    body = _body(request)
    email = normalizar_email(body.get("email", ""))
    codigo = normalizar_codigo(body.get("codigo", ""))
    if not email or not codigo:
        return _erro("Preencha e-mail e código de acesso.")
    aluna = Aluna.objects.filter(email=email, codigo=codigo).first()
    if not aluna:
        return _erro("E-mail ou código não encontrado. Confira os dados enviados pela mentora.", 404)
    if aluna.status == Aluna.STATUS_PAUSADA:
        return _erro("Seu acesso está pausado. Fale com a mentora para regularizar.", 403)
    if aluna.status == Aluna.STATUS_ARQUIVADA:
        return _erro("Este acesso não está mais ativo. Fale com a mentora.", 403)
    token = _make_token({"role": "aluna", "id": aluna.id})
    return _json({"token": token, "aluna": _aluna_dict(aluna, full=True)})


# --------------------------------------------------------------- dict helpers ----

def _aula_dict(a: Aula) -> dict:
    return {
        "id": a.id, "titulo": a.titulo, "descricao": a.descricao, "faseId": a.fase_id,
        "duracao": a.duracao, "url": a.url, "capaUrl": a.capa_url, "status": a.status,
        "destaque": a.destaque, "createdAt": a.created_at.isoformat(),
    }


def _material_dict(m: Material) -> dict:
    return {
        "id": m.id, "titulo": m.titulo, "descricao": m.descricao, "faseId": m.fase_id,
        "tipo": m.tipo, "url": m.url, "createdAt": m.created_at.isoformat(),
    }


def _tarefa_dict(t: Tarefa) -> dict:
    return {
        "id": t.id, "titulo": t.titulo, "descricao": t.descricao, "faseId": t.fase_id,
        "prazo": t.prazo.isoformat(), "prioridade": t.prioridade,
    }


def _desafio_dict(d: Desafio) -> dict:
    return {"id": d.id, "titulo": d.titulo, "descricao": d.descricao}


def _checklist_item_dict(c: ChecklistItem) -> dict:
    return {"id": c.id, "faseId": c.fase_id, "texto": c.texto}


def _aluna_dict(al: Aluna, full: bool) -> dict:
    if not full:
        return {"id": al.id, "nome": al.nome}
    return {
        "id": al.id, "nome": al.nome, "email": al.email, "whatsapp": al.whatsapp,
        "turma": al.turma, "dataEntrada": al.data_entrada.isoformat(), "status": al.status,
        "objetivo": al.objetivo, "notas": al.notas, "codigo": al.codigo,
    }


def _duvida_dict(d: Duvida) -> dict:
    return {
        "id": d.id, "alunaId": d.aluna_id, "faseId": d.fase_id, "texto": d.texto,
        "data": d.created_at.isoformat(),
        "respostas": [
            {
                "alunaId": r.aluna_id, "nome": "Mentora" if r.from_mentor else (r.aluna.nome if r.aluna else "Aluna"),
                "texto": r.texto, "fromMentor": r.from_mentor, "data": r.created_at.isoformat(),
            }
            for r in d.respostas.select_related("aluna").all()
        ],
    }


def _entrega_dict(e: Entrega) -> dict:
    return {
        "id": e.id, "alunaId": e.aluna_id, "faseId": e.fase_id, "titulo": e.titulo,
        "link": e.link, "comentario": e.comentario, "data": e.created_at.isoformat(),
    }


def _evolucao_dict(e: Evolucao) -> dict:
    return {"id": e.id, "alunaId": e.aluna_id, "faseId": e.fase_id, "texto": e.texto, "data": e.created_at.isoformat()}


def _comentario_dict(c: ComentarioAula) -> dict:
    return {
        "id": c.id, "aulaId": c.aula_id, "alunaId": c.aluna_id, "texto": c.texto,
        "fromMentor": c.from_mentor, "data": c.created_at.isoformat(),
    }


# ------------------------------------------------------------- estado ----

@auth_required
@require_http_methods(["GET"])
def estado(request):
    conteudo_row = Config.obter()
    is_mentor = request.tcc_role == "mentor"

    alunas_qs = Aluna.objects.all()
    duvidas_qs = Duvida.objects.prefetch_related("respostas__aluna").all()
    entregas_qs = Entrega.objects.all()
    evolucao_qs = Evolucao.objects.all()
    comentarios_qs = ComentarioAula.objects.all()

    checklist_alunas: dict[str, dict[str, bool]] = {}
    for row in ChecklistMarcado.objects.all():
        checklist_alunas.setdefault(str(row.aluna_id), {})[str(row.item_id)] = True

    progresso_aulas: dict[str, dict[str, bool]] = {}
    for row in ProgressoAula.objects.all():
        progresso_aulas.setdefault(str(row.aluna_id), {})[str(row.aula_id)] = True

    tarefas_alunas: dict[str, dict[str, bool]] = {}
    for row in TarefaConcluida.objects.all():
        tarefas_alunas.setdefault(str(row.aluna_id), {})[str(row.tarefa_id)] = True

    desafios_alunas: dict[str, dict[str, dict]] = {}
    for row in DesafioStatus.objects.all():
        desafios_alunas.setdefault(str(row.aluna_id), {})[str(row.desafio_id)] = {
            "topei": row.topei, "feito": row.feito,
        }

    return _json({
        "role": request.tcc_role,
        "alunaAtual": _aluna_dict(request.tcc_aluna, full=True) if request.tcc_aluna else None,
        "conteudo": {
            "avisoMentora": conteudo_row.aviso_mentora,
            "faseAtualId": conteudo_row.fase_atual_id,
            "mentoraNome": conteudo_row.mentora_nome,
            "abasOcultas": conteudo_row.abas_ocultas,
            "aulas": [_aula_dict(a) for a in Aula.objects.all()],
            "materiais": [_material_dict(m) for m in Material.objects.all()],
            "tarefas": [_tarefa_dict(t) for t in Tarefa.objects.all()],
            "desafios": [_desafio_dict(d) for d in Desafio.objects.all()],
            "checklist": [_checklist_item_dict(c) for c in ChecklistItem.objects.all()],
        },
        "alunas": [_aluna_dict(al, full=is_mentor) for al in alunas_qs],
        "duvidas": [_duvida_dict(d) for d in duvidas_qs],
        "entregas": [_entrega_dict(e) for e in entregas_qs],
        "evolucao": [_evolucao_dict(e) for e in evolucao_qs],
        "comentariosAula": [_comentario_dict(c) for c in comentarios_qs],
        "checklistAlunas": checklist_alunas,
        "progressoAulas": progresso_aulas,
        "tarefasAlunas": tarefas_alunas,
        "desafiosAlunas": desafios_alunas,
    })


# ------------------------------------------------------------ config (mentor) ----

@csrf_exempt
@auth_required
@mentor_required
@require_http_methods(["POST"])
def config_update(request):
    body = _body(request)
    cfg = Config.obter()
    if "avisoMentora" in body:
        cfg.aviso_mentora = str(body["avisoMentora"]).strip()
    if "faseAtualId" in body:
        cfg.fase_atual_id = body["faseAtualId"]
    if "mentoraNome" in body:
        cfg.mentora_nome = str(body["mentoraNome"]).strip()
    if "abasOcultas" in body and isinstance(body["abasOcultas"], list):
        cfg.abas_ocultas = body["abasOcultas"]
    cfg.save()
    return _json({"ok": True})


@csrf_exempt
@auth_required
@mentor_required
@require_http_methods(["POST"])
def aba_toggle(request):
    body = _body(request)
    tab_id = body.get("tabId")
    if not tab_id:
        return _erro("tabId obrigatório.")
    cfg = Config.obter()
    ocultas = list(cfg.abas_ocultas or [])
    if tab_id in ocultas:
        ocultas.remove(tab_id)
    else:
        ocultas.append(tab_id)
    cfg.abas_ocultas = ocultas
    cfg.save()
    return _json({"abasOcultas": ocultas})


# ------------------------------------------------------------ CRUD generico (mentor) ----

def _crud_view(model, to_dict, fields_from_body):
    """Gera (create_view, update_view, delete_view) para um model simples de conteudo."""

    @csrf_exempt
    @auth_required
    @mentor_required
    @require_http_methods(["POST"])
    def create(request):
        body = _body(request)
        obj = model()
        try:
            fields_from_body(obj, body)
            obj.save()
        except Exception as exc:  # validação simples, devolve erro legível
            return _erro(str(exc))
        return _json(to_dict(obj), status=201)

    @csrf_exempt
    @auth_required
    @mentor_required
    @require_http_methods(["POST"])
    def update(request, pk):
        obj = model.objects.filter(pk=pk).first()
        if not obj:
            return _erro("Não encontrado.", 404)
        body = _body(request)
        try:
            fields_from_body(obj, body)
            obj.save()
        except Exception as exc:
            return _erro(str(exc))
        return _json(to_dict(obj))

    @csrf_exempt
    @auth_required
    @mentor_required
    @require_http_methods(["POST"])
    def delete(request, pk):
        model.objects.filter(pk=pk).delete()
        return _json({"ok": True})

    return create, update, delete


def _aula_fields(obj: Aula, body: dict):
    obj.titulo = str(body.get("titulo", obj.titulo or "")).strip()
    if not obj.titulo:
        raise ValueError("Informe o título da aula.")
    obj.descricao = str(body.get("descricao", obj.descricao or "")).strip()
    obj.fase_id = body.get("faseId", obj.fase_id or "onboarding")
    obj.duracao = int(body.get("duracao") or 0)
    obj.url = str(body.get("url", obj.url or "")).strip() or ""
    obj.capa_url = str(body.get("capaUrl", obj.capa_url or "")).strip()
    obj.status = body.get("status", obj.status or Aula.STATUS_PUBLICADA)
    obj.destaque = bool(body.get("destaque", obj.destaque))


def _material_fields(obj: Material, body: dict):
    obj.titulo = str(body.get("titulo", obj.titulo or "")).strip()
    if not obj.titulo:
        raise ValueError("Informe o título do material.")
    obj.descricao = str(body.get("descricao", obj.descricao or "")).strip()
    obj.fase_id = body.get("faseId", obj.fase_id or "onboarding")
    obj.tipo = body.get("tipo", obj.tipo or Material.TIPO_PDF)
    obj.url = str(body.get("url", obj.url or "")).strip() or ""


def _tarefa_fields(obj: Tarefa, body: dict):
    obj.titulo = str(body.get("titulo", obj.titulo or "")).strip()
    if not obj.titulo:
        raise ValueError("Informe o título da tarefa.")
    obj.descricao = str(body.get("descricao", obj.descricao or "")).strip()
    obj.fase_id = body.get("faseId", obj.fase_id or "onboarding")
    prazo = body.get("prazo")
    if prazo:
        obj.prazo = date.fromisoformat(prazo)
    elif not obj.prazo:
        raise ValueError("Informe o prazo da tarefa.")
    obj.prioridade = body.get("prioridade", obj.prioridade or Tarefa.PRIORIDADE_MEDIA)


def _desafio_fields(obj: Desafio, body: dict):
    obj.titulo = str(body.get("titulo", obj.titulo or "")).strip()
    if not obj.titulo:
        raise ValueError("Informe o título do desafio.")
    obj.descricao = str(body.get("descricao", obj.descricao or "")).strip()


def _checklist_fields(obj: ChecklistItem, body: dict):
    obj.texto = str(body.get("texto", obj.texto or "")).strip()
    if not obj.texto:
        raise ValueError("Informe o texto do item.")
    obj.fase_id = body.get("faseId", obj.fase_id or "onboarding")


aula_create, aula_update, aula_delete = _crud_view(Aula, _aula_dict, _aula_fields)
material_create, material_update, material_delete = _crud_view(Material, _material_dict, _material_fields)
tarefa_create, tarefa_update, tarefa_delete = _crud_view(Tarefa, _tarefa_dict, _tarefa_fields)
desafio_create, desafio_update, desafio_delete = _crud_view(Desafio, _desafio_dict, _desafio_fields)
checklist_create, checklist_update, checklist_delete = _crud_view(ChecklistItem, _checklist_item_dict, _checklist_fields)


@csrf_exempt
@auth_required
@mentor_required
@require_http_methods(["POST"])
def aula_mover(request, pk):
    body = _body(request)
    delta = int(body.get("delta", 0))
    aulas = list(Aula.objects.order_by("ordem", "id"))
    idx = next((i for i, a in enumerate(aulas) if a.id == int(pk)), None)
    if idx is None:
        return _erro("Não encontrado.", 404)
    alvo = idx + delta
    if 0 <= alvo < len(aulas):
        aulas[idx].ordem, aulas[alvo].ordem = aulas[alvo].ordem, aulas[idx].ordem
        aulas[idx].save(update_fields=["ordem"])
        aulas[alvo].save(update_fields=["ordem"])
    return _json([_aula_dict(a) for a in Aula.objects.order_by("ordem", "id")])


# ------------------------------------------------------------ alunas (mentor) ----

@csrf_exempt
@auth_required
@mentor_required
@require_http_methods(["POST"])
def aluna_salvar(request):
    body = _body(request)
    nome = str(body.get("nome", "")).strip()
    email = normalizar_email(body.get("email", ""))
    if not nome or not email:
        return _erro("Nome e e-mail são obrigatórios.")
    if "@" not in email or "." not in email.split("@")[-1]:
        return _erro("Informe um e-mail válido.")

    pk = body.get("id")
    if pk:
        obj = Aluna.objects.filter(pk=pk).first()
        if not obj:
            return _erro("Aluna não encontrada.", 404)
    else:
        obj = Aluna()

    duplicada = Aluna.objects.filter(email=email).exclude(pk=obj.pk).exists()
    if duplicada:
        return _erro("Já existe uma aluna cadastrada com este e-mail.")

    obj.nome = nome
    obj.email = email
    obj.whatsapp = str(body.get("whatsapp", "")).strip()
    obj.turma = str(body.get("turma", "")).strip() or "Turma 01"
    data_entrada = body.get("dataEntrada")
    obj.data_entrada = date.fromisoformat(data_entrada) if data_entrada else date.today()
    obj.status = body.get("status", obj.status or Aluna.STATUS_ATIVA)
    obj.objetivo = str(body.get("objetivo", "")).strip()
    obj.notas = str(body.get("notas", "")).strip()
    obj.save()
    return _json(_aluna_dict(obj, full=True), status=201)


@csrf_exempt
@auth_required
@mentor_required
@require_http_methods(["POST"])
def aluna_regenerar_codigo(request, pk):
    obj = Aluna.objects.filter(pk=pk).first()
    if not obj:
        return _erro("Não encontrada.", 404)
    from .models import gerar_codigo_acesso
    obj.codigo = gerar_codigo_acesso()
    obj.save(update_fields=["codigo"])
    return _json(_aluna_dict(obj, full=True))


@csrf_exempt
@auth_required
@mentor_required
@require_http_methods(["POST"])
def aluna_impersonar(request, pk):
    obj = Aluna.objects.filter(pk=pk).first()
    if not obj:
        return _erro("Não encontrada.", 404)
    if obj.status in (Aluna.STATUS_PAUSADA, Aluna.STATUS_ARQUIVADA):
        return _erro("Acesso não está mais ativo.", 403)
    token = _make_token({"role": "aluna", "id": obj.id})
    return _json({"token": token, "aluna": _aluna_dict(obj, full=True)})


# ------------------------------------------------------------ interações (aluna) ----

@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def progresso_aula_toggle(request):
    if not request.tcc_aluna:
        return _erro("Entre com seu acesso de aluna antes.", 403)
    body = _body(request)
    aula = Aula.objects.filter(pk=body.get("aulaId")).first()
    if not aula:
        return _erro("Aula não encontrada.", 404)
    row, criado = ProgressoAula.objects.get_or_create(aluna=request.tcc_aluna, aula=aula)
    if not criado:
        row.delete()
        return _json({"concluida": False})
    return _json({"concluida": True})


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def checklist_toggle(request):
    if not request.tcc_aluna:
        return _erro("Entre com seu acesso de aluna antes.", 403)
    body = _body(request)
    item = ChecklistItem.objects.filter(pk=body.get("itemId")).first()
    if not item:
        return _erro("Item não encontrado.", 404)
    row, criado = ChecklistMarcado.objects.get_or_create(aluna=request.tcc_aluna, item=item)
    if not criado:
        row.delete()
        return _json({"feito": False})
    return _json({"feito": True})


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def tarefa_toggle(request, pk):
    if not request.tcc_aluna:
        return _erro("Entre com seu acesso de aluna antes.", 403)
    tarefa = Tarefa.objects.filter(pk=pk).first()
    if not tarefa:
        return _erro("Tarefa não encontrada.", 404)
    row, criado = TarefaConcluida.objects.get_or_create(aluna=request.tcc_aluna, tarefa=tarefa)
    if not criado:
        row.delete()
        return _json({"feito": False})
    return _json({"feito": True})


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def desafio_status_toggle(request, pk):
    if not request.tcc_aluna:
        return _erro("Entre com seu acesso de aluna antes.", 403)
    campo = _body(request).get("campo")
    if campo not in ("topei", "feito"):
        return _erro("campo inválido.")
    desafio = Desafio.objects.filter(pk=pk).first()
    if not desafio:
        return _erro("Desafio não encontrado.", 404)
    row, _criado = DesafioStatus.objects.get_or_create(aluna=request.tcc_aluna, desafio=desafio)
    if campo == "feito":
        row.feito = not row.feito
        if row.feito:
            row.topei = True
    else:
        row.topei = not row.topei
        if not row.topei:
            row.feito = False
    row.save()
    return _json({"topei": row.topei, "feito": row.feito})


# ------------------------------------------------------------ murais (aluna cria, dono ou mentor apaga) ----

@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def entrega_criar(request):
    if not request.tcc_aluna:
        return _erro("Entre com seu acesso de aluna antes de registrar.", 403)
    body = _body(request)
    titulo = str(body.get("titulo", "")).strip()
    if not titulo:
        return _erro("Dê um título para a entrega.")
    obj = Entrega.objects.create(
        aluna=request.tcc_aluna, fase_id=body.get("faseId", "onboarding"), titulo=titulo,
        link=str(body.get("link", "")).strip(), comentario=str(body.get("comentario", "")).strip(),
    )
    return _json(_entrega_dict(obj), status=201)


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def entrega_apagar(request, pk):
    obj = Entrega.objects.filter(pk=pk).first()
    if not obj:
        return _json({"ok": True})
    if request.tcc_role != "mentor" and obj.aluna_id != getattr(request.tcc_aluna, "id", None):
        return _erro("Sem permissão.", 403)
    obj.delete()
    return _json({"ok": True})


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def evolucao_criar(request):
    if not request.tcc_aluna:
        return _erro("Entre com seu acesso de aluna antes de registrar.", 403)
    body = _body(request)
    texto = str(body.get("texto", "")).strip()
    if not texto:
        return _erro("Escreva o que você evoluiu antes de registrar.")
    obj = Evolucao.objects.create(aluna=request.tcc_aluna, fase_id=body.get("faseId", "") or "", texto=texto)
    return _json(_evolucao_dict(obj), status=201)


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def evolucao_apagar(request, pk):
    obj = Evolucao.objects.filter(pk=pk).first()
    if not obj:
        return _json({"ok": True})
    if request.tcc_role != "mentor" and obj.aluna_id != getattr(request.tcc_aluna, "id", None):
        return _erro("Sem permissão.", 403)
    obj.delete()
    return _json({"ok": True})


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def duvida_criar(request):
    if not request.tcc_aluna:
        return _erro("Entre com seu acesso de aluna antes de perguntar.", 403)
    body = _body(request)
    texto = str(body.get("texto", "")).strip()
    if not texto:
        return _erro("Escreva sua pergunta antes de publicar.")
    obj = Duvida.objects.create(aluna=request.tcc_aluna, fase_id=body.get("faseId", "") or "", texto=texto)
    return _json(_duvida_dict(obj), status=201)


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def duvida_apagar(request, pk):
    obj = Duvida.objects.filter(pk=pk).first()
    if not obj:
        return _json({"ok": True})
    if request.tcc_role != "mentor" and obj.aluna_id != getattr(request.tcc_aluna, "id", None):
        return _erro("Sem permissão.", 403)
    obj.delete()
    return _json({"ok": True})


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def duvida_responder(request, pk):
    duvida = Duvida.objects.filter(pk=pk).first()
    if not duvida:
        return _erro("Não encontrada.", 404)
    texto = str(_body(request).get("texto", "")).strip()
    if not texto:
        return _erro("Escreva uma resposta.")
    from_mentor = request.tcc_role == "mentor"
    if not from_mentor and not request.tcc_aluna:
        return _erro("Entre com seu acesso antes de responder.", 403)
    RespostaDuvida.objects.create(
        duvida=duvida, aluna=None if from_mentor else request.tcc_aluna, texto=texto, from_mentor=from_mentor,
    )
    return _json(_duvida_dict(duvida), status=201)


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def comentario_aula_criar(request):
    body = _body(request)
    texto = str(body.get("texto", "")).strip()
    if not texto:
        return _erro("Escreva um comentário.")
    aula = Aula.objects.filter(pk=body.get("aulaId")).first()
    if not aula:
        return _erro("Aula não encontrada.", 404)
    from_mentor = request.tcc_role == "mentor"
    if not from_mentor and not request.tcc_aluna:
        return _erro("Entre com seu acesso de aluna antes de comentar.", 403)
    obj = ComentarioAula.objects.create(
        aula=aula, aluna=None if from_mentor else request.tcc_aluna, texto=texto, from_mentor=from_mentor,
    )
    return _json(_comentario_dict(obj), status=201)


@csrf_exempt
@auth_required
@require_http_methods(["POST"])
def comentario_aula_apagar(request, pk):
    obj = ComentarioAula.objects.filter(pk=pk).first()
    if not obj:
        return _json({"ok": True})
    if request.tcc_role != "mentor" and obj.aluna_id != getattr(request.tcc_aluna, "id", None):
        return _erro("Sem permissão.", 403)
    obj.delete()
    return _json({"ok": True})
