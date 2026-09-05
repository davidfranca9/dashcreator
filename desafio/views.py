"""API do Desafio Postaria Mais.

Autenticacao no mesmo esquema do tcc_portal (token assinado no Bearer), mas
com cadastro self-service: a lead se inscreve com email, recebe um codigo
DES-XXXXX e usa email + codigo pra voltar depois.
"""

from __future__ import annotations

import json
from functools import wraps

from django.conf import settings
from django.core.mail import send_mail
from django.core.signing import BadSignature, SignatureExpired, dumps, loads
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
    Post,
    normalizar_email,
)

TOKEN_SALT = "desafio-postaria-mais-auth"
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


def _make_token(participante: Participante) -> str:
    return dumps({"id": participante.pk}, salt=TOKEN_SALT, compress=True)


def auth_required(view):
    """Injeta request.participante a partir do token Bearer."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return _erro("Faça login para continuar.", 401)
        try:
            payload = loads(header[len("Bearer "):].strip(), salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        except (BadSignature, SignatureExpired):
            return _erro("Sessão expirada. Entre novamente.", 401)

        participante = Participante.objects.filter(pk=payload.get("id"), ativa=True).first()
        if not participante:
            return _erro("Cadastro não encontrado.", 401)
        request.participante = participante
        return view(request, *args, **kwargs)

    return wrapper


def _dados_participante(participante: Participante) -> dict:
    return {
        "id": participante.pk,
        "nome": participante.nome,
        "email": participante.email,
        "instagram": participante.instagram,
        "codigo_acesso": participante.codigo_acesso,
        "pontos": scoring.total_de(participante),
    }


def _enviar_codigo(participante: Participante) -> None:
    """Manda o codigo de acesso por email. Falha de email nao derruba o
    cadastro: a participante ja recebe o codigo na tela tambem."""
    corpo = (
        f"Oi, {participante.nome}!\n\n"
        "Sua inscrição no Desafio Postaria Mais está confirmada.\n\n"
        f"Seu código de acesso: {participante.codigo_acesso}\n\n"
        "Guarde esse código: é com ele (e com o seu email) que você entra na plataforma do desafio.\n\n"
        "Te vejo lá!"
    )
    try:
        send_mail(
            "Seu acesso ao Desafio Postaria Mais",
            corpo,
            settings.DEFAULT_FROM_EMAIL,
            [participante.email],
            fail_silently=True,
        )
    except Exception:  # pragma: no cover - rede/SMTP
        pass


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def cadastro(request: HttpRequest) -> JsonResponse:
    dados = _body(request)
    nome = (dados.get("nome") or "").strip()
    email = normalizar_email(dados.get("email"))
    whatsapp = (dados.get("whatsapp") or "").strip()
    instagram = (dados.get("instagram") or "").strip().lstrip("@")

    if not nome or not email:
        return _erro("Preencha nome e email.")
    if "@" not in email or "." not in email.split("@")[-1]:
        return _erro("Esse email não parece válido.")

    existente = Participante.objects.filter(email=email).first()
    if existente:
        # Ja inscrita: reenvia o codigo em vez de barrar, que e' o que a
        # pessoa quer quando repete o cadastro por ter perdido o acesso.
        _enviar_codigo(existente)
        return _json(
            {
                "ja_inscrita": True,
                "mensagem": "Você já está inscrita. Reenviamos seu código de acesso por email.",
            }
        )

    participante = Participante.objects.create(
        nome=nome, email=email, whatsapp=whatsapp, instagram=instagram
    )
    _enviar_codigo(participante)
    return _json(
        {
            "token": _make_token(participante),
            "participante": _dados_participante(participante),
        },
        status=201,
    )


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def login(request: HttpRequest) -> JsonResponse:
    dados = _body(request)
    email = normalizar_email(dados.get("email"))
    codigo = (dados.get("codigo") or "").strip().upper()

    participante = Participante.objects.filter(email=email, codigo_acesso=codigo, ativa=True).first()
    if not participante:
        return _erro("Email ou código incorreto.", 401)

    return _json({"token": _make_token(participante), "participante": _dados_participante(participante)})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def reenviar_codigo(request: HttpRequest) -> JsonResponse:
    email = normalizar_email(_body(request).get("email"))
    participante = Participante.objects.filter(email=email, ativa=True).first()
    if participante:
        _enviar_codigo(participante)
    # Resposta identica exista ou nao: nao entrega quem esta inscrita.
    return _json({"mensagem": "Se esse email estiver inscrito, o código chega em instantes."})


@csrf_exempt
@require_http_methods(["GET", "OPTIONS"])
@auth_required
def estado(request: HttpRequest) -> JsonResponse:
    """Tudo que a tela precisa numa chamada só: missões, progresso, ranking e mural."""
    participante = request.participante
    hoje = timezone.localdate()

    concluidas = {c.missao_id: c for c in participante.conclusoes.all()}
    missoes = []
    for missao in Missao.objects.all():
        conclusao = concluidas.get(missao.pk)
        missoes.append(
            {
                "dia": missao.dia,
                "titulo": missao.titulo,
                "data_liberacao": missao.data_liberacao.isoformat(),
                "liberada": hoje >= missao.data_liberacao,
                "concluida": conclusao is not None,
                "comprovacao": conclusao.comprovacao if conclusao else "",
            }
        )

    return _json(
        {
            "participante": _dados_participante(participante),
            "missoes": missoes,
            "ranking": scoring.ranking(limite=10),
            "extrato": scoring.extrato(participante),
            "feed": _feed(),
            "checkin_feito_hoje": participante.checkins.filter(data=hoje).exists(),
        }
    )


def _feed() -> list[dict]:
    posts = (
        Post.objects.select_related("participante")
        .prefetch_related("comentarios__participante")
        .all()[:50]
    )
    return [
        {
            "id": post.pk,
            "autor": post.participante.nome,
            "autor_id": post.participante_id,
            "texto": post.texto,
            "quando": post.created_at.isoformat(),
            "comentarios": [
                {"autor": c.participante.nome, "texto": c.texto, "quando": c.created_at.isoformat()}
                for c in post.comentarios.all()
            ],
        }
        for post in posts
    ]


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@auth_required
def checkin(request: HttpRequest) -> JsonResponse:
    registro, criado = CheckIn.objects.get_or_create(
        participante=request.participante, data=timezone.localdate()
    )
    if criado:
        scoring.pontuar_checkin(registro)
    return _json({"ja_registrado": not criado, "pontos": scoring.total_de(request.participante)})


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@auth_required
def concluir_missao(request: HttpRequest, dia: int) -> JsonResponse:
    participante = request.participante
    missao = Missao.objects.filter(dia=dia).first()
    if not missao:
        return _erro("Missão não encontrada.", 404)

    hoje = timezone.localdate()
    if hoje < missao.data_liberacao:
        return _erro(f"Essa missão libera em {missao.data_liberacao:%d/%m}.", 403)

    comprovacao = (_body(request).get("comprovacao") or "").strip()
    conclusao, criada = Conclusao.objects.get_or_create(
        participante=participante,
        missao=missao,
        defaults={"comprovacao": comprovacao, "concluida_em": hoje},
    )
    if not criada and comprovacao and comprovacao != conclusao.comprovacao:
        # Voltou pra anexar/atualizar a comprovacao: os pontos ja pagos ficam,
        # e o bonus de comprovacao entra agora (a trava cuida do resto).
        conclusao.comprovacao = comprovacao
        conclusao.save(update_fields=["comprovacao", "updated_at"])

    scoring.pontuar_conclusao(conclusao)
    return _json(
        {
            "ja_concluida": not criada,
            "no_prazo": conclusao.no_prazo,
            "pontos": scoring.total_de(participante),
        }
    )


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@auth_required
def publicar(request: HttpRequest) -> JsonResponse:
    texto = (_body(request).get("texto") or "").strip()
    if len(texto) < 3:
        return _erro("Escreva sua publicação antes de enviar.")

    post = Post.objects.create(participante=request.participante, texto=texto)
    scoring.pontuar_publicacao(post)
    return _json({"id": post.pk, "pontos": scoring.total_de(request.participante)}, status=201)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
@auth_required
def comentar(request: HttpRequest, post_id: int) -> JsonResponse:
    texto = (_body(request).get("texto") or "").strip()
    if len(texto) < 2:
        return _erro("Escreva seu comentário antes de enviar.")

    post = Post.objects.filter(pk=post_id).first()
    if not post:
        return _erro("Publicação não encontrada.", 404)

    comentario, criado = Comentario.objects.get_or_create(
        post=post, participante=request.participante, defaults={"texto": texto}
    )
    if criado:
        scoring.pontuar_comentario(comentario)
    return _json(
        {
            "ja_comentado": not criado,
            "pontos": scoring.total_de(request.participante),
        }
    )


@require_http_methods(["GET", "OPTIONS"])
def ranking(request: HttpRequest) -> JsonResponse:
    return _json({"ranking": scoring.ranking(limite=50)})
