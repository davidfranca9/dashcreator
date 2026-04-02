from __future__ import annotations

import re

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm, UsernameField
from django.contrib.auth.models import User
from django.utils import timezone

from .constants import IMAGE_LICENSE_TERM_CHOICES, PROJECT_DISTRIBUTION_CHOICES, SETTINGS_GROUPS
from .models import AccessCode, FinanceEntry, Membership, Niche, Project, Prospect, ServiceCategory, Workspace, normalize_access_code
from .services import default_niche_queryset, ensure_default_niches, ensure_default_settings, settings_map


UserModel = get_user_model()
DEFAULT_CLOSING_SOURCE_CHOICES = [
    ("Inbound", "Inbound"),
    ("Prospeccao", "Prospecção"),
    ("Plataforma", "Plataforma"),
    ("Agencia", "Agencia"),
    ("Indicacao", "Indicacao"),
    ("Nao se aplica", "NÃ£o se aplica"),
]
STATUS_PROGRESS_MAP = {
    "Briefing": 0,
    "Aguardando produto": 10,
    "Em gravacao": 25,
    "Em edicao": 55,
    "Aguardando cliente": 80,
    "Aprovado": 95,
    "Entregue": 100,
}
DEFAULT_CLOSING_SOURCE_CHOICES = [
    ("Inbound", "Inbound"),
    ("Prospeccao", "Prospec\u00e7\u00e3o"),
    ("Follow-up", "Follow-up"),
    ("Plataforma", "Plataforma"),
    ("Agencia", "Ag\u00eancia"),
    ("Indicacao", "Indica\u00e7\u00e3o"),
    ("Nao se aplica", "N\u00e3o se aplica"),
]


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = UsernameField(label="Usuario ou email", widget=forms.TextInput(attrs={"autofocus": True}))

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Informe um usuario ou email e uma senha validos.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "placeholder": "Usuario",
                "autocomplete": "username",
                "class": "login-input",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "placeholder": "Senha",
                "autocomplete": "current-password",
                "class": "login-input",
            }
        )

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
    def __init__(self, *args, workspace: Workspace | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        self.order_fields(
            [
                "company",
                "contact",
                "contact_type",
                "stage",
                "contact_date",
                "niche",
                "email",
                "instagram",
                "whatsapp",
                "meeting_scheduled",
                "meeting_date",
                "note",
            ]
        )
        self.fields["contact_date"].widget = forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        )
        self.fields["contact_date"].input_formats = ["%Y-%m-%d"]
        self.fields["meeting_date"].widget = forms.DateInput(
            attrs={"type": "date"},
            format="%Y-%m-%d",
        )
        self.fields["meeting_date"].input_formats = ["%Y-%m-%d"]
        self.fields["niche"].queryset = Niche.objects.none()
        if workspace is not None:
            ensure_default_niches(workspace)
            current_niche = self.instance.niche if getattr(self.instance, "pk", None) and self.instance.niche_id else None
            if current_niche is None:
                initial_niche = self.initial.get("niche")
                if isinstance(initial_niche, Niche):
                    current_niche = initial_niche
                elif initial_niche:
                    current_niche = Niche.objects.filter(workspace=workspace, pk=initial_niche).first()
            self.fields["niche"].queryset = default_niche_queryset(workspace, current_niche)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("meeting_scheduled") and not cleaned_data.get("meeting_date"):
            self.add_error("meeting_date", "Informe a data da reuniao agendada.")

        if not cleaned_data.get("meeting_scheduled"):
            cleaned_data["meeting_date"] = None

        return cleaned_data

    def save(self, commit=True):
        prospect = super().save(commit=False)
        if commit:
            prospect.save()
            self.save_m2m()
        return prospect

    class Meta:
        model = Prospect
        fields = [
            "company",
            "contact",
            "contact_type",
            "stage",
            "contact_date",
            "niche",
            "email",
            "instagram",
            "whatsapp",
            "meeting_scheduled",
            "meeting_date",
            "note",
        ]
        labels = {
            "company": "Empresa",
            "contact": "Contato",
            "contact_type": "Tipo de contato",
            "stage": "Etapa",
            "contact_date": "Data",
            "niche": "Nicho",
            "email": "Email",
            "instagram": "Instagram",
            "whatsapp": "WhatsApp",
            "meeting_scheduled": "Reuniao agendada",
            "meeting_date": "Data da reuniao",
            "note": "Observacoes",
        }
        widgets = {"note": forms.Textarea(attrs={"rows": 5})}


class ProjectForm(forms.ModelForm):
    def __init__(self, *args, workspace: Workspace | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        settings_values = settings_map(workspace) if workspace is not None else {}
        default_entry_rate = settings_values.get("ops_default_entry_rate", "50%").replace("%", "").strip()
        self.default_entry_rate = int(default_entry_rate or 50)
        self.order_fields(
            [
                "company",
                "closing_source",
                "content_distribution",
                "image_license_term_days",
                "niche",
                "service_category",
                "stage",
                "status",
                "total_value",
                "entry_value",
                "received_value",
                "deliverables_count",
                "payment_due_date",
                "meeting_scheduled",
                "meeting_date",
                "close_date",
                "due_date",
                "note",
            ]
        )
        self.fields["niche"].queryset = Niche.objects.none()
        self.fields["service_category"].queryset = ServiceCategory.objects.none()
        if workspace is not None:
            ensure_default_niches(workspace)
            current_niche = self.instance.niche if getattr(self.instance, "pk", None) and self.instance.niche_id else None
            if current_niche is None:
                initial_niche = self.initial.get("niche")
                if isinstance(initial_niche, Niche):
                    current_niche = initial_niche
                elif initial_niche:
                    current_niche = Niche.objects.filter(workspace=workspace, pk=initial_niche).first()
            self.fields["niche"].queryset = default_niche_queryset(workspace, current_niche)
            self.fields["service_category"].queryset = ServiceCategory.objects.filter(workspace=workspace)
        if not self.is_bound and not getattr(self.instance, "pk", None) and not self.initial.get("close_date"):
            self.fields["close_date"].initial = timezone.localdate()
        self.fields["close_date"].widget.format = "%Y-%m-%d"
        self.fields["close_date"].input_formats = ["%Y-%m-%d"]
        self.fields["due_date"].widget.format = "%Y-%m-%d"
        self.fields["due_date"].input_formats = ["%Y-%m-%d"]
        self.fields["payment_due_date"].widget.format = "%Y-%m-%d"
        self.fields["payment_due_date"].input_formats = ["%Y-%m-%d"]
        self.fields["meeting_date"].widget.format = "%Y-%m-%d"
        self.fields["meeting_date"].input_formats = ["%Y-%m-%d"]

        self.fields["entry_value"].help_text = (
            f"Preenchido automaticamente com {self.default_entry_rate}% do valor total. "
            "Voce pode ajustar manualmente se quiser."
        )
        self.fields["stage"].help_text = "A etapa acompanha o status automaticamente."
        self.fields["payment_due_date"].help_text = "Use a data prevista para o recebimento desse trabalho."
        self.fields["meeting_date"].help_text = "Defina a data da reuniao para gerar o atalho do Google Agenda."
        self.fields["note"].help_text = "Campo livre para anotacoes extras desse job."
        self.fields["content_distribution"] = forms.ChoiceField(
            label="Destino do conteudo",
            choices=PROJECT_DISTRIBUTION_CHOICES,
            required=False,
        )
        self.fields["content_distribution"].help_text = "Marque se o material sera usado de forma organica ou em Ads."
        self.fields["image_license_term_days"] = forms.TypedChoiceField(
            label="Direito de uso de imagem",
            choices=[("", "Selecione")] + list(IMAGE_LICENSE_TERM_CHOICES),
            coerce=int,
            empty_value=None,
            required=False,
        )
        self.fields["image_license_term_days"].help_text = "Selecione o prazo de licenciamento quando o destino for Ads."
        current_closing_source = (
            self.data.get(self.add_prefix("closing_source"))
            if self.is_bound
            else self.initial.get("closing_source") or getattr(self.instance, "closing_source", "")
        )
        closing_source_choices = [("", "Selecione")] + DEFAULT_CLOSING_SOURCE_CHOICES
        if current_closing_source and current_closing_source not in {value for value, _ in closing_source_choices}:
            closing_source_choices.append((current_closing_source, current_closing_source))
        self.fields["closing_source"] = forms.ChoiceField(
            label="Via de fechamento",
            choices=closing_source_choices,
            required=False,
        )
        self.fields["closing_source"].help_text = "Selecione por onde esse trabalho foi fechado."
        self.fields["deliverables_count"].help_text = "Use a quantidade total de videos incluidos neste trabalho."
        self.fields["total_value"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["entry_value"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["received_value"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["deliverables_count"].widget.attrs.update({"min": "1"})

    def clean(self):
        cleaned_data = super().clean()
        service_category = cleaned_data.get("service_category")

        if service_category is None:
            self.add_error("service_category", "Selecione uma categoria de servico nas configuracoes do workspace.")

        total_value = cleaned_data.get("total_value") or 0
        entry_value = cleaned_data.get("entry_value") or 0
        received_value = cleaned_data.get("received_value") or 0
        content_distribution = cleaned_data.get("content_distribution")
        image_license_term_days = cleaned_data.get("image_license_term_days")

        if entry_value > total_value:
            self.add_error("entry_value", "A entrada nao pode ser maior que o valor total.")
        if received_value > total_value:
            self.add_error("received_value", "O valor recebido nao pode ser maior que o total.")
        if content_distribution == "Ads" and not image_license_term_days:
            self.add_error("image_license_term_days", "Selecione o prazo do direito de uso de imagem para Ads.")
        if content_distribution != "Ads":
            cleaned_data["image_license_term_days"] = None
        if cleaned_data.get("meeting_scheduled") and not cleaned_data.get("meeting_date"):
            self.add_error("meeting_date", "Informe a data da reuniao agendada.")
        if not cleaned_data.get("meeting_scheduled"):
            cleaned_data["meeting_date"] = None
        return cleaned_data

    def save(self, commit=True):
        project = super().save(commit=False)
        project.project_name = project.service_category_name
        project.content_type = ""
        project.stage = "Entregue" if project.status == "Entregue" else "Fechado"
        project.progress = STATUS_PROGRESS_MAP.get(project.status, project.progress)
        if commit:
            project.save()
            self.save_m2m()
        return project

    class Meta:
        model = Project
        fields = [
            "company",
            "closing_source",
            "content_distribution",
            "image_license_term_days",
            "niche",
            "service_category",
            "stage",
            "status",
            "total_value",
            "entry_value",
            "received_value",
            "deliverables_count",
            "payment_due_date",
            "meeting_scheduled",
            "meeting_date",
            "close_date",
            "due_date",
            "note",
        ]
        labels = {
            "company": "Empresa",
            "closing_source": "Via de fechamento",
            "content_distribution": "Destino do conteudo",
            "image_license_term_days": "Direito de uso de imagem",
            "niche": "Nicho",
            "service_category": "Categoria de servico",
            "stage": "Etapa",
            "status": "Status",
            "total_value": "Valor total",
            "entry_value": "Entrada",
            "received_value": "Recebido",
            "deliverables_count": "Quantidade de videos",
            "payment_due_date": "Data prevista de pagamento",
            "meeting_scheduled": "Reuniao agendada",
            "meeting_date": "Data da reuniao",
            "close_date": "Fechamento",
            "due_date": "Entrega",
            "note": "Observacoes",
        }
        widgets = {
            "payment_due_date": forms.DateInput(attrs={"type": "date"}),
            "meeting_date": forms.DateInput(attrs={"type": "date"}),
            "close_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 5}),
        }


class WorkspaceBusinessForm(forms.ModelForm):
    def clean_business_zip_code(self):
        zip_code = re.sub(r"\D", "", self.cleaned_data.get("business_zip_code", ""))
        if not zip_code:
            return ""
        if len(zip_code) != 8:
            raise forms.ValidationError("Informe um CEP com 8 digitos.")
        return f"{zip_code[:5]}-{zip_code[5:]}"

    class Meta:
        model = Workspace
        fields = [
            "business_zip_code",
            "business_street",
            "business_number",
            "business_complement",
            "business_cnpj",
            "business_pis",
            "instagram_url",
            "tiktok_url",
            "portfolio_url",
        ]
        labels = {
            "business_zip_code": "CEP",
            "business_street": "Rua",
            "business_number": "Numero",
            "business_complement": "Complemento",
            "business_cnpj": "CNPJ",
            "business_pis": "Chave PIX",
            "instagram_url": "Instagram",
            "tiktok_url": "TikTok",
            "portfolio_url": "Portfolio",
        }
        widgets = {
            "business_zip_code": forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "00000-000"}),
            "business_number": forms.TextInput(attrs={"placeholder": "Numero"}),
            "business_complement": forms.TextInput(attrs={"placeholder": "Complemento"}),
            "business_pis": forms.TextInput(attrs={"placeholder": "Chave PIX"}),
        }


class WorkspaceSettingsForm(forms.Form):
    ui_dark_theme = forms.BooleanField(required=False, label="Tema escuro")
    ui_soft_card_shadows = forms.BooleanField(required=False, label="Sombras suaves nos cards")
    ui_subtle_navigation_animation = forms.BooleanField(required=False, label="Animacao discreta na navegacao")
    ops_default_entry_rate = forms.ChoiceField(label="Entrada padrao sugerida", choices=[("50%", "50%"), ("40%", "40%"), ("30%", "30%")])
    ops_primary_currency = forms.ChoiceField(label="Moeda principal", choices=[("BRL (R$)", "BRL (R$)"), ("USD ($)", "USD ($)"), ("EUR (EUR)", "EUR (EUR)")])
    ops_follow_up_reminders = forms.BooleanField(required=False, label="Lembretes de follow-up")
    legal_contract_signer_name = forms.CharField(required=False, label="Nome no contrato", max_length=160)

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


class ManagedOptionForm(forms.Form):
    name = forms.CharField(max_length=160, label="Nome")

    def __init__(self, *args, label: str, help_text: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = label
        self.fields["name"].help_text = help_text


class ProfilePhotoForm(forms.Form):
    photo = forms.FileField(label="Foto de perfil")

    allowed_types = {"image/png", "image/jpeg", "image/webp", "image/gif"}
    max_size = 2 * 1024 * 1024

    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        content_type = getattr(photo, "content_type", "")
        if content_type not in self.allowed_types:
            raise forms.ValidationError("Envie uma imagem em PNG, JPG, WEBP ou GIF.")
        if photo.size > self.max_size:
            raise forms.ValidationError("A imagem precisa ter no maximo 2 MB.")
        return photo


class FinanceEntryForm(forms.ModelForm):
    class Meta:
        model = FinanceEntry
        fields = ["amount", "occurred_on", "description"]
        labels = {
            "amount": "Valor",
            "occurred_on": "Data",
            "description": "Descricao",
        }
        widgets = {
            "occurred_on": forms.DateInput(attrs={"type": "date"}),
            "description": forms.TextInput(attrs={"placeholder": "Ex.: cliente pagou entrada / impulsionamento / editor"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["occurred_on"].input_formats = ["%Y-%m-%d"]
        self.fields["occurred_on"].widget.format = "%Y-%m-%d"
