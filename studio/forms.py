from __future__ import annotations

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm, UsernameField
from django.contrib.auth.models import User
from django.utils import timezone

from .constants import SETTINGS_GROUPS
from .models import AccessCode, Membership, Project, Prospect, Workspace, normalize_access_code
from .services import ensure_default_settings


UserModel = get_user_model()


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = UsernameField(label="Usuario ou email", widget=forms.TextInput(attrs={"autofocus": True}))

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Informe um usuario ou email e uma senha validos.",
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            login_value = username.strip()
            matched_user = UserModel._default_manager.filter(email__iexact=login_value).first()
            if matched_user is None:
                matched_user = UserModel._default_manager.filter(username__iexact=login_value).first()

            normalized_username = matched_user.get_username() if matched_user else login_value
            self.user_cache = authenticate(self.request, username=normalized_username, password=password)

            if self.user_cache is None:
                raise self.get_invalid_login_error()

            self.confirm_login_allowed(self.user_cache)
            self.cleaned_data["username"] = normalized_username

        return self.cleaned_data


class AppPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(label="Email da conta")

    def get_users(self, email):
        active_users = UserModel._default_manager.filter(email__iexact=email, is_active=True)
        for user in active_users:
            if user.has_usable_password():
                yield user


class AppSetPasswordForm(SetPasswordForm):
    new_password1 = forms.CharField(
        label="Nova senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label="Confirme a nova senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="Email")
    workspace_name = forms.CharField(label="Nome do studio", max_length=160)
    access_code = forms.CharField(
        label="Insira seu codigo",
        help_text="Use um codigo de acesso valido para definir se a conta sera pagante ou nao pagante.",
    )
    field_order = ["username", "email", "workspace_name", "access_code", "password1", "password2"]

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

    def clean_access_code(self):
        code = normalize_access_code(self.cleaned_data["access_code"])
        access_code = AccessCode.objects.filter(code=code, is_active=True).select_related("assigned_user").first()
        if access_code is None:
            raise forms.ValidationError("Codigo de acesso invalido.")
        if access_code.assigned_user_id:
            raise forms.ValidationError("Este codigo ja foi utilizado.")

        self.access_code_instance = access_code
        return code

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            workspace = Workspace.objects.create(name=self.cleaned_data["workspace_name"])
            Membership.objects.create(user=user, workspace=workspace, role=Membership.ROLE_OWNER)
            ensure_default_settings(workspace)
            access_code = self.access_code_instance
            access_code.assigned_user = user
            access_code.assigned_at = timezone.now()
            access_code.save(update_fields=["assigned_user", "assigned_at", "updated_at"])
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
