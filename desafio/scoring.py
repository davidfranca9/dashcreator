"""Motor de pontuacao do Desafio Postaria Mais.

Regras vindas do briefing (PDF "Ajustes - DEV - Plataforma"):

    Publicacao na comunidade ....... 5 pts por publicacao
    Missao concluida ............... 20 pts
    Conclusao dentro do prazo ...... +10 pts (entregue no dia da liberacao)
    Envio da comprovacao ........... +5 pts (mandou link/print)
    Streak ......................... 3 dias = 7, 5 dias = 15, 7 dias = 50
    Comentario em post de colega ... 2 pts (uma vez por post, post de outra pessoa)
    Check-in diario ................ 5 pts por dia

Todo credito passa por `_creditar`, que usa a unique_together de PontoEvento
como trava de idempotencia: chamar a mesma regra duas vezes pro mesmo evento
nao dobra a pontuacao. Isso importa porque as views chamam essas funcoes em
fluxos que o usuario pode repetir (reenviar comprovacao, recarregar a pagina).
"""

from django.db import IntegrityError, transaction
from django.db.models import Sum

from .models import CheckIn, Comentario, Conclusao, Participante, PontoEvento, Post

PONTOS_PUBLICACAO = 5
PONTOS_MISSAO = 20
PONTOS_PRAZO = 10
PONTOS_COMPROVACAO = 5
PONTOS_COMENTARIO = 2
PONTOS_CHECKIN = 5

# Bonus por sequencia de dias concluidos: {dias: pontos}
BONUS_STREAK = {3: 7, 5: 15, 7: 50}


def _creditar(participante: Participante, tipo: str, pontos: int, referencia: str) -> PontoEvento | None:
    """Credita uma vez so. Devolve None se aquele evento ja tinha sido pago.

    O insert vai dentro de um savepoint proprio: sem isso, o IntegrityError da
    trava de idempotencia quebraria a transacao inteira de quem chamou (a view
    nao conseguiria mais rodar query nenhuma depois).
    """
    try:
        with transaction.atomic():
            return PontoEvento.objects.create(
                participante=participante,
                tipo=tipo,
                pontos=pontos,
                referencia=str(referencia),
            )
    except IntegrityError:
        return None


def pontuar_publicacao(post: Post) -> None:
    _creditar(post.participante, PontoEvento.TIPO_PUBLICACAO, PONTOS_PUBLICACAO, post.pk)


def pontuar_comentario(comentario: Comentario) -> None:
    """So pontua comentario em post de OUTRA participante.

    Comentar no proprio post nao vale ponto, senao bastava postar e comentar
    sozinha pra subir no ranking.
    """
    if comentario.post.participante_id == comentario.participante_id:
        return
    _creditar(comentario.participante, PontoEvento.TIPO_COMENTARIO, PONTOS_COMENTARIO, comentario.post_id)


def pontuar_checkin(checkin: CheckIn) -> None:
    _creditar(checkin.participante, PontoEvento.TIPO_CHECKIN, PONTOS_CHECKIN, checkin.data.isoformat())


def pontuar_conclusao(conclusao: Conclusao) -> None:
    """Credita a missao e, quando couber, os bonus de prazo e comprovacao.

    Roda tambem quando a participante volta e anexa a comprovacao depois: os
    creditos ja pagos sao ignorados pela trava de idempotencia e so o novo
    entra.
    """
    participante = conclusao.participante
    referencia = conclusao.missao_id

    _creditar(participante, PontoEvento.TIPO_MISSAO, PONTOS_MISSAO, referencia)
    if conclusao.no_prazo:
        _creditar(participante, PontoEvento.TIPO_PRAZO, PONTOS_PRAZO, referencia)
    if conclusao.tem_comprovacao:
        _creditar(participante, PontoEvento.TIPO_COMPROVACAO, PONTOS_COMPROVACAO, referencia)

    avaliar_streak(participante)


def _maior_sequencia(dias: list) -> int:
    """Maior sequencia de dias consecutivos dentro das datas informadas."""
    if not dias:
        return 0
    ordenados = sorted(set(dias))
    melhor = atual = 1
    for anterior, seguinte in zip(ordenados, ordenados[1:]):
        atual = atual + 1 if (seguinte - anterior).days == 1 else 1
        melhor = max(melhor, atual)
    return melhor


def avaliar_streak(participante: Participante) -> None:
    """Paga os bonus de streak alcancados ate agora.

    Os niveis sao cumulativos: quem chega a 7 dias seguidos recebeu tambem os
    bonus de 3 e de 5 pelo caminho (cada um creditado uma unica vez).
    """
    dias = list(participante.conclusoes.values_list("concluida_em", flat=True))
    sequencia = _maior_sequencia(dias)
    for nivel, pontos in sorted(BONUS_STREAK.items()):
        if sequencia >= nivel:
            _creditar(participante, PontoEvento.TIPO_STREAK, pontos, nivel)


def total_de(participante: Participante) -> int:
    return participante.pontos.aggregate(total=Sum("pontos"))["total"] or 0


def ranking(limite: int | None = None) -> list[dict]:
    """Placar geral, do maior pro menor. Empate desempata por quem chegou
    primeiro naquela pontuacao (participante mais antiga na frente)."""
    linhas = (
        Participante.objects.filter(ativa=True)
        .annotate(total=Sum("pontos__pontos"))
        .order_by("-total", "created_at")
    )
    if limite:
        linhas = linhas[:limite]
    return [
        {
            "participante_id": p.pk,
            "nome": p.nome,
            "instagram": p.instagram,
            "total": p.total or 0,
            "posicao": indice + 1,
        }
        for indice, p in enumerate(linhas)
    ]


def extrato(participante: Participante) -> list[dict]:
    """Historico de pontos, pra conseguir explicar de onde veio cada ponto."""
    return [
        {
            "tipo": evento.get_tipo_display(),
            "pontos": evento.pontos,
            "quando": evento.created_at,
        }
        for evento in participante.pontos.all()
    ]
