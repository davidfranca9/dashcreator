from __future__ import annotations

from datetime import date, timedelta
import re

from django import forms
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm, UserCreationForm, UsernameField
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone

from .contact_types import DEFAULT_CONTACT_TYPE_CHOICES, infer_contact_type, normalize_contact_type
from .constants import (
    COMMISSION_PAYMENT_TYPES,
    IMAGE_LICENSE_TERM_CHOICES,
    POST_PRODUCTION_PAYMENT_TYPES,
    PROJECT_DISTRIBUTION_CHOICES,
    SERVICE_TYPE_CATEGORIES,
    SERVICE_TYPE_CHOICES,
    SERVICE_TYPE_TO_CATEGORY,
    SETTINGS_GROUPS,
)
from .models import AccessCode, CashBox, FinanceEntry, FixedCost, Membership, Niche, Project, ProjectInstallment, Prospect, ServiceCategory, Workspace, normalize_access_code
from .services import default_niche_queryset, ensure_default_niches, ensure_default_settings, settings_map


UserModel = get_user_model()
STATUS_PROGRESS_MAP = {
    "Briefing": 0,
    "Em produção": 40,
    "Aguardando aprovação": 80,
    "Concluído": 100,
    "Cancelado": 0,
}
DEFAULT_CLOSING_SOURCE_CHOICES = [
    ("Inbound", "Inbound"),
    ("Prospeccao", "Prospecção"),
    ("Follow-up", "Follow-up"),
    ("Plataforma", "Plataforma"),
    ("Agencia", "Agência"),
    ("Indicacao", "Indicação"),
    ("Networking", "Networking"),
    ("Nao se aplica", "Não se aplica"),
]
ADD_SERVICE_CATEGORY_VALUE = "__add_service_category__"
HAS_ENTRY_YES = "yes"
HAS_ENTRY_NO = "no"
HAS_INSTALLMENTS_YES = "yes"
HAS_INSTALLMENTS_NO = "no"
PAYMENT_RECURRENCE_SINGLE = "single"
PAYMENT_RECURRENCE_MONTHLY = "monthly"
SOCIAL_MEDIA_SERVICE_TYPE = "social_media"
MARKETING_CONSULTING_SERVICE_TYPE = "consultoria_marketing"
UGC_CREATOR_SERVICE_TYPE = "ugc_creator"
FREELANCER_SERVICE_TYPE = "freelancer"
VIDEO_EDITOR_SERVICE_TYPE = "editora_video"
VIDEOMAKER_SERVICE_TYPE = "videomaker"
STORYMAKER_SERVICE_TYPE = "storymaker"
UGC_MANAGER_SERVICE_TYPE = "ugc_manager"
PUBLICIDADE_SERVICE_TYPE = "publicidade"
RECURRING_CONTRACT_TYPES = [SOCIAL_MEDIA_SERVICE_TYPE, MARKETING_CONSULTING_SERVICE_TYPE]
RECURRING_CONTRACT_HIDDEN_FIELDS = [
    "stage",
    "status",
    "has_entry",
    "entry_value",
    "received_value",
    "monthly_value",
]
SOCIAL_MEDIA_HIDDEN_FIELDS = [
    "deliverables_count",
]
# UGC/Freelancer/Editora/Captação/Publicidade: o campo "Recebido" é
# calculado automaticamente (mirror da entrada ou via parcelas pagas),
# e a etapa é derivada do status no save(). Por isso esses campos
# ficam ocultos no formulário.
ENTRY_RECEIPT_SERVICE_TYPES = [
    UGC_CREATOR_SERVICE_TYPE,
    FREELANCER_SERVICE_TYPE,
    VIDEO_EDITOR_SERVICE_TYPE,
    VIDEOMAKER_SERVICE_TYPE,
    STORYMAKER_SERVICE_TYPE,
    UGC_MANAGER_SERVICE_TYPE,
    PUBLICIDADE_SERVICE_TYPE,
]
# Tipos com contratos plurimensais auto-faturados: ao definir uma
# duração > 1 mês, o sistema gera as parcelas mensais automaticamente
# a partir do dia escolhido em payment_due_date. Para os contratos
# recorrentes (Social Media, Consultoria), o valor de cada parcela é
# o "Valor mensal do contrato"; para Publicidade é o total dividido
# pela duração.
AUTO_MONTHLY_INSTALLMENT_TYPES = [
    PUBLICIDADE_SERVICE_TYPE,
    SOCIAL_MEDIA_SERVICE_TYPE,
    MARKETING_CONSULTING_SERVICE_TYPE,
]
ENTRY_RECEIPT_HIDDEN_FIELDS = [
    "stage",
    "received_value",
]


def _contract_due_date_from_start(start_date: date | None, duration_months: int | None) -> date | None:
    if start_date is None:
        return None
    duration = max(1, int(duration_months or 1))
    month_index = (start_date.year * 12) + (start_date.month - 1) + duration
    year = month_index // 12
    month = (month_index % 12) + 1
    return date(year, month, 1) - timedelta(days=1)

# Mapeia cada campo type-specific aos service_type que devem exibi-lo no
# form. Lido pelo template para gerar atributos data-show-for-type, e pelo
# JS para mostrar/esconder conforme o tipo de serviço selecionado.
# Nota: videos_count NÃO entra aqui porque deliverables_count já cobre o
# papel de "Quantidade de vídeos" pros tipos UGC/Freelancer/Editora/etc.
FIELD_VISIBILITY_BY_SERVICE_TYPE = {
    "stories_count": ["storymaker"],
    "story_coverage_date": ["storymaker", "videomaker"],
    "posts_per_month": ["social_media"],
    "videos_per_month": ["social_media"],
    "profile_managed": ["social_media"],
    "payment_recurrence": ["publicidade"],
    "contract_duration_months": ["social_media", "consultoria_marketing", "publicidade"],
    "monthly_value": ["ugc_manager"],
    "managed_creators_count": ["ugc_manager"],
    "publication_date": ["publicidade"],
    "affiliate_program": ["afiliacao"],
    "sold_amount": ["afiliacao"],
    "commission_percentage": ["afiliacao"],
    "extra_value": ["afiliacao"],
    "withdrawal_date": ["afiliacao"],
    "briefing": ["consultoria_marketing", "freelancer"],
    # Campos universais com regra de exibição condicional ao tipo:
    "deliverables_count": [
        "ugc_creator", "freelancer", "editora_video", "videomaker",
        "shop_creator", "ugc_manager", "publicidade",
    ],
    "content_distribution": ["ugc_creator"],
    "image_license_term_days": ["ugc_creator"],
}

# Tipos cujo bloco de pagamento é "valor único pós-produção": esconde
# has_entry / entry_value e mantém apenas total_value + payment_due_date.
SIMPLIFIED_PAYMENT_TYPES = POST_PRODUCTION_PAYMENT_TYPES | COMMISSION_PAYMENT_TYPES

# Tipos sem reunião nem data de entrega (brief: Afiliação).
NO_DELIVERY_TYPES = COMMISSION_PAYMENT_TYPES

# Tipos cujo bloco "Parcelas de pagamento" faz sentido: contratos longos /
# recorrentes onde o cliente paga em parcelas previsiveis. UGC e similares
# (job unico com entrada + saldo) usam apenas has_entry / entry_value /
# payment_due_date e nao mostram a lista de parcelas.
INSTALLMENTS_TYPES = RECURRING_CONTRACT_TYPES

CONTRACT_DURATION_CHOICES = [
    (1, "1 mês"),
    (3, "3 meses"),
    (6, "6 meses"),
    (12, "12 meses"),
]


class ProjectInstallmentForm(forms.ModelForm):
    class Meta:
        model = ProjectInstallment
        fields = ["due_date", "amount", "paid"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "amount": forms.NumberInput(attrs={"step": "0.01", "min": "0", "inputmode": "decimal"}),
        }
        labels = {
            "due_date": "Data da parcela",
            "amount": "Valor",
            "paid": "Pago",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # type="date" inputs só aceitam yyyy-mm-dd; sem isso o Django
        # renderiza dd/mm/yyyy do locale e o browser mostra vazio.
        self.fields["due_date"].input_formats = ["%Y-%m-%d"]


ProjectInstallmentFormSet = forms.inlineformset_factory(
    Project,
    ProjectInstallment,
    form=ProjectInstallmentForm,
    extra=0,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


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
    has_installments = forms.ChoiceField(
        label="Tem parcela?",
        choices=[(HAS_INSTALLMENTS_YES, "Sim"), (HAS_INSTALLMENTS_NO, "Não")],
        initial=HAS_INSTALLMENTS_NO,
        required=False,
        widget=forms.RadioSelect,
    )
    payment_recurrence = forms.ChoiceField(
        label="Recorrência de pagamento",
        choices=[
            (PAYMENT_RECURRENCE_SINGLE, "Pagamento único"),
            (PAYMENT_RECURRENCE_MONTHLY, "Mensal recorrente"),
        ],
        initial=PAYMENT_RECURRENCE_SINGLE,
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
        elif getattr(self.instance, "pk", None):
            if self.instance.total_value and self.instance.entry_value == self.instance.total_value:
                self.initial["has_entry"] = HAS_ENTRY_NO
            if self.instance.installments.exists():
                self.initial["has_installments"] = HAS_INSTALLMENTS_YES
            if self.instance.service_type == PUBLICIDADE_SERVICE_TYPE and int(self.instance.contract_duration_months or 0) > 1:
                self.initial["payment_recurrence"] = PAYMENT_RECURRENCE_MONTHLY

        self.fields["has_entry"].help_text = "Marque Não quando o cliente pagar o valor total de uma vez."
        self.fields["has_installments"].help_text = "Marque Sim para cadastrar as parcelas com data e valor."
        self.fields["payment_recurrence"].help_text = "Use mensal recorrente quando o pagamento de publicidade se repetir por mais de um mês."
        self.fields["entry_value"].help_text = (
            f"Preenchido automaticamente com {self.default_entry_rate}% do valor total. "
            "Você pode ajustar manualmente se quiser."
        )
        self.fields["stage"].help_text = "A etapa acompanha o status automaticamente."
        self.fields["payment_due_date"].help_text = "Use quando não houver parcelas cadastradas."
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

        # Service type - aparece no topo do form e dirige a visibilidade
        # dos blocos type-specific via JS no template.
        self.fields["service_type"] = forms.ChoiceField(
            label="Tipo de serviço",
            choices=SERVICE_TYPE_CHOICES,
            required=False,
            help_text="Define quais campos extras aparecem no formulário.",
        )
        self.fields["service_type"].widget.attrs["data-service-type"] = "true"
        if not self.is_bound and not self.initial.get("service_type") and not getattr(self.instance, "service_type", ""):
            self.initial["service_type"] = "outros"

        # Money fields type-specific já têm default=0 no model; tornar
        # not required no form pra não exigir preenchimento explícito.
        for optional_money in ("monthly_value", "sold_amount", "commission_percentage", "extra_value"):
            self.fields[optional_money].required = False

        # Alguns campos são escondidos pela UI para contratos recorrentes, mas o form
        # ainda precisa aceitar o POST sem exigir valores invisíveis.
        for hidden_for_contract in ("due_date", "entry_value", "received_value", "deliverables_count"):
            self.fields[hidden_for_contract].required = False

        # Configurações dos campos type-specific.
        self.fields["contract_duration_months"] = forms.TypedChoiceField(
            label="Duração do contrato",
            choices=[("", "Selecione")] + CONTRACT_DURATION_CHOICES,
            coerce=int,
            empty_value=None,
            required=False,
        )
        for money_field in ("monthly_value", "sold_amount", "extra_value"):
            self.fields[money_field].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["commission_percentage"].widget.attrs.update({"step": "0.01", "min": "0", "max": "100", "inputmode": "decimal"})
        for count_field in ("stories_count", "posts_per_month", "videos_per_month", "managed_creators_count"):
            self.fields[count_field].widget.attrs.update({"min": "0"})

        self.fields["monthly_value"].help_text = "Valor que entra no caixa pelo gerenciamento."
        self.fields["managed_creators_count"].help_text = "Quantidade de creators envolvidos no gerenciamento."
        self.fields["briefing"].help_text = "Descreva o serviço para freelancer ou o briefing da consultoria."
        self.fields["affiliate_program"].help_text = "Nome do programa de afiliação ou marca."
        self.fields["story_coverage_date"].help_text = "Dia marcado para a captação."
        self.fields["publication_date"].help_text = "Data prevista para a publicação."
        self.fields["withdrawal_date"].help_text = "Data prevista para o saque da comissão."

        # Mapa exposto ao template para gerar data-show-for-type por campo.
        self.field_visibility_by_type = FIELD_VISIBILITY_BY_SERVICE_TYPE
        self.service_type_categories = SERVICE_TYPE_CATEGORIES
        self.service_type_to_category = SERVICE_TYPE_TO_CATEGORY
        self.simplified_payment_types = list(SIMPLIFIED_PAYMENT_TYPES)
        self.commission_payment_types = list(COMMISSION_PAYMENT_TYPES)
        self.no_delivery_types = list(NO_DELIVERY_TYPES)
        self.installments_types = list(INSTALLMENTS_TYPES)
        self.recurring_contract_types = list(RECURRING_CONTRACT_TYPES)
        self.recurring_contract_hidden_fields = RECURRING_CONTRACT_HIDDEN_FIELDS
        self.social_media_hidden_fields = SOCIAL_MEDIA_HIDDEN_FIELDS
        self.entry_receipt_service_types = list(ENTRY_RECEIPT_SERVICE_TYPES)
        self.entry_receipt_hidden_fields = ENTRY_RECEIPT_HIDDEN_FIELDS
        self.auto_monthly_installment_types = list(AUTO_MONTHLY_INSTALLMENT_TYPES)
        self.order_fields(
            [
                # --- Identidade do trabalho ---
                "company",
                "service_type",
                "service_category",
                "new_service_category",
                # --- Bloco de contrato (em cima) ---
                "niche",
                "closing_source",
                "stage",
                "status",
                "close_date",
                "due_date",
                "contract_duration_months",
                "meeting_scheduled",
                "meeting_date",
                # Campos type-specific (parte de contrato/entregáveis)
                "deliverables_count",
                "stories_count",
                "story_coverage_date",
                "posts_per_month",
                "videos_per_month",
                "profile_managed",
                "managed_creators_count",
                "publication_date",
                "content_distribution",
                "image_license_term_days",
                "affiliate_program",
                "sold_amount",
                "commission_percentage",
                "extra_value",
                "withdrawal_date",
                "briefing",
                # --- Bloco de pagamento (embaixo) ---
                "total_value",
                "monthly_value",
                "has_entry",
                "entry_value",
                "received_value",
                "has_installments",
                "payment_recurrence",
                "payment_due_date",
                # --- Observações no final ---
                "note",
            ]
        )

    def clean_service_type(self):
        return self.cleaned_data.get("service_type") or "outros"

    def clean(self):
        cleaned_data = super().clean()
        # Money type-specific fields que vieram vazios contam como zero
        # (model usa default=0).
        for optional_money in ("monthly_value", "sold_amount", "commission_percentage", "extra_value"):
            if cleaned_data.get(optional_money) in (None, ""):
                cleaned_data[optional_money] = 0
        service_category_value = cleaned_data.get("service_category")
        new_service_category = (cleaned_data.get("new_service_category") or "").strip()

        service_type_value = cleaned_data.get("service_type") or "outros"
        service_type_label = dict(SERVICE_TYPE_CHOICES).get(service_type_value, "")

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
            # Service category nao informada: auto-cria (ou reusa) uma com o
            # mesmo nome do service_type. Mantem a coluna preenchida pra
            # service_category_name() e relatorios legados.
            cleaned_data["service_category"] = None
            if self.workspace is not None and service_type_label:
                cleaned_data["service_category"], _ = ServiceCategory.objects.get_or_create(
                    workspace=self.workspace,
                    name=service_type_label,
                )

        total_value = cleaned_data.get("total_value") or 0
        entry_value = cleaned_data.get("entry_value") or 0
        received_value = cleaned_data.get("received_value") or 0
        has_entry = cleaned_data.get("has_entry") or HAS_ENTRY_YES
        has_installments = cleaned_data.get("has_installments") or HAS_INSTALLMENTS_NO
        payment_recurrence = cleaned_data.get("payment_recurrence") or PAYMENT_RECURRENCE_SINGLE
        payment_recurrence_was_posted = self.is_bound and self.add_prefix("payment_recurrence") in self.data
        content_distribution = cleaned_data.get("content_distribution")
        image_license_term_days = cleaned_data.get("image_license_term_days")
        is_social_media = service_type_value == SOCIAL_MEDIA_SERVICE_TYPE
        is_ugc_manager = service_type_value == UGC_MANAGER_SERVICE_TYPE
        is_recurring_contract = service_type_value in RECURRING_CONTRACT_TYPES
        is_existing_recurring_contract = (
            bool(getattr(self.instance, "pk", None))
            and getattr(self.instance, "service_type", "") in RECURRING_CONTRACT_TYPES
        )

        if is_recurring_contract:
            contract_end_date = cleaned_data.get("due_date") or _contract_due_date_from_start(
                cleaned_data.get("close_date"),
                cleaned_data.get("contract_duration_months"),
            )
            if contract_end_date:
                cleaned_data["due_date"] = contract_end_date
            else:
                self.add_error("due_date", "Informe a data de finalização do contrato.")

            if is_existing_recurring_contract:
                entry_value = self.instance.entry_value or 0
                received_value = self.instance.received_value or 0
                deliverables_count = self.instance.deliverables_count or 1
            else:
                entry_value = 0
                received_value = 0
                deliverables_count = 1
            cleaned_data["entry_value"] = entry_value
            cleaned_data["received_value"] = received_value
            cleaned_data["monthly_value"] = 0
            if is_social_media:
                cleaned_data["deliverables_count"] = deliverables_count
            # Parcelas mensais agora são geradas automaticamente; o
            # payment_due_date define o dia fixo de cobrança em todos os
            # meses do contrato.
            if not cleaned_data.get("payment_due_date"):
                self.add_error("payment_due_date", "Informe a data prevista de pagamento.")
        elif service_type_value in NO_DELIVERY_TYPES and not cleaned_data.get("due_date"):
            cleaned_data["due_date"] = cleaned_data.get("close_date")
        else:
            if not cleaned_data.get("due_date"):
                self.add_error("due_date", "Informe a data prevista para entrega.")
            if (
                service_type_value in FIELD_VISIBILITY_BY_SERVICE_TYPE["deliverables_count"]
                and not cleaned_data.get("deliverables_count")
            ):
                self.add_error("deliverables_count", "Informe a quantidade de vídeos.")
            if service_type_value == PUBLICIDADE_SERVICE_TYPE:
                duration_months = cleaned_data.get("contract_duration_months")
                if not payment_recurrence_was_posted and payment_recurrence == PAYMENT_RECURRENCE_SINGLE and duration_months and duration_months > 1:
                    payment_recurrence = PAYMENT_RECURRENCE_MONTHLY
                if payment_recurrence == PAYMENT_RECURRENCE_MONTHLY:
                    if not duration_months or duration_months <= 1:
                        self.add_error("contract_duration_months", "Informe a duração da recorrência de pagamento.")
                    elif not cleaned_data.get("payment_due_date"):
                        cleaned_data["payment_due_date"] = cleaned_data.get("close_date")
                else:
                    cleaned_data["contract_duration_months"] = None

        management_value = cleaned_data.get("monthly_value") or 0
        if is_ugc_manager:
            if management_value <= 0:
                self.add_error("monthly_value", "Informe o valor do gerenciamento.")
            if management_value > total_value:
                self.add_error("monthly_value", "O valor do gerenciamento não pode ser maior que o valor total do contrato.")
            if not cleaned_data.get("managed_creators_count"):
                self.add_error("managed_creators_count", "Informe a quantidade de creators.")

        if not is_recurring_contract and has_entry == HAS_ENTRY_NO:
            no_entry_value = management_value if is_ugc_manager and management_value > 0 else total_value
            entry_value = no_entry_value
            cleaned_data["entry_value"] = no_entry_value
        if service_type_value in SIMPLIFIED_PAYMENT_TYPES:
            # Pagamento único pós-produção (Publicidade, Shop Creator,
            # Afiliação): não há entrada — ignora o que o navegador mandou
            # mesmo que o JS tenha calculado um valor padrão.
            entry_value = 0
            cleaned_data["entry_value"] = 0
        if service_type_value in ENTRY_RECEIPT_SERVICE_TYPES:
            received_value = entry_value
            cleaned_data["received_value"] = entry_value
        if entry_value > total_value:
            self.add_error("entry_value", "A entrada não pode ser maior que o valor total.")
        if is_ugc_manager and management_value > 0 and entry_value > management_value:
            self.add_error("entry_value", "A entrada não pode ser maior que o valor do gerenciamento.")
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
        project.stage = "Entregue" if project.status == "Concluído" else "Fechado"
        project.progress = STATUS_PROGRESS_MAP.get(project.status, project.progress)
        if commit:
            project.save()
            self.save_m2m()
        return project

    class Meta:
        model = Project
        fields = [
            "company",
            "service_type",
            "service_category",
            "closing_source",
            "content_distribution",
            "image_license_term_days",
            "niche",
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
            "stories_count",
            "story_coverage_date",
            "posts_per_month",
            "videos_per_month",
            "profile_managed",
            "contract_duration_months",
            "monthly_value",
            "managed_creators_count",
            "publication_date",
            "affiliate_program",
            "sold_amount",
            "commission_percentage",
            "extra_value",
            "withdrawal_date",
            "briefing",
            "note",
        ]
        labels = {
            "company": "Cliente / Marca",
            "service_type": "Tipo de serviço",
            "closing_source": "Via de fechamento",
            "content_distribution": "Destino do conteúdo",
            "image_license_term_days": "Direito de uso de imagem",
            "niche": "Nicho",
            "service_category": "Categoria de serviço",
            "stage": "Etapa",
            "status": "Status",
            "total_value": "Valor de contrato",
            "entry_value": "Entrada",
            "received_value": "Recebido",
            "deliverables_count": "Quantidade de vídeos",
            "payment_due_date": "Data prevista de pagamento",
            "meeting_scheduled": "Reunião agendada",
            "meeting_date": "Data da reunião",
            "close_date": "Data de fechamento",
            "due_date": "Data prevista para entrega",
            "stories_count": "Quantidade de stories",
            "story_coverage_date": "Data de captação",
            "posts_per_month": "Posts por mês",
            "videos_per_month": "Vídeos por mês",
            "profile_managed": "Perfil gerenciado",
            "contract_duration_months": "Duração do contrato",
            "monthly_value": "Valor do gerenciamento",
            "managed_creators_count": "Quantidade de creators",
            "publication_date": "Data de publicação",
            "affiliate_program": "Programa de afiliação",
            "sold_amount": "Valor total vendido",
            "commission_percentage": "% de comissão",
            "extra_value": "Valor extra fixo",
            "withdrawal_date": "Data de saque",
            "briefing": "Briefing do contrato",
            "note": "Observações",
        }
        widgets = {
            "payment_due_date": forms.DateInput(attrs={"type": "date"}),
            "meeting_date": forms.DateInput(attrs={"type": "date"}),
            "close_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "story_coverage_date": forms.DateInput(attrs={"type": "date"}),
            "publication_date": forms.DateInput(attrs={"type": "date"}),
            "withdrawal_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 5}),
            "briefing": forms.Textarea(attrs={"rows": 4}),
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
    ops_pro_labore_amount = forms.DecimalField(
        label="Pró-labore mensal",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0", "inputmode": "decimal"}),
    )
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


class FixedCostForm(forms.ModelForm):
    class Meta:
        model = FixedCost
        fields = ["kind", "recurrence", "name", "amount", "due_day", "due_month"]
        labels = {
            "kind": "Tipo",
            "recurrence": "Tipo de custo",
            "name": "Nome",
            "amount": "Valor",
            "due_day": "Dia do vencimento",
            "due_month": "Mês do vencimento",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Notion Pro, Editor fixo"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs.update({"step": "0.01", "min": "0", "inputmode": "decimal"})
        self.fields["due_day"].widget.attrs.update({"min": "1", "max": "31", "inputmode": "numeric"})
        self.fields["amount"].help_text = "Para custos anuais, informe o valor total do ano — o sistema converte para o equivalente mensal no total reservado."
        self.fields["due_month"].help_text = "Usado apenas para custos anuais."

    def clean_due_day(self):
        value = self.cleaned_data.get("due_day")
        if value is None:
            return value
        if value < 1 or value > 31:
            raise forms.ValidationError("Informe um dia entre 1 e 31.")
        return value


class CashBoxForm(forms.ModelForm):
    class Meta:
        model = CashBox
        fields = ["name", "allocation_percentage", "description"]
        labels = {
            "name": "Nome da caixinha",
            "allocation_percentage": "% do fluxo livre",
            "description": "Descrição",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Ex.: Impostos, viagem, equipamento"}),
            "description": forms.TextInput(attrs={"placeholder": "Ex.: Separar para troca de câmera"}),
        }

    def __init__(self, *args, workspace: Workspace | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        self.fields["allocation_percentage"].widget.attrs.update({"step": "0.01", "min": "0.01", "max": "100", "inputmode": "decimal"})
        self.fields["allocation_percentage"].help_text = "Percentual calculado sobre o valor que sobra depois de pró-labore, custo fixo, reserva e investimento."

    def clean_allocation_percentage(self):
        value = self.cleaned_data.get("allocation_percentage")
        if value is None or value <= 0:
            raise forms.ValidationError("Informe um percentual maior que zero.")
        if value > 100:
            raise forms.ValidationError("O percentual não pode passar de 100%.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        percentage = cleaned_data.get("allocation_percentage")
        if self.workspace is None or percentage is None:
            return cleaned_data
        existing_total = CashBox.objects.filter(workspace=self.workspace).exclude(pk=getattr(self.instance, "pk", None)).aggregate(
            total=Sum("allocation_percentage")
        )["total"] or 0
        if existing_total + percentage > 100:
            self.add_error("allocation_percentage", "A soma das caixinhas extras não pode passar de 100% do fluxo livre.")
        return cleaned_data
