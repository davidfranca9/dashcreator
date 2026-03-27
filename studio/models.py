from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.text import slugify

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

    class Meta:
        unique_together = [("user", "workspace")]
        ordering = ["workspace__name", "user__username"]

    def __str__(self) -> str:
        return f"{self.user} @ {self.workspace}"


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


class WorkspaceOwnedModel(TimestampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class Prospect(WorkspaceOwnedModel):
    company = models.CharField(max_length=160)
    contact = models.CharField(max_length=160)
    stage = models.CharField(max_length=30, choices=PROSPECT_STAGE_CHOICES)
    proposal_value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.TextField(blank=True, default="")
    meeting_scheduled = models.BooleanField(default=False)

    class Meta:
        ordering = ["stage", "-updated_at"]

    def __str__(self) -> str:
        return f"{self.company} - {self.contact}"


class Project(WorkspaceOwnedModel):
    company = models.CharField(max_length=160)
    project_name = models.CharField(max_length=180)
    content_type = models.CharField(max_length=120, default="UGC Vertical")
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
        return self.project_name


class WorkspaceSetting(TimestampedModel):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="settings")
    key = models.CharField(max_length=120)
    value = models.CharField(max_length=255)

    class Meta:
        unique_together = [("workspace", "key")]
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.workspace} - {self.key}"
