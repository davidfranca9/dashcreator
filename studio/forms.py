from __future__ import annotations

import re

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm, UsernameField
from django.contrib.auth.models import User
from django.utils import timezone

from .contact_types import DEFAULT_CONTACT_TYPE_CHOICES, infer_contact_type, normalize_contact_type
from .constants import IMAGE_LICENSE_TERM_CHOICES, PROJECT_DISTRIBUTION_CHOICES, SETTINGS_GROUPS
from .models import AccessCode, FinanceEntry, Membership, Niche, Project, Prospect, ServiceCategory, Workspace, normalize_access_code
from .services import default_niche_queryset, ensure_default_niches, ensure_default_settings, settings_map


UserModel = get_user_model()
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
    ("Prospeccao", "Prospecção"),
    ("Follow-up", "Follow-up"),
    ("Plataforma", "Plataforma"),
    ("Agencia", "Agência"),
    ("Indicacao", "Indicação"),
    ("Nao se aplica", "Não se aplica"),
]
ADD_SERVICE_CATEGORY_VALUE = "__add_service_category__"
HAS_ENTRY_YES = "yes"
HAS_ENTRY_NO = "no"


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = UsernameField(label="Usuário ou email", widget=forms.TextInput(attrs={"autofocus": True}))

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Informe um usuário ou email e uma senha válidos.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "placeholder": "Usuário",
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
    full_name = forms.CharField(label="Nome completo", max_length=160)
    email = forms.EmailField(label="Email")
    workspace_name = forms.CharField(
        label="Nome profissional ou nome da marca",
        max_length=160,
        help_text=(
            "Use o nome pelo qual você quer aparecer na plataforma. Pode ser seu nome pessoal, "
            "nome da sua marca, nome da sua empresa ou seu @ do Instagram/TikTok."
        ),
        widget=forms.TextInput(attrs={"placeholder": "Ex: Ana Souza, Ana UGC Creator ou @anasouzaugc"}),
    )
    access_code = forms.CharField(
        label="Insira seu código",
        help_text="Use um código de acesso válido para definir se a conta será pagante ou não pagante.",
    )
    field_order = ["full_name", "username", "email", "workspace_name", "access_code", "password1", "password2"]

    class Meta:
        model = User
        fields = ("username", "email", "workspace_name", "password1", "password2")
        labels = {
            "username": "Usuário",
            "password1": "Senha",
            "password2": "Confirme a senha",
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este email.")
        return email

    def clean_full_name(self):
        return " ".join(self.cleaned_data["full_name"].split())

    def clean_access_code(self):
        code = normalize_access_code(self.cleaned_data["access_code"])
        access_code = AccessCode.objects.filter(code=code, is_active=True).select_related("assigned_user").first()
        if access_code is None:
            raise forms.ValidationError("Código de acesso inválido.")
        if access_code.assigned_user_id:
            raise forms.ValidationError("Este código já foi utilizado.")

        self.access_code_instance = access_code
        return code

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        full_name = self.cleaned_data["full_name"]
        name_parts = full_name.split(" ", 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ""
        if commit:
            user.save()
            workspace = Workspace.objects.create(
                name=self.cleaned_data["workspace_name"],
                business_full_name=full_name,
            )
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
                "contact_type",
                "contact",
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
        self.fields["contact_type"].required = True
        self.fields["contact"].required = False
        self.fields["contact_type"].choices = DEFAULT_CONTACT_TYPE_CHOICES
        self.fields["contact_type"].widget = forms.Select(choices=DEFAULT_CONTACT_TYPE_CHOICES)
        if not self.is_bound and getattr(self.instance, "pk", None):
            inferred_contact_type = infer_contact_type(
                self.instance.contact_type,
                email=self.instance.email,
                instagram=self.instance.instagram,
                whatsapp=self.instance.whatsapp,
            )
            if inferred_contact_type:
                self.initial["contact_type"] = inferred_contact_type
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
        if not getattr(self.instance, "pk", None) and not self.initial.get("stage"):
            self.fields["stage"].initial = "Rascunho"
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
            self.add_error("meeting_date", "Informe a data da reunião agendada.")

        if not cleaned_data.get("meeting_scheduled"):
            cleaned_data["meeting_date"] = None

        return cleaned_data

    def clean_contact_type(self):
        normalized_contact_type = normalize_contact_type(self.cleaned_data.get("contact_type", ""))
        if not normalized_contact_type:
            raise forms.ValidationError("Selecione um tipo de contato válido.")
        return normalized_contact_type

    def save(self, commit=True):
        prospect = super().save(commit=False)
        prospect.contact_type = self.cleaned_data.get("contact_type", "")
        if commit:
            prospect.save()
            self.save_m2m()
        return prospect

    class Meta:
        model = Prospect
        fields = [
            "company",
            "contact_type",
            "contact",
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
            "meeting_scheduled": "Reunião agendada",
            "meeting_date": "Data da reunião",
            "note": "Observações",
        }
        widgets = {"note": forms.Textarea(attrs={"rows": 5})}


class ProjectForm(forms.ModelForm):
    has_entry = forms.ChoiceField(
        label="Tem entrada?",
        choices=[(HAS_ENTRY_YES, "Sim"), (HAS_ENTRY_NO, "Não")],
        initial=HAS_ENTRY_YES,
        required=False,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, workspace: Workspace | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        settings_values = settings_map(workspace) if workspace is not None else {}
        default_entry_rate = settings_values.get("ops_default_entry_rate", "50%").replace("%", "").strip()
        self.default_entry_rate = int(default_entry_rate or 50)
        self.show_new_service_category = False
        self.fields["niche"].queryset = Niche.objects.none()
        self.fields["service_category"].queryset = ServiceCategory.objects.none()
        current_service_category = self.instance.service_category if getattr(self.instance, "pk", None) and self.instance.service_category_id else None
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
            if current_service_category is None:
                initial_service_category = self.initial.get("service_category")
                if isinstance(initial_service_category, ServiceCategory):
                    current_service_category = initial_service_category
                elif initial_service_category:
                    current_service_category = ServiceCategory.objects.filter(workspace=workspace, pk=initial_service_category).first()
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
        service_category_choices = [("", "---------")]
        if workspace is not None:
            service_category_choices.extend(
                (str(item.pk), item.name)
                for item in ServiceCategory.objects.filter(workspace=workspace).order_by("name")
            )
        service_category_choices.append((ADD_SERVICE_CATEGORY_VALUE, "Adicionar categoria"))
        self.fields["service_category"] = forms.ChoiceField(
            label="Categoria de serviço",
            choices=service_category_choices,
            required=False,
        )
        self.fields["service_category"].widget.attrs["data-new-option-value"] = ADD_SERVICE_CATEGORY_VALUE
        self.fields["service_category"].help_text = "Selecione uma categoria existente ou use a opção Adicionar categoria."
        if current_service_category is not None:
            self.initial["service_category"] = str(current_service_category.pk)
        self.fields["new_service_category"] = forms.CharField(
            label="Nova categoria",
            required=False,
            help_text="Digite o nome da nova categoria para salvar e reutilizar depois.",
            widget=forms.TextInput(attrs={"placeholder": "Ex.: Estratégia UGC"}),
        )
        if self.is_bound:
            self.show_new_service_category = self.data.get(self.add_prefix("service_category")) == ADD_SERVICE_CATEGORY_VALUE
        elif getattr(self.instance, "pk", None) and self.instance.total_value and self.instance.entry_value == self.instance.total_value:
            self.initial["has_entry"] = HAS_ENTRY_NO

        self.fields["has_entry"].help_text = "Marque Não quando o cliente pagar o valor total de uma vez."
        self.fields["entry_value"].help_text = (
            f"Preenchido automaticamente com {self.default_entry_rate}% do valor total. "
            "Você pode ajustar manualmente se quiser."
        )
        self.fields["stage"].help_text = "A etapa acompanha o status automaticamente."
        self.fields["payment_due_date"].help_text = "Use a data prevista para o recebimento desse trabalho."
        self.fields["meeting_date"].help_text = "Defina a data da reunião para gerar o atalho do Google Agenda."
        self.fields["note"].help_text = "Campo livre para anotações extras desse job."
        self.fields["content_distribution"] = forms.ChoiceField(
            label="Destino do conteúdo",
            choices=PROJECT_DISTRIBUTION_CHOICES,
            required=False,
        )
        self.fields["content_distribution"].help_text = "Marque se o material será usado de forma orgânica, em Ads ou se não se aplica."
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
        self.fields["deliverables_count"].help_text = "Use a quantidade total de vídeos incluídos neste trabalho."
        self.fields["total_value"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["entry_value"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["received_value"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["deliverables_count"].widget.attrs.update({"min": "1"})
        self.order_fields(
            [
                "company",
                "closing_source",
                "content_distribution",
                "image_license_term_days",
                "niche",
                "service_category",
                "new_service_category",
                "stage",
                "status",
                "total_value",
                "has_entry",
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

    def clean(self):
        cleaned_data = super().clean()
        service_category_value = cleaned_data.get("service_category")
        new_service_category = (cleaned_data.get("new_service_category") or "").strip()

        if service_category_value == ADD_SERVICE_CATEGORY_VALUE:
            cleaned_data["service_category"] = None
            if not new_service_category:
                self.add_error("new_service_category", "Digite o nome da nova categoria.")
            elif self.workspace is None:
                self.add_error("service_category", "Não foi possível carregar as categorias do workspace.")
            else:
                cleaned_data["service_category"], _ = ServiceCategory.objects.get_or_create(
                    workspace=self.workspace,
                    name=new_service_category,
                )
        elif service_category_value:
            cleaned_data["service_category"] = None
            service_category = None
            if self.workspace is not None:
                service_category = ServiceCategory.objects.filter(workspace=self.workspace, pk=service_category_value).first()
            if service_category is None:
                self.add_error("service_category", "Selecione uma categoria de serviço válida.")
            else:
                cleaned_data["service_category"] = service_category
        else:
            cleaned_data["service_category"] = None
            self.add_error("service_category", "Selecione uma categoria de serviço.")

        total_value = cleaned_data.get("total_value") or 0
        entry_value = cleaned_data.get("entry_value") or 0
        received_value = cleaned_data.get("received_value") or 0
        has_entry = cleaned_data.get("has_entry") or HAS_ENTRY_YES
        content_distribution = cleaned_data.get("content_distribution")
        image_license_term_days = cleaned_data.get("image_license_term_days")

        if has_entry == HAS_ENTRY_NO:
            entry_value = total_value
            cleaned_data["entry_value"] = total_value
        if entry_value > total_value:
            self.add_error("entry_value", "A entrada não pode ser maior que o valor total.")
        if received_value > total_value:
            self.add_error("received_value", "O valor recebido não pode ser maior que o total.")
        if content_distribution == "Ads" and not image_license_term_days:
            self.add_error("image_license_term_days", "Selecione o prazo do direito de uso de imagem para Ads.")
        if content_distribution != "Ads":
            cleaned_data["image_license_term_days"] = None
        if cleaned_data.get("meeting_scheduled") and not cleaned_data.get("meeting_date"):
            self.add_error("meeting_date", "Informe a data da reunião agendada.")
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
            "content_distribution": "Destino do conteúdo",
            "image_license_term_days": "Direito de uso de imagem",
            "niche": "Nicho",
            "service_category": "Categoria de serviço",
            "stage": "Etapa",
            "status": "Status",
            "total_value": "Valor total",
            "entry_value": "Entrada",
            "received_value": "Recebido",
            "deliverables_count": "Quantidade de vídeos",
            "payment_due_date": "Data prevista de pagamento",
            "meeting_scheduled": "Reunião agendada",
            "meeting_date": "Data da reunião",
            "close_date": "Fechamento",
            "due_date": "Data prevista para entrega",
            "note": "Observações",
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
            raise forms.ValidationError("Informe um CEP com 8 dígitos.")
        return f"{zip_code[:5]}-{zip_code[5:]}"

    class Meta:
        model = Workspace
        fields = [
            "business_full_name",
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
            "business_full_name": "Nome completo",
            "business_zip_code": "CEP",
            "business_street": "Rua",
            "business_number": "Número",
            "business_complement": "Complemento",
            "business_cnpj": "CNPJ",
            "business_pis": "Chave PIX",
            "instagram_url": "Instagram",
            "tiktok_url": "TikTok",
            "portfolio_url": "Portfólio",
        }
        widgets = {
            "business_full_name": forms.TextInput(attrs={"placeholder": "Nome completo"}),
            "business_zip_code": forms.TextInput(attrs={"inputmode": "numeric", "placeholder": "00000-000"}),
            "business_number": forms.TextInput(attrs={"placeholder": "Número"}),
            "business_complement": forms.TextInput(attrs={"placeholder": "Complemento"}),
            "business_pis": forms.TextInput(attrs={"placeholder": "Chave PIX"}),
        }


class ContractBrandForm(forms.Form):
    company_legal_name = forms.CharField(label="Razão social", max_length=180)
    company_cnpj = forms.CharField(label="CNPJ", max_length=18)
    company_address = forms.CharField(label="Endereço", max_length=255)
    company_phone = forms.CharField(label="Telefone", max_length=40)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company_legal_name"].widget.attrs.update({"placeholder": "Razão social da marca"})
        self.fields["company_cnpj"].widget.attrs.update({"placeholder": "00.000.000/0000-00"})
        self.fields["company_address"].widget.attrs.update({"placeholder": "Endereço completo da marca"})
        self.fields["company_phone"].widget.attrs.update({"placeholder": "(00) 00000-0000"})

    def clean_company_cnpj(self):
        digits = re.sub(r"\D", "", self.cleaned_data.get("company_cnpj", ""))
        if len(digits) != 14:
            raise forms.ValidationError("Informe um CNPJ válido com 14 dígitos.")
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


class WorkspaceSettingsForm(forms.Form):
    ui_dark_theme = forms.BooleanField(required=False, label="Tema escuro")
    ui_soft_card_shadows = forms.BooleanField(required=False, label="Sombras suaves nos cards")
    ui_subtle_navigation_animation = forms.BooleanField(required=False, label="Animação discreta na navegação")
    ops_default_entry_rate = forms.ChoiceField(label="Entrada padrão sugerida", choices=[("50%", "50%"), ("40%", "40%"), ("30%", "30%")])
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
            raise forms.ValidationError("A imagem precisa ter no máximo 2 MB.")
        return photo


class FinanceEntryForm(forms.ModelForm):
    class Meta:
        model = FinanceEntry
        fields = ["amount", "occurred_on", "description"]
        labels = {
            "amount": "Valor",
            "occurred_on": "Data",
            "description": "Descrição",
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
