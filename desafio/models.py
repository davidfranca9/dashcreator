"""Modelos do Desafio Postaria Mais.

App separado do tcc_portal de proposito: o publico aqui e' lead novo que se
cadastra sozinho pelo email (nao e' aluna da mentoria), o ciclo de vida e' de
7 dias e a gamificacao e' exclusiva desse produto.
"""

import random
import string

from django.db import models


def gerar_codigo_acesso() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem I/O/0/1 pra nao confundir na leitura
    return "DES-" + "".join(random.choice(chars) for _ in range(5))


def normalizar_email(raw: str) -> str:
    return (raw or "").strip().lower()


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Participante(TimestampedModel):
    """Lead inscrita no desafio. Cadastro self-service por email."""

    nome = models.CharField(max_length=160)
    email = models.EmailField(unique=True)
    whatsapp = models.CharField(max_length=40, blank=True, default="")
    instagram = models.CharField(max_length=80, blank=True, default="")
    codigo_acesso = models.CharField(max_length=20, unique=True, default=gerar_codigo_acesso)
    ativa = models.BooleanField(default=True)
    # Quem indicou essa participante (chegou pelo link ?ref=CODIGO de alguem).
    # O briefing nao definiu pontuacao por indicacao, entao aqui so registra a
    # rede; se virar regra de ponto depois, o dado ja esta guardado.
    indicada_por = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="indicadas"
    )

    class Meta:
        ordering = ["nome"]

    def save(self, *args, **kwargs) -> None:
        self.email = normalizar_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.nome} <{self.email}>"


class Missao(TimestampedModel):
    """Catalogo das 7 missoes. O texto completo de cada missao mora no
    frontend (landing/desafio/dashboard-missions.html); aqui fica so o que o
    backend precisa pra validar liberacao e pontuar."""

    dia = models.PositiveSmallIntegerField(unique=True)
    titulo = models.CharField(max_length=160)
    data_liberacao = models.DateField()

    class Meta:
        ordering = ["dia"]

    def __str__(self) -> str:
        return f"Dia {self.dia:02d}: {self.titulo}"


class Conclusao(TimestampedModel):
    """Missao concluida por uma participante, com a comprovacao enviada."""

    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name="conclusoes")
    missao = models.ForeignKey(Missao, on_delete=models.CASCADE, related_name="conclusoes")
    comprovacao = models.TextField(blank=True, default="")
    concluida_em = models.DateField()

    class Meta:
        ordering = ["-concluida_em"]
        unique_together = [("participante", "missao")]

    @property
    def no_prazo(self) -> bool:
        """Entregue no mesmo dia em que a missao foi liberada."""
        return self.concluida_em == self.missao.data_liberacao

    @property
    def tem_comprovacao(self) -> bool:
        return bool(self.comprovacao.strip())

    def __str__(self) -> str:
        return f"{self.participante.nome} concluiu dia {self.missao.dia}"


class Post(TimestampedModel):
    """Publicacao no mural da comunidade."""

    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name="posts")
    texto = models.TextField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.participante.nome}: {self.texto[:40]}"


class Comentario(TimestampedModel):
    """Comentario no post de outra participante.

    unique_together (post, participante) garante a regra do briefing: uma
    pessoa so pontua uma vez por post, nao da pra farmar ponto comentando
    varias vezes no mesmo lugar.
    """

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comentarios")
    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name="comentarios")
    texto = models.TextField()

    class Meta:
        ordering = ["created_at"]
        unique_together = [("post", "participante")]

    def __str__(self) -> str:
        return f"{self.participante.nome} comentou em {self.post_id}"


class CheckIn(TimestampedModel):
    """Presenca diaria na plataforma. Um por participante por dia."""

    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name="checkins")
    data = models.DateField()

    class Meta:
        ordering = ["-data"]
        unique_together = [("participante", "data")]

    def __str__(self) -> str:
        return f"{self.participante.nome} em {self.data}"


class PontoEvento(TimestampedModel):
    """Extrato de pontos. Cada linha diz de onde veio cada ponto.

    Guardar o extrato (em vez de so um total) e' proposital: em competicao com
    podio, alguem vai questionar a pontuacao, e sem historico nao da pra
    explicar nem auditar.
    """

    TIPO_PUBLICACAO = "publicacao"
    TIPO_MISSAO = "missao"
    TIPO_PRAZO = "prazo"
    TIPO_COMPROVACAO = "comprovacao"
    TIPO_STREAK = "streak"
    TIPO_COMENTARIO = "comentario"
    TIPO_CHECKIN = "checkin"
    TIPO_CHOICES = [
        (TIPO_PUBLICACAO, "Publicação na comunidade"),
        (TIPO_MISSAO, "Missão concluída"),
        (TIPO_PRAZO, "Conclusão dentro do prazo"),
        (TIPO_COMPROVACAO, "Envio da comprovação"),
        (TIPO_STREAK, "Sequência de dias"),
        (TIPO_COMENTARIO, "Comentário em post de colega"),
        (TIPO_CHECKIN, "Check-in diário"),
    ]

    participante = models.ForeignKey(Participante, on_delete=models.CASCADE, related_name="pontos")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    pontos = models.IntegerField()
    # Chave de idempotencia: impede creditar o mesmo evento duas vezes
    # (ex: reenviar comprovacao da mesma missao, streak de 3 dias recontado).
    referencia = models.CharField(max_length=80)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("participante", "tipo", "referencia")]

    def __str__(self) -> str:
        return f"{self.participante.nome} +{self.pontos} ({self.tipo})"
