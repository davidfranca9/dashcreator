from __future__ import annotations

from datetime import timedelta
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils.text import slugify
from PIL import Image, ImageOps

from .constants import (
    IMAGE_LICENSE_TERM_CHOICES,
    PROJECT_DISTRIBUTION_CHOICES,
    PROJECT_STAGE_CHOICES,
    PROJECT_STATUS_CHOICES,
    PROSPECT_STAGE_CHOICES,
    SERVICE_TYPE_CHOICES,
)


def normalize_access_code(raw_code: str) -> str:
    return (raw_code or "").strip().upper().replace(" ", "")


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Workspace(TimestampedModel):
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    business_full_name = models.CharField(max_length=160, blank=True, default="")
    business_address = models.CharField(max_length=255, blank=True, default="")
    business_zip_code = models.CharField(max_length=9, blank=True, default="")
    business_street = models.CharField(max_length=180, blank=True, default="")
    business_number = models.CharField(max_length=20, blank=True, default="")
    business_complement = models.CharField(max_length=120, blank=True, default="")
    business_cnpj = models.CharField(max_length=18, blank=True, default="")
    business_pis = models.CharField(max_length=20, blank=True, default="")
    instagram_url = models.URLField(blank=True, default="")
    tiktok_url = models.URLField(blank=True, default="")
    portfolio_url = models.URLField(blank=True, default="")

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            base_slug = slugify(self.name) or "workspace"
            slug = base_slug
            suffix = 2
            while Workspace.objects.exclude(pk=self.pk).filter(slug=slug).exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Membership(TimestampedModel):
    ROLE_OWNER = "owner"
    ROLE_ADMIN = "admin"
    ROLE_MEMBER = "member"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Owner"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_MEMBER, "Member"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_OWNER)
    avatar = models.ImageField(upload_to="ugc_fotos/", blank=True, null=True)

    class Meta:
        unique_together = [("user", "workspace")]
        ordering = ["workspace__name", "user__username"]

    def __str__(self) -> str:
        return f"{self.user} @ {self.workspace}"

    def save(self, *args, **kwargs) -> None:
        old_avatar_name = None
        if self.pk:
            old_avatar_name = Membership.objects.filter(pk=self.pk).values_list("avatar", flat=True).first()

        avatar_file = self.avatar
        if avatar_file and (not hasattr(avatar_file, "_committed") or not avatar_file._committed):
            avatar_file.seek(0)
            with Image.open(avatar_file) as image:
                # Corrige a orientacao original do arquivo antes de processar.
                image = ImageOps.exif_transpose(image)
                # Garante um formato consistente para salvar em JPEG.
                image = image.convert("RGB")
                # Reduz a imagem mantendo proporcao dentro do limite maximo de 1080x1080.
                image.thumbnail((1080, 1080), Image.Resampling.LANCZOS)

                buffer = BytesIO()
                # Salva a versao final comprimida em JPEG para reduzir bastante o tamanho.
                image.save(buffer, format="JPEG", quality=75, optimize=True)

            base_name = slugify(getattr(avatar_file, "name", "").rsplit(".", 1)[0]) or f"avatar-{self.user_id or 'workspace'}"
            self.avatar.save(f"{base_name}.jpg", ContentFile(buffer.getvalue()), save=False)

        super().save(*args, **kwargs)

        if old_avatar_name and self.avatar and old_avatar_name != self.avatar.name:
            self.avatar.storage.delete(old_avatar_name)

    @property
    def initials(self) -> str:
        base_name = (self.user.get_full_name() or self.user.username or self.user.email or "Perfil").strip()
        pieces = [item[0].upper() for item in base_name.split() if item]
        if len(pieces) >= 2:
            return "".join(pieces[:2])
        if pieces:
            return pieces[0]
        return "P"


class AccessCode(TimestampedModel):
    AUDIENCE_PAID = "paid"
    AUDIENCE_NON_PAID = "non_paid"
    AUDIENCE_CHOICES = [
        (AUDIENCE_PAID, "Pagante"),
        (AUDIENCE_NON_PAID, "Nao pagante"),
    ]

    code = models.CharField(max_length=40, unique=True)
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES)
    assigned_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="access_code_entry",
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["audience", "code"]

    def __str__(self) -> str:
        return f"{self.code} ({self.get_audience_display()})"

    def save(self, *args, **kwargs) -> None:
        self.code = normalize_access_code(self.code)
        super().save(*args, **kwargs)


class ActiveUserSession(TimestampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="active_session")
    session_key = models.CharField(max_length=40, unique=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"{self.user} - {self.session_key}"


class WorkspaceOwnedModel(TimestampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class ServiceCategory(WorkspaceOwnedModel):
    name = models.CharField(max_length=160)

    class Meta:
        ordering = ["name"]
        unique_together = [("workspace", "name")]

    def __str__(self) -> str:
        return self.name


class Niche(WorkspaceOwnedModel):
    name = models.CharField(max_length=160)

    class Meta:
        ordering = ["name"]
        unique_together = [("workspace", "name")]

    def __str__(self) -> str:
        return self.name


class Prospect(WorkspaceOwnedModel):
    company = models.CharField(max_length=160)
    contact = models.CharField(max_length=160)
    contact_type = models.CharField(max_length=120, blank=True, default="")
    stage = models.CharField(max_length=30, choices=PROSPECT_STAGE_CHOICES)
    contact_date = models.DateField(null=True, blank=True)
    meeting_date = models.DateField(null=True, blank=True)
    niche = models.ForeignKey(Niche, on_delete=models.SET_NULL, null=True, blank=True, related_name="prospects")
    email = models.EmailField(blank=True, default="")
    instagram = models.CharField(max_length=160, blank=True, default="")
    whatsapp = models.CharField(max_length=40, blank=True, default="")
    proposal_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, default="")
    meeting_scheduled = models.BooleanField(default=False)

    class Meta:
        ordering = ["stage", "-updated_at"]

    def __str__(self) -> str:
        return f"{self.company} - {self.contact}"


class Project(WorkspaceOwnedModel):
    CONTRACT_STATUS_PENDING = "pending"
    CONTRACT_STATUS_GENERATED = "generated"
    CONTRACT_STATUS_DISMISSED = "dismissed"
    CONTRACT_STATUS_CHOICES = [
        (CONTRACT_STATUS_PENDING, "Pendente"),
        (CONTRACT_STATUS_GENERATED, "Contrato gerado"),
        (CONTRACT_STATUS_DISMISSED, "Dispensado"),
    ]

    company = models.CharField(max_length=160)
    company_legal_name = models.CharField(max_length=180, blank=True, default="")
    company_cnpj = models.CharField(max_length=18, blank=True, default="")
    company_address = models.CharField(max_length=255, blank=True, default="")
    company_phone = models.CharField(max_length=40, blank=True, default="")
    project_name = models.CharField(max_length=180, blank=True, default="")
    content_type = models.CharField(max_length=120, blank=True, default="")
    closing_source = models.CharField(max_length=120, blank=True, default="")
    content_distribution = models.CharField(max_length=20, choices=PROJECT_DISTRIBUTION_CHOICES, blank=True, default="")
    image_license_term_days = models.PositiveSmallIntegerField(choices=IMAGE_LICENSE_TERM_CHOICES, null=True, blank=True)
    niche = models.ForeignKey(Niche, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    service_category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    service_type = models.CharField(
        max_length=40,
        choices=SERVICE_TYPE_CHOICES,
        default="outros",
        blank=True,
    )
    stage = models.CharField(max_length=30, choices=PROJECT_STAGE_CHOICES, default="Fechado")
    status = models.CharField(max_length=40, choices=PROJECT_STATUS_CHOICES, default="Briefing")
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    entry_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deliverables_count = models.PositiveIntegerField(default=1)
    progress = models.PositiveSmallIntegerField(default=0)
    payment_due_date = models.DateField(null=True, blank=True)
    meeting_scheduled = models.BooleanField(default=False)
    meeting_date = models.DateField(null=True, blank=True)
    note = models.TextField(blank=True, default="")
    contract_status = models.CharField(
        max_length=20,
        choices=CONTRACT_STATUS_CHOICES,
        default=CONTRACT_STATUS_PENDING,
    )
    close_date = models.DateField()
    due_date = models.DateField()

    # Campos específicos por tipo de serviço (brief Dash Creator seção 4).
    # Cada um aparece no form apenas para os tipos que listam o campo;
    # os demais ficam null/0/"" e não são exibidos nem cobrados pela UI.
    videos_count = models.PositiveIntegerField(null=True, blank=True)
    stories_count = models.PositiveIntegerField(null=True, blank=True)
    story_coverage_date = models.DateField(null=True, blank=True)
    posts_per_month = models.PositiveIntegerField(null=True, blank=True)
    videos_per_month = models.PositiveIntegerField(null=True, blank=True)
    contract_duration_months = models.PositiveSmallIntegerField(null=True, blank=True)
    monthly_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    managed_creators_count = models.PositiveIntegerField(null=True, blank=True)
    affiliate_program = models.CharField(max_length=160, blank=True, default="")
    sold_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    extra_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    withdrawal_date = models.DateField(null=True, blank=True)
    publication_date = models.DateField(null=True, blank=True)
    profile_managed = models.CharField(max_length=160, blank=True, default="")
    briefing = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["stage", "due_date", "-updated_at"]

    def __str__(self) -> str:
        return self.service_category_name

    @property
    def service_category_name(self) -> str:
        if self.service_category_id:
            return self.service_category.name
        if self.project_name:
            return self.project_name
        return self.company

    @property
    def image_usage_expires_on(self):
        if self.content_distribution != "Ads" or not self.image_license_term_days:
            return None
        return self.due_date + timedelta(days=self.image_license_term_days)


class ProjectInstallment(WorkspaceOwnedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="installments")
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)
    paid_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "pk"]

    def __str__(self) -> str:
        return f"Parcela {self.amount} em {self.due_date}"


class FinanceEntry(WorkspaceOwnedModel):
    KIND_INCOMING = "incoming"
    KIND_OUTGOING = "outgoing"
    KIND_CHOICES = [
        (KIND_INCOMING, "Entrada"),
        (KIND_OUTGOING, "Saida"),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    occurred_on = models.DateField()
    description = models.CharField(max_length=180, blank=True, default="")

    class Meta:
        ordering = ["-occurred_on", "-updated_at"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} - {self.amount}"


class FixedCost(WorkspaceOwnedModel):
    KIND_TOOL = "tool"
    KIND_COLLABORATOR = "collaborator"
    KIND_CHOICES = [
        (KIND_TOOL, "Ferramenta"),
        (KIND_COLLABORATOR, "Colaborador"),
    ]
    RECURRENCE_MONTHLY = "monthly"
    RECURRENCE_ANNUAL = "annual"
    RECURRENCE_CHOICES = [
        (RECURRENCE_MONTHLY, "Mensal"),
        (RECURRENCE_ANNUAL, "Anual"),
    ]
    MONTH_CHOICES = [
        (1, "Janeiro"),
        (2, "Fevereiro"),
        (3, "Março"),
        (4, "Abril"),
        (5, "Maio"),
        (6, "Junho"),
        (7, "Julho"),
        (8, "Agosto"),
        (9, "Setembro"),
        (10, "Outubro"),
        (11, "Novembro"),
        (12, "Dezembro"),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default=RECURRENCE_MONTHLY)
    due_day = models.PositiveSmallIntegerField(default=1)
    due_month = models.PositiveSmallIntegerField(choices=MONTH_CHOICES, default=1)
    icon = models.CharField(max_length=60, blank=True, default="")

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} - {self.name}"

    def monthly_equivalent(self) -> "Decimal":
        from decimal import Decimal as _Decimal
        if self.recurrence == self.RECURRENCE_ANNUAL:
            return (_Decimal(self.amount or 0) / _Decimal(12)).quantize(_Decimal("0.01"))
        return _Decimal(self.amount or 0)


class WorkspaceSetting(TimestampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="settings")
    key = models.CharField(max_length=120)
    value = models.CharField(max_length=255)

    class Meta:
        unique_together = [("workspace", "key")]
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.workspace} - {self.key}"
