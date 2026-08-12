import random
import string

from django.db import models


def gerar_codigo_acesso() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "TCC" + "".join(random.choice(chars) for _ in range(4))


def normalizar_codigo(raw: str) -> str:
    return (raw or "").strip().upper().replace(" ", "")


def normalizar_email(raw: str) -> str:
    return (raw or "").strip().lower()


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# As 8 fases da jornada sao um catalogo fixo (espelha FASES no index.html) --
# nao viram tabela porque mentoras nao editam essa lista hoje.
FASE_IDS = [
    "onboarding", "metodo", "narrativa", "calendario",
    "roteiros", "perfil", "prospeccao", "laboratorio",
]
FASE_CHOICES = [(f, f) for f in FASE_IDS]


class Config(TimestampedModel):
    """Linha unica com as configuracoes gerais do portal (equivalente ao antigo conteudo_admin)."""

    aviso_mentora = models.TextField(blank=True, default="")
    fase_atual_id = models.CharField(max_length=32, choices=FASE_CHOICES, default="onboarding")
    mentora_nome = models.CharField(max_length=160, blank=True, default="")
    abas_ocultas = models.JSONField(default=list, blank=True)  # lista de tab ids ocultos pras alunas

    class Meta:
        verbose_name = "Configuracao"
        verbose_name_plural = "Configuracoes"

    @classmethod
    def obter(cls) -> "Config":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Aluna(TimestampedModel):
    STATUS_ATIVA = "ativa"
    STATUS_PAUSADA = "pausada"
    STATUS_CONCLUIDA = "concluida"
    STATUS_ARQUIVADA = "arquivada"
    STATUS_CHOICES = [
        (STATUS_ATIVA, "Ativa"),
        (STATUS_PAUSADA, "Pausada"),
        (STATUS_CONCLUIDA, "Concluida"),
        (STATUS_ARQUIVADA, "Arquivada"),
    ]

    nome = models.CharField(max_length=160)
    email = models.EmailField(unique=True)
    whatsapp = models.CharField(max_length=40, blank=True, default="")
    turma = models.CharField(max_length=80, blank=True, default="Turma 01")
    data_entrada = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ATIVA)
    objetivo = models.TextField(blank=True, default="")
    notas = models.TextField(blank=True, default="")
    codigo = models.CharField(max_length=20, unique=True, default=gerar_codigo_acesso)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.nome

    def save(self, *args, **kwargs):
        self.email = normalizar_email(self.email)
        self.codigo = normalizar_codigo(self.codigo) or gerar_codigo_acesso()
        super().save(*args, **kwargs)


class Aula(TimestampedModel):
    STATUS_PUBLICADA = "publicada"
    STATUS_RASCUNHO = "rascunho"
    STATUS_CHOICES = [(STATUS_PUBLICADA, "Publicada"), (STATUS_RASCUNHO, "Rascunho")]

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")
    fase_id = models.CharField(max_length=32, choices=FASE_CHOICES)
    duracao = models.PositiveIntegerField(default=0)  # minutos
    url = models.URLField(blank=True, default="")
    capa_url = models.URLField(blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PUBLICADA)
    destaque = models.BooleanField(default=False)
    ordem = models.IntegerField(default=0)

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self) -> str:
        return self.titulo


class Material(TimestampedModel):
    TIPO_PDF = "pdf"
    TIPO_VIDEO = "video"
    TIPO_MODELO = "modelo"
    TIPO_LINK = "link"
    TIPO_CHOICES = [
        (TIPO_PDF, "PDF"), (TIPO_VIDEO, "Video"), (TIPO_MODELO, "Modelo"), (TIPO_LINK, "Link"),
    ]

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")
    fase_id = models.CharField(max_length=32, choices=FASE_CHOICES)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default=TIPO_PDF)
    url = models.URLField(blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.titulo


class Tarefa(TimestampedModel):
    PRIORIDADE_ALTA = "alta"
    PRIORIDADE_MEDIA = "media"
    PRIORIDADE_BAIXA = "baixa"
    PRIORIDADE_CHOICES = [
        (PRIORIDADE_ALTA, "Alta"), (PRIORIDADE_MEDIA, "Media"), (PRIORIDADE_BAIXA, "Baixa"),
    ]

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")
    fase_id = models.CharField(max_length=32, choices=FASE_CHOICES)
    prazo = models.DateField()
    prioridade = models.CharField(max_length=20, choices=PRIORIDADE_CHOICES, default=PRIORIDADE_MEDIA)

    class Meta:
        ordering = ["prazo", "id"]

    def __str__(self) -> str:
        return self.titulo


class Desafio(TimestampedModel):
    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.titulo


class ChecklistItem(TimestampedModel):
    fase_id = models.CharField(max_length=32, choices=FASE_CHOICES)
    texto = models.CharField(max_length=200)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.texto


# ---- interacoes da aluna (toggles: a existencia da linha = "marcado") ----

class ProgressoAula(TimestampedModel):
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="progresso_aulas")
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE, related_name="progresso")

    class Meta:
        unique_together = ("aluna", "aula")


class ChecklistMarcado(TimestampedModel):
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="checklist_marcado")
    item = models.ForeignKey(ChecklistItem, on_delete=models.CASCADE, related_name="marcacoes")

    class Meta:
        unique_together = ("aluna", "item")


class TarefaConcluida(TimestampedModel):
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="tarefas_concluidas")
    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name="conclusoes")

    class Meta:
        unique_together = ("aluna", "tarefa")


class DesafioStatus(TimestampedModel):
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="desafios_status")
    desafio = models.ForeignKey(Desafio, on_delete=models.CASCADE, related_name="status_alunas")
    topei = models.BooleanField(default=False)
    feito = models.BooleanField(default=False)

    class Meta:
        unique_together = ("aluna", "desafio")


# ---- murais / conteudo gerado pela aluna ----

class Entrega(TimestampedModel):
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="entregas")
    fase_id = models.CharField(max_length=32, choices=FASE_CHOICES)
    titulo = models.CharField(max_length=200)
    link = models.URLField(blank=True, default="")
    comentario = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]


class Evolucao(TimestampedModel):
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="evolucoes")
    fase_id = models.CharField(max_length=32, choices=FASE_CHOICES, blank=True, default="")
    texto = models.TextField()

    class Meta:
        ordering = ["-created_at"]


class Duvida(TimestampedModel):
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="duvidas")
    fase_id = models.CharField(max_length=32, choices=FASE_CHOICES, blank=True, default="")
    texto = models.TextField()

    class Meta:
        ordering = ["-created_at"]


class RespostaDuvida(TimestampedModel):
    duvida = models.ForeignKey(Duvida, on_delete=models.CASCADE, related_name="respostas")
    # aluna nula quando a resposta e' da mentora
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="respostas_duvida", null=True, blank=True)
    texto = models.TextField()
    from_mentor = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]


class ComentarioAula(TimestampedModel):
    aula = models.ForeignKey(Aula, on_delete=models.CASCADE, related_name="comentarios")
    # aluna nula quando o comentario e' da mentora
    aluna = models.ForeignKey(Aluna, on_delete=models.CASCADE, related_name="comentarios_aula", null=True, blank=True)
    texto = models.TextField()
    from_mentor = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
