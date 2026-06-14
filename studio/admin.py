from django.contrib import admin

from .models import AccessCode, ActiveUserSession, InfoProduct, Membership, Niche, Project, Prospect, ServiceCategory, Workspace, WorkspaceSetting


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_beta", "created_at")
    list_filter = ("is_beta",)
    list_editable = ("is_beta",)
    search_fields = ("name", "slug")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "workspace__name")


@admin.register(AccessCode)
class AccessCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "audience", "assigned_user", "is_active", "assigned_at", "created_at")
    list_filter = ("audience", "is_active")
    search_fields = ("code", "assigned_user__username", "assigned_user__email")


@admin.register(ActiveUserSession)
class ActiveUserSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "session_key", "updated_at")
    search_fields = ("user__username", "user__email", "session_key")


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    list_display = ("company", "contact", "contact_type", "stage", "meeting_date", "niche", "proposal_value", "workspace", "updated_at")
    list_filter = ("stage", "meeting_scheduled", "workspace", "niche")
    search_fields = ("company", "contact", "contact_type", "email", "instagram", "whatsapp", "note")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("service_category", "company", "closing_source", "niche", "stage", "status", "total_value", "workspace", "due_date")
    list_filter = ("stage", "status", "workspace", "niche")
    search_fields = ("service_category__name", "project_name", "company", "closing_source", "niche__name")


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "updated_at")
    list_filter = ("workspace",)
    search_fields = ("name",)


@admin.register(InfoProduct)
class InfoProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "status", "price", "platform", "workspace", "updated_at")
    list_filter = ("workspace", "status", "product_type", "platform")
    search_fields = ("name", "sales_link")


@admin.register(Niche)
class NicheAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "updated_at")
    list_filter = ("workspace",)
    search_fields = ("name",)


@admin.register(WorkspaceSetting)
class WorkspaceSettingAdmin(admin.ModelAdmin):
    list_display = ("workspace", "key", "value", "updated_at")
    list_filter = ("workspace",)
    search_fields = ("workspace__name", "key", "value")
