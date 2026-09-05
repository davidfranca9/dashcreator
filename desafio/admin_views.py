"""Painel da organizadora do Desafio Postaria Mais.

Separado de views.py de proposito: ali e' a API da participante, aqui e' a da
organizadora. A autenticacao tambem e' outra: entra quem e' staff do Django
(mesmo usuario e senha do /admin/), com salt proprio e validade curta, pra que
um token de participante nunca sirva aqui e vice-versa.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import wraps
from uuid import uuid4

from django.contrib.auth import authenticate
from django.core.signing import BadSignature, SignatureExpired, dumps, loads
from django.db.models import Count, Sum
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import scoring
from .models import (
    CheckIn,
    Comentario,
    Conclusao,
    Missao,
    Participante,
    PontoEvento,
    Post,
)

ADMIN_TOKEN_SALT = "desafio-postaria-mais-organizadora"
ADMIN_TOKEN_MAX_AGE = 60 * 60 * 12  # 12 horas


def _json(data, status: int = 200) -> JsonResponse:
    return JsonResponse(data, status=status, safe=False)


def _erro(msg: str, status: int = 400) -> JsonResponse:
    return _json({"erro": msg}, status=status)


def _body(request: HttpRequest) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def staff_required(view):
    """Injeta request.organizadora a partir do token Bearer de staff."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return _erro("Faça login para continuar.", 401)
        try:
            payload = loads(
                header[len("Bearer "):].strip(),
                salt=ADMIN_TOKEN_SALT,
                max_age=ADMIN_TOKEN_MAX_AGE,
            )
        except (BadSignature, SignatureExpired):
            return _erro("Sessão expirada. Entre novamente.", 401)

        from django.contrib.auth import get_user_model

        user = get_user_model().objects.filter(pk=payload.get("uid"), is_staff=True, is_active=True).first()
        if not user:
            return _erro("Acesso não autorizado.", 403)
        request.organizadora = user
        return view(request, *args, **kwargs)

    return wrapper


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def login_admin(request: HttpRequest) -> JsonResponse:
    dados = _body(request)
    user = authenticate(
        username=(dados.get("usuario") or "").strip(),
        password=dados.get("senha") or "",
    )
    # Resposta unica pros dois casos: nao entrega se o usuario existe.
    if not user or not user.is_staff:
        return _erro("Usuário ou senha incorretos.", 401)

    return _json(
        {
            "token": dumps({"uid": user.pk}, salt=ADMIN_TOKEN_SALT, compress=True),
            "nome": user.get_full_name() or user.get_username(),
        }
    )


def _contagem_por_participante(model, campo: str = "id") -> dict:
    return {
        linha["participante_id"]: linha["n"]
        for linha in model.objects.values("participante_id").annotate(n=Count(campo))
    }


def _atividade_por_dia(missoes) -> list[dict]:
    """Movimento em cada dia do desafio: quem apareceu e quem entregou."""
    checkins = {
        linha["data"]: linha["n"] for linha in CheckIn.objects.values("data").annotate(n=Count("id"))
    }
    conclusoes = {
        linha["concluida_em"]: linha["n"]
        for linha in Conclusao.objects.values("concluida_em").annotate(n=Count("id"))
    }
    return [
        {
            "data": missao.data_liberacao.isoformat(),
            "dia": missao.dia,
            "checkins": checkins.get(missao.data_liberacao, 0),
            "conclusoes": conclusoes.get(missao.data_liberacao, 0),
        }
        for missao in missoes
    ]


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
@staff_required
def painel(request: HttpRequest) -> JsonResponse:
    """Tudo que o painel mostra, numa chamada só.

    As contagens saem em queries separadas de proposito: juntar Sum de pontos
    com Count de check-in no mesmo annotate multiplica as linhas do join e o
    total sai errado.
    """
    hoje = timezone.localdate()

    pontos_por = {
        linha["participante_id"]: linha["total"]
        for linha in PontoEvento.objects.values("participante_id").annotate(total=Sum("pontos"))
    }
    checkins_por = _contagem_por_participante(CheckIn)
    conclusoes_por = _contagem_por_participante(Conclusao)
    posts_por = _contagem_por_participante(Post)
    comentarios_por = _contagem_por_participante(Comentario)

    participantes = list(Participante.objects.select_related("indicada_por").all())
    linhas = [
        {
            "id": p.pk,
            "nome": p.nome,
            "email": p.email,
            "whatsapp": p.whatsapp,
            "instagram": p.instagram,
            "codigo_acesso": p.codigo_acesso,
            "ativa": p.ativa,
            "pontos": pontos_por.get(p.pk, 0) or 0,
            "checkins": checkins_por.get(p.pk, 0),
            "missoes": conclusoes_por.get(p.pk, 0),
            "posts": posts_por.get(p.pk, 0),
            "comentarios": comentarios_por.get(p.pk, 0),
            "indicada_por": p.indicada_por.nome if p.indicada_por else "",
            "inscrita_em": p.created_at.isoformat(),
        }
        for p in participantes
    ]

    missoes = list(Missao.objects.all())
    conclusoes = list(Conclusao.objects.select_related("participante", "missao").all())
    por_missao: dict[int, list[Conclusao]] = {}
    for c in conclusoes:
        por_missao.setdefault(c.missao_id, []).append(c)

    total_ativas = sum(1 for p in participantes if p.ativa)
    dados_missoes = [
        {
            "dia": m.dia,
            "titulo": m.titulo,
            "data_liberacao": m.data_liberacao.isoformat(),
            "liberada": hoje >= m.data_liberacao,
            "concluidas": len(por_missao.get(m.pk, [])),
            "no_prazo": sum(1 for c in por_missao.get(m.pk, []) if c.no_prazo),
            "com_comprovacao": sum(1 for c in por_missao.get(m.pk, []) if c.tem_comprovacao),
            "total_ativas": total_ativas,
        }
        for m in missoes
    ]

    comprovacoes = [
        {
            "id": c.pk,
            "participante": c.participante.nome,
            "participante_id": c.participante_id,
            "dia": c.missao.dia,
            "missao": c.missao.titulo,
            "comprovacao": c.comprovacao,
            "no_prazo": c.no_prazo,
            "quando": c.concluida_em.isoformat(),
        }
        for c in sorted(conclusoes, key=lambda c: c.created_at, reverse=True)
        if c.tem_comprovacao
    ]

    posts = Post.objects.select_related("participante").prefetch_related("comentarios__participante")[:60]
    mural = [
        {
            "id": post.pk,
            "autor": post.participante.nome,
            "texto": post.texto,
            "quando": post.created_at.isoformat(),
            "comentarios": [
                {
                    "id": c.pk,
                    "autor": c.participante.nome,
                    "texto": c.texto,
                    "quando": c.created_at.isoformat(),
                }
                for c in post.comentarios.all()
            ],
        }
        for post in posts
    ]

    return _json(
        {
            "metricas": {
                "inscritas": len(participantes),
                "ativas": total_ativas,
                "inscritas_hoje": sum(1 for p in participantes if p.created_at.date() == hoje),
                "checkins_hoje": CheckIn.objects.filter(data=hoje).count(),
                "missoes_concluidas": len(conclusoes),
                "comprovacoes": len(comprovacoes),
                "posts": Post.objects.count(),
                "comentarios": Comentario.objects.count(),
                "indicacoes": Participante.objects.filter(indicada_por__isnull=False).count(),
            },
            "ranking": scoring.ranking(),
            "missoes": dados_missoes,
            "participantes": linhas,
            "comprovacoes": comprovacoes,
            "mural": mural,
            "atividade": _atividade_por_dia(missoes),
            "hoje": hoje.isoformat(),
        }
    )


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@staff_required
def ajustar_pontos(request: HttpRequest) -> JsonResponse:
    """Credito ou desconto lancado na mao pela organizadora.

    Diferente dos pontos automaticos, um ajuste manual nao tem evento natural
    pra deduplicar: se a organizadora lancar dois bonus iguais, os dois valem.
    Por isso a referencia leva um sufixo aleatorio, senao a trava de
    idempotencia engoliria o segundo lancamento.
    """
    dados = _body(request)
    participante = Participante.objects.filter(pk=dados.get("participante_id")).first()
    if not participante:
        return _erro("Participante não encontrada.", 404)

    try:
        pontos = int(dados.get("pontos"))
    except (TypeError, ValueError):
        return _erro("Informe quantos pontos lançar.")
    if pontos == 0:
        return _erro("O ajuste precisa ser diferente de zero.")

    motivo = (dados.get("motivo") or "").strip() or "ajuste manual"
    referencia = f"{timezone.now():%d/%m %H:%M} {motivo[:40]} #{uuid4().hex[:6]}"
    PontoEvento.objects.create(
        participante=participante,
        tipo=PontoEvento.TIPO_AJUSTE,
        pontos=pontos,
        referencia=referencia,
    )
    return _json({"pontos": scoring.total_de(participante)})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@staff_required
def alternar_participante(request: HttpRequest, participante_id: int) -> JsonResponse:
    """Liga ou desliga uma participante. Desligada some do ranking e nao entra
    mais no portal, mas os dados dela ficam."""
    participante = Participante.objects.filter(pk=participante_id).first()
    if not participante:
        return _erro("Participante não encontrada.", 404)

    participante.ativa = not participante.ativa
    participante.save(update_fields=["ativa", "updated_at"])
    return _json({"ativa": participante.ativa})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@staff_required
def mudar_data_missao(request: HttpRequest, dia: int) -> JsonResponse:
    missao = Missao.objects.filter(dia=dia).first()
    if not missao:
        return _erro("Missão não encontrada.", 404)

    bruto = (_body(request).get("data_liberacao") or "").strip()
    try:
        nova = datetime.strptime(bruto, "%Y-%m-%d").date()
    except ValueError:
        return _erro("Data inválida. Use o formato do calendário.")

    missao.data_liberacao = nova
    missao.save(update_fields=["data_liberacao", "updated_at"])
    return _json({"dia": missao.dia, "data_liberacao": missao.data_liberacao.isoformat()})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@staff_required
def remover_post(request: HttpRequest, post_id: int) -> JsonResponse:
    """Tira um post do mural. Os pontos que ele gerou ficam: quem comentou nao
    tem culpa do post ter sido removido."""
    post = Post.objects.filter(pk=post_id).first()
    if not post:
        return _erro("Publicação não encontrada.", 404)
    post.delete()
    return _json({"removido": True})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@staff_required
def remover_comentario(request: HttpRequest, comentario_id: int) -> JsonResponse:
    comentario = Comentario.objects.filter(pk=comentario_id).first()
    if not comentario:
        return _erro("Comentário não encontrado.", 404)
    comentario.delete()
    return _json({"removido": True})
