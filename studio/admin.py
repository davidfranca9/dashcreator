from django.contrib import admin

from .models import Membership, Project, Prospect, Workspace, WorkspaceSetting


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email", "workspace__name")


@admin.register(Prospect)
class ProspectAdmin(admin.ModelAdmin):
    list_display = ("company", "contact", "stage", "proposal_value", "meeting_scheduled", "workspace", "updated_at")
    list_filter = ("stage", "meeting_scheduled", "workspace")
    search_fields = ("company", "contact", "note")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("project_name", "company", "stage", "status", "total_value", "workspace", "due_date")
    list_filter = ("stage", "status", "workspace")
    search_fields = ("project_name", "company", "content_type")


@admin.register(WorkspaceSetting)
class WorkspaceSettingAdmin(admin.ModelAdmin):
    list_display = ("workspace", "key", "value", "updated_at")
    list_filter = ("workspace",)
    search_fields = ("workspace__name", "key", "value")
