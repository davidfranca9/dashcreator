from __future__ import annotations

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .constants import SETTINGS_GROUPS
from .models import Membership, Project, Prospect, Workspace
from .services import ensure_default_settings


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="Email")
    workspace_name = forms.CharField(label="Nome do studio", max_length=160)

    class Meta:
        model = User
        fields = ("username", "email", "workspace_name", "password1", "password2")
        labels = {
            "username": "Usuario",
            "password1": "Senha",
            "password2": "Confirme a senha",
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ja existe uma conta com este email.")
        return email

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            workspace = Workspace.objects.create(name=self.cleaned_data["workspace_name"])
            Membership.objects.create(user=user, workspace=workspace, role=Membership.ROLE_OWNER)
            ensure_default_settings(workspace)
        return user


class ProspectForm(forms.ModelForm):
    class Meta:
        model = Prospect
        fields = ["company", "contact", "stage", "proposal_value", "meeting_scheduled", "note"]
        labels = {
            "company": "Empresa",
            "contact": "Contato",
            "stage": "Etapa",
            "proposal_value": "Valor estimado",
            "meeting_scheduled": "Reuniao agendada",
            "note": "Observacoes",
        }
        widgets = {"note": forms.Textarea(attrs={"rows": 5})}


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "company",
            "project_name",
            "content_type",
            "stage",
            "status",
            "total_value",
            "entry_value",
            "received_value",
            "deliverables_count",
            "progress",
            "close_date",
            "due_date",
        ]
        labels = {
            "company": "Empresa",
            "project_name": "Projeto",
            "content_type": "Tipo de conteudo",
            "stage": "Etapa",
            "status": "Status",
            "total_value": "Valor total",
            "entry_value": "Entrada",
            "received_value": "Recebido",
            "deliverables_count": "Pecas",
            "progress": "Progresso (%)",
            "close_date": "Fechamento",
            "due_date": "Entrega",
        }
        widgets = {
            "close_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        total_value = cleaned_data.get("total_value") or 0
        entry_value = cleaned_data.get("entry_value") or 0
        received_value = cleaned_data.get("received_value") or 0
        progress = cleaned_data.get("progress") or 0

        if entry_value > total_value:
            self.add_error("entry_value", "A entrada nao pode ser maior que o valor total.")
        if received_value > total_value:
            self.add_error("received_value", "O valor recebido nao pode ser maior que o total.")
        if progress > 100:
            self.add_error("progress", "O progresso precisa ficar entre 0 e 100.")
        return cleaned_data


class WorkspaceSettingsForm(forms.Form):
    ui_lock_light_contrast = forms.BooleanField(required=False, label="Contraste claro travado no app")
    ui_soft_card_shadows = forms.BooleanField(required=False, label="Sombras suaves nos cards")
    ui_subtle_navigation_animation = forms.BooleanField(required=False, label="Animacao discreta na navegacao")
    ops_default_entry_rate = forms.ChoiceField(label="Entrada padrao sugerida", choices=[("50%", "50%"), ("40%", "40%"), ("30%", "30%")])
    ops_primary_currency = forms.ChoiceField(label="Moeda principal", choices=[("BRL (R$)", "BRL (R$)"), ("USD ($)", "USD ($)"), ("EUR (EUR)", "EUR (EUR)")])
    ops_follow_up_reminders = forms.BooleanField(required=False, label="Lembretes de follow-up")

    def __init__(self, *args, settings_values: dict[str, str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        settings_values = settings_values or {}
        for group in SETTINGS_GROUPS:
            for row in group["rows"]:
                field = self.fields[row["id"]]
                field.help_text = row["detail"]
                raw_value = settings_values.get(row["id"])
                if raw_value is None:
                    field.initial = row["value"]
                elif row["type"] == "check":
                    field.initial = str(raw_value).lower() in {"1", "true", "yes", "on"}
                else:
                    field.initial = raw_value
