from __future__ import annotations

from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils.text import slugify
from PIL import Image, ImageOps

from .constants import PROJECT_STAGE_CHOICES, PROJECT_STATUS_CHOICES, PROSPECT_STAGE_CHOICES


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
    company = models.CharField(max_length=160)
    project_name = models.CharField(max_length=180, blank=True, default="")
    content_type = models.CharField(max_length=120, blank=True, default="")
    closing_source = models.CharField(max_length=120, blank=True, default="")
    niche = models.ForeignKey(Niche, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    service_category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    stage = models.CharField(max_length=30, choices=PROJECT_STAGE_CHOICES, default="Fechado")
    status = models.CharField(max_length=40, choices=PROJECT_STATUS_CHOICES, default="Briefing")
    total_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    entry_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    received_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    deliverables_count = models.PositiveIntegerField(default=1)
    progress = models.PositiveSmallIntegerField(default=0)
    close_date = models.DateField()
    due_date = models.DateField()

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


class WorkspaceSetting(TimestampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="settings")
    key = models.CharField(max_length=120)
    value = models.CharField(max_length=255)

    class Meta:
        unique_together = [("workspace", "key")]
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.workspace} - {self.key}"
