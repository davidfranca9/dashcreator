from __future__ import annotations

import calendar
import json
import mimetypes
import re
from datetime import date
from decimal import Decimal
from html import escape, unescape
from pathlib import Path
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetCompleteView, PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils._os import safe_join
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .emails import send_signup_confirmation_email

from .forms import (
    AUTO_MONTHLY_INSTALLMENT_TYPES,
    AppPasswordResetForm,
    CashBoxAllocationForm,
    AppSetPasswordForm,
    CashBoxForm,
    ContractBrandForm,
    EmailOrUsernameAuthenticationForm,
    FinanceEntryForm,
    FixedCostForm,
    HAS_INSTALLMENTS_YES,
    ManagedOptionForm,
    ProjectForm,
    ProjectInstallmentFormSet,
    ProspectForm,
    SignUpForm,
    WorkspaceBusinessForm,
    WorkspaceSettingsForm,
)
from .constants import CASH_BOX_ALLOCATION_SETTINGS
from .models import CashBox, FinanceEntry, FixedCost, Project, ProjectInstallment, Prospect, ServiceCategory
from .services import (
    confirm_follow_up_companies,
    dashboard_snapshot,
    distribution_snapshot,
    dismiss_follow_up_company,
    finance_snapshot,
    get_or_create_workspace_for_user,
    jobs_snapshot_filtered,
    legal_snapshot,
    parse_month_value,
    prospection_snapshot,
    reports_snapshot,
    save_settings,
    settings_map,
    shell_context,
    start_follow_up_prospection,
    workspace_business_address_summary,
)


class AppLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailOrUsernameAuthenticationForm
    redirect_authenticated_user = True


class AppPasswordResetView(PasswordResetView):
    template_name = "registration/hubla_password_reset_form.html"
    email_template_name = "registration/hubla_password_reset_email.txt"
    subject_template_name = "registration/hubla_password_reset_subject.txt"
    form_class = AppPasswordResetForm
    success_url = reverse_lazy("password_reset_done")


class AppPasswordResetDoneView(PasswordResetDoneView):
    template_name = "registration/hubla_password_reset_done.html"


class AppPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "registration/hubla_password_reset_confirm.html"
    form_class = AppSetPasswordForm
    success_url = reverse_lazy("password_reset_complete")


class AppPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "registration/hubla_password_reset_complete.html"


def home(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def serve_media_file(request: HttpRequest, path: str) -> FileResponse:
    media_root = Path(django_settings.MEDIA_ROOT)

    try:
        absolute_path = Path(safe_join(str(media_root), path))
    except ValueError as exc:
        raise Http404("Arquivo inválido.") from exc

    if not absolute_path.is_file():
        raise Http404("Arquivo não encontrado.")

    content_type, _ = mimetypes.guess_type(absolute_path.name)
    response = FileResponse(absolute_path.open("rb"), content_type=content_type or "application/octet-stream")
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _first_non_empty(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _format_cnpj(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 14:
        return (value or "").strip()
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _compose_company_address(data: dict) -> str:
    street = _first_non_empty(
        data.get("street"),
        data.get("logradouro"),
        data.get("address"),
        data.get("endereco"),
    )
    number = _first_non_empty(data.get("number"), data.get("numero"))
    complement = _first_non_empty(data.get("complement"), data.get("complemento"))
    district = _first_non_empty(data.get("district"), data.get("bairro"))
    city = _first_non_empty(data.get("city"), data.get("municipio"), data.get("cidade"))
    state = _first_non_empty(data.get("state"), data.get("uf"))
    zip_code = _first_non_empty(data.get("zip_code"), data.get("cep"))

    line_one = ", ".join(part for part in [street, number] if part)
    if complement:
        line_one = ", ".join(part for part in [line_one, complement] if part)
    city_state = " - ".join(part for part in [city, state] if part)
    line_two = ", ".join(part for part in [district, city_state] if part)
    address = ", ".join(part for part in [line_one, line_two] if part)
    if zip_code:
        address = ", ".join(part for part in [address, f"CEP {zip_code}"] if part)
    return address


@login_required
@require_POST
def business_zip_lookup(request: HttpRequest) -> JsonResponse:
    zip_code = re.sub(r"\D", "", request.POST.get("cep", ""))
    if len(zip_code) != 8:
        return JsonResponse({"ok": False, "error": "Informe um CEP válido com 8 dígitos."}, status=400)

    if not django_settings.APIBRASIL_CEP_URL:
        return JsonResponse({"ok": False, "error": "Busca de CEP não configurada no ambiente."}, status=503)

    headers = {"Accept": "application/json"}
    if django_settings.APIBRASIL_CEP_TOKEN:
        headers["Authorization"] = f"Bearer {django_settings.APIBRASIL_CEP_TOKEN}"
        headers["X-API-KEY"] = django_settings.APIBRASIL_CEP_TOKEN

    request_url = django_settings.APIBRASIL_CEP_URL.format(cep=zip_code)
    request_object = Request(request_url, headers=headers)

    try:
        with urlopen(request_object, timeout=django_settings.APIBRASIL_CEP_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError:
        return JsonResponse({"ok": False, "error": "Não foi possível consultar esse CEP agora."}, status=502)
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "A busca de CEP falhou. Tente novamente."}, status=502)

    data = payload
    if isinstance(payload, dict):
        for key in ("result", "data", "response"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                data = nested
                break

    if not isinstance(data, dict):
        data = {}

    if isinstance(payload, dict) and (payload.get("error") or payload.get("status") in {"ERROR", "error"}):
        return JsonResponse(
            {
                "ok": False,
                "error": _first_non_empty(
                    payload.get("message"),
                    data.get("message"),
                    "CEP não encontrado.",
                ),
            },
            status=404,
        )

    street = _first_non_empty(
        data.get("street"),
        data.get("logradouro"),
        data.get("address"),
        data.get("endereco"),
    )
    if not street:
        return JsonResponse({"ok": False, "error": "Não encontramos a rua desse CEP."}, status=404)
    normalized_zip_code = _first_non_empty(
        data.get("cep"),
        payload.get("cep") if isinstance(payload, dict) else "",
    ) or f"{zip_code[:5]}-{zip_code[5:]}"

    return JsonResponse(
        {
            "ok": True,
            "zip_code": normalized_zip_code,
            "street": street,
        }
    )


@login_required
def business_cnpj_lookup(request: HttpRequest) -> JsonResponse:
    cnpj = re.sub(r"\D", "", request.GET.get("cnpj", ""))
    if len(cnpj) != 14:
        return JsonResponse({"ok": False, "error": "Informe um CNPJ válido com 14 dígitos."}, status=400)

    if not django_settings.APIBRASIL_CNPJ_URL:
        return JsonResponse({"ok": False, "error": "Busca de CNPJ não configurada no ambiente."}, status=503)

    headers = {"Accept": "application/json"}
    if django_settings.APIBRASIL_CNPJ_TOKEN:
        headers["Authorization"] = f"Bearer {django_settings.APIBRASIL_CNPJ_TOKEN}"
        headers["X-API-KEY"] = django_settings.APIBRASIL_CNPJ_TOKEN

    request_url = django_settings.APIBRASIL_CNPJ_URL.format(cnpj=cnpj)
    request_object = Request(request_url, headers=headers)

    try:
        with urlopen(request_object, timeout=django_settings.APIBRASIL_CNPJ_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError:
        return JsonResponse({"ok": False, "error": "Não foi possível consultar esse CNPJ agora."}, status=502)
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "A busca de CNPJ falhou. Tente novamente."}, status=502)

    data = payload
    if isinstance(payload, dict):
        for key in ("result", "data", "response"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                data = nested
                break

    if not isinstance(data, dict):
        data = {}

    if isinstance(payload, dict) and (payload.get("error") or payload.get("status") in {"ERROR", "error"}):
        return JsonResponse(
            {
                "ok": False,
                "error": _first_non_empty(
                    payload.get("message"),
                    data.get("message"),
                    "CNPJ não encontrado.",
                ),
            },
            status=404,
        )

    legal_name = _first_non_empty(
        data.get("razao_social"),
        data.get("social_reason"),
        data.get("corporate_name"),
        data.get("company_name"),
        data.get("nome"),
        data.get("name"),
    )
    if not legal_name:
        return JsonResponse({"ok": False, "error": "Não encontramos a razão social desse CNPJ."}, status=404)

    phone = _first_non_empty(
        data.get("telefone"),
        data.get("phone"),
        data.get("telefone_1"),
        data.get("ddd_telefone_1"),
    )

    return JsonResponse(
        {
            "ok": True,
            "company_legal_name": legal_name,
            "company_cnpj": _format_cnpj(_first_non_empty(data.get("cnpj"), cnpj) or cnpj),
            "company_address": _compose_company_address(data),
            "company_phone": phone,
        }
    )


def _long_date_label(raw_date: date) -> str:
    months = {
        1: "janeiro",
        2: "fevereiro",
        3: "março",
        4: "abril",
        5: "maio",
        6: "junho",
        7: "julho",
        8: "agosto",
        9: "setembro",
        10: "outubro",
        11: "novembro",
        12: "dezembro",
    }
    return f"{raw_date.day} de {months[raw_date.month]} de {raw_date.year}"


def _contract_placeholder(value: str | None, fallback: str = "________________") -> str:
    normalized = (value or "").strip()
    return normalized or fallback


def _license_term_labels(days: int | None) -> tuple[str, str]:
    mapping = {
        90: ("03 (três) meses", "90 (noventa) dias"),
        180: ("06 (seis) meses", "180 (cento e oitenta) dias"),
        270: ("09 (nove) meses", "270 (duzentos e setenta) dias"),
        360: ("12 (doze) meses", "360 (trezentos e sessenta) dias"),
    }
    return mapping.get(days or 90, ("03 (três) meses", "90 (noventa) dias"))


def _legal_count_label(value: int) -> str:
    mapping = {
        1: "um",
        2: "dois",
        3: "três",
        4: "quatro",
        5: "cinco",
        6: "seis",
        7: "sete",
        8: "oito",
        9: "nove",
        10: "dez",
        11: "onze",
        12: "doze",
    }
    normalized = max(0, int(value or 0))
    written = mapping.get(normalized, str(normalized))
    return f"{normalized:02d} ({written})"


def _contract_clause_five_text(payload: dict) -> str:
    if payload["is_ads"]:
        return (
            "5.1. O prazo de utilização do conteúdo em tráfego pago (ads) e uso orgânico terá início na data da entrega final do conteúdo, "
            "independentemente da data em que este vier a ser efetivamente publicado ou veiculado.<br/>"
            "5.2. No caso de uso orgânico, a CONTRATANTE terá direito de uso do conteúdo de forma vitalícia em seus perfis de redes sociais, "
            "incluindo, mas não se limitando a, Instagram, TikTok, Pinterest e YouTube.<br/>"
            f"5.3. No caso de tráfego pago (ads), incluindo sites, marketplace da marca e plataformas como Facebook Ads, Instagram Ads, "
            f"Pinterest Ads, TikTok Ads e YouTube Ads, a licença de uso será válida pelo período de "
            f"<b>{payload['image_term_months_text']}</b>, equivalente a <b>{payload['image_term_days_text']}</b>.<br/>"
            "5.4. Após esse período, a continuidade da veiculação do conteúdo em tráfego pago dependerá de nova negociação entre as partes, "
            "mediante novo contrato ou termo aditivo.<br/>"
            "5.5. O valor para renovação da licença de uso em tráfego pago corresponderá a 30% do valor unitário do conteúdo entregue, "
            "podendo a renovação ser feita por período mínimo de 03 (três) meses.<br/>"
            "5.6. Havendo controvérsias, discordâncias ou alterações na campanha de tráfego pago, as partes poderão renegociar os termos deste "
            "contrato, mediante mútuo acordo.<br/>"
            "5.7. Caso qualquer das partes deseje encerrar ou alterar este contrato, deverá comunicar a outra por escrito com antecedência "
            "mínima de 20 (vinte) dias, a fim de que sejam ajustadas eventuais pendências financeiras ou operacionais.<br/>"
            "5.8. Todas as comunicações formais relacionadas a encerramento, alteração ou renovação deverão ser feitas pelos e-mails informados "
            "no cabeçalho deste contrato."
        )

    return (
        "5.1. O prazo de utilização do conteúdo para uso orgânico terá início na data da entrega final do conteúdo, independentemente da data "
        "em que este vier a ser efetivamente publicado ou veiculado.<br/>"
        "5.2. A CONTRATANTE terá direito de uso do conteúdo de forma vitalícia em seus perfis de redes sociais, incluindo, mas não se "
        "limitando a, Instagram, TikTok, Pinterest e YouTube.<br/>"
        "5.3. Qualquer intenção de utilizar o conteúdo em tráfego pago (ads), marketplace, sites ou outras plataformas de mídia patrocinada "
        "dependerá de nova negociação entre as partes, mediante contrato ou termo aditivo específico.<br/>"
        "5.4. Todas as comunicações formais relacionadas a alteração, renovação ou ampliação do escopo deverão ser feitas pelos e-mails "
        "informados no cabeçalho deste contrato."
    )


def _project_contract_payload(workspace, user, project: Project) -> dict:
    settings_values = settings_map(workspace)
    creator_name = _contract_placeholder(
        workspace.business_full_name or settings_values.get("legal_contract_signer_name") or user.get_full_name() or user.username
    )
    creator_email = _contract_placeholder(user.email)
    creator_address = _contract_placeholder(workspace_business_address_summary(workspace))
    creator_cnpj = _contract_placeholder(workspace.business_cnpj)
    creator_pix_key = _contract_placeholder(workspace.business_pis)
    company_name = _contract_placeholder(project.company_legal_name or project.company)
    is_ads = project.content_distribution == "Ads"
    distribution_label = "tráfego pago (ads)" if project.content_distribution == "Ads" else "uso orgânico"
    mixed_distribution_label = (
        "uso orgânico e tráfego pago (ads)"
        if is_ads
        else "uso orgânico"
    )
    contract_title = (
        "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE CRIAÇÃO DE CONTEÚDO UGC PARA USO ORGÂNICO E TRÁFEGO PAGO (ADS)"
        if is_ads
        else "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE CRIAÇÃO DE CONTEÚDO UGC PARA USO ORGÂNICO"
    )
    service_name = _contract_placeholder(project.service_category_name)
    total_value = f"R$ {project.total_value:.2f}".replace(".", ",")
    entry_value = f"R$ {project.entry_value:.2f}".replace(".", ",")
    balance_value = f"R$ {(project.total_value - project.entry_value):.2f}".replace(".", ",")
    due_date_text = _long_date_label(project.due_date)
    close_date_text = _long_date_label(project.close_date)
    image_term = project.image_license_term_days or 90
    image_term_months_text, image_term_days_text = _license_term_labels(image_term)
    license_expires_on = project.image_usage_expires_on or project.due_date

    return {
        "is_ads": is_ads,
        "contract_title": contract_title,
        "creator_name": creator_name,
        "creator_email": creator_email,
        "creator_address": creator_address,
        "creator_cnpj": creator_cnpj,
        "creator_pix_key": creator_pix_key,
        "company_name": company_name,
        "company_display_name": _contract_placeholder(project.company),
        "company_cnpj": _contract_placeholder(project.company_cnpj),
        "company_address": _contract_placeholder(project.company_address),
        "company_phone": _contract_placeholder(project.company_phone),
        "company_email": "________________",
        "service_name": service_name,
        "distribution_label": distribution_label,
        "mixed_distribution_label": mixed_distribution_label,
        "deliverables_count": project.deliverables_count,
        "deliverables_count_label": _legal_count_label(project.deliverables_count),
        "deliverables_text": f"{project.deliverables_count} vídeo(s) UGC",
        "total_value": total_value,
        "entry_value": entry_value,
        "balance_value": balance_value,
        "close_date_text": close_date_text,
        "due_date_text": due_date_text,
        "payment_due_date_text": _long_date_label(project.payment_due_date or project.due_date),
        "image_term": image_term,
        "image_term_months_text": image_term_months_text,
        "image_term_days_text": image_term_days_text,
        "license_expires_on_text": _long_date_label(license_expires_on),
        "project_note": (project.note or "").strip(),
    }


def _contract_intro_paragraphs(payload: dict) -> list[str]:
    return [
        (
            f"<b>CONTRATADA:</b><br/>"
            f"{payload['creator_name']}, brasileira, solteira, Criadora de Conteúdo UGC, inscrita no CNPJ sob o nº "
            f"{payload['creator_cnpj']}, residente e domiciliada em {payload['creator_address']}, e-mail "
            f"{payload['creator_email']}.<br/><br/>"
            f"<b>CONTRATANTE:</b><br/>"
            f"{payload['company_name']}, pessoa jurídica de direito privado, inscrita no CNPJ sob o nº "
            f"{payload['company_cnpj']}, com sede em {payload['company_address']}, telefone {payload['company_phone']} "
            f"e e-mail {payload['company_email']}."
        ),
        (
            "As partes acima identificadas têm entre si justo e contratado o presente Contrato de Prestação de "
            "Serviços de Criação de Conteúdo UGC, que se regerá pelas cláusulas e condições a seguir."
        ),
    ]


def _contract_clauses(payload: dict) -> list[dict[str, str]]:
    return [
        {
            "key": "1",
            "title": "CLÁUSULA 1 - DO OBJETO",
            "body": (
                "1.1. O presente contrato tem por objeto a prestação de serviços de criação de conteúdo do tipo UGC "
                f"(User Generated Content) pela CONTRATADA, com a finalidade de promover os produtos ou serviços da "
                f"CONTRATANTE, para utilização em <b>{payload['mixed_distribution_label']}</b>.<br/>"
                "1.2. A CONTRATADA compromete-se a personalizar os entregáveis de acordo com as necessidades específicas "
                f"da CONTRATANTE, dentro do escopo dos serviços previamente alinhados para o trabalho "
                f"<b>{payload['service_name']}</b>.<br/>"
                "1.3. Os conteúdos criados poderão incluir, sem limitação: vídeos, imagens, textos e outros formatos, "
                "conforme ajuste prévio entre as partes."
            ),
        },
        {
            "key": "2",
            "title": "CLÁUSULA 2 - DAS OBRIGAÇÕES DA CONTRATADA",
            "body": (
                "2.1. São obrigações da CONTRATADA:<br/>"
                "a) Criar os conteúdos de acordo com o briefing e cronograma fornecidos pela CONTRATANTE.<br/>"
                "b) Garantir que os conteúdos sejam originais e atendam aos padrões de qualidade solicitados pela CONTRATANTE.<br/>"
                "c) Realizar eventuais ajustes no conteúdo criado, caso solicitados pela CONTRATANTE, respeitando o prazo de até "
                "7 (sete) dias corridos após a entrega inicial.<br/>"
                "d) Respeitar as políticas de privacidade, direitos autorais e regulamentações aplicáveis.<br/>"
                "e) Garantir a entrega do material dentro do prazo previamente acordado entre as partes."
            ),
        },
        {
            "key": "3",
            "title": "CLÁUSULA 3 - DAS OBRIGAÇÕES DA CONTRATANTE",
            "body": (
                "3.1. São obrigações da CONTRATANTE:<br/>"
                "a) Fornecer as informações, briefings e materiais necessários para o desenvolvimento do conteúdo.<br/>"
                "b) Efetuar os pagamentos nos prazos e condições estabelecidos neste contrato.<br/>"
                "c) Utilizar os conteúdos criados exclusivamente nos termos acordados neste instrumento.<br/>"
                "d) Garantir que os dados e informações fornecidos à CONTRATADA estejam em conformidade com a Lei Geral de "
                "Proteção de Dados (Lei nº 13.709/2018 - LGPD)."
            ),
        },
        {
            "key": "4",
            "title": "CLÁUSULA 4 - DOS ENTREGÁVEIS",
            "body": (
                f"4.1. As partes acordam que os serviços consistirão em criação de conteúdo UGC, compreendendo a gravação de "
                f"<b>{payload['deliverables_count_label']}</b> roteiros desenvolvidos pela CONTRATADA, edição e entrega do material "
                f"por meio do Google Drive, até <b>{payload['due_date_text']}</b>, conforme cronograma alinhado entre as partes.<br/>"
                f"4.2. A CONTRATADA produzirá <b>{payload['deliverables_count_label']}</b> vídeos, com duração mínima de 15 segundos "
                "e máxima de 90 segundos cada.<br/>"
                "4.3. Antes da gravação, a CONTRATADA submeterá à CONTRATANTE a ideia e o roteiro do conteúdo para aprovação.<br/>"
                "4.4. A CONTRATANTE compromete-se a revisar o material e encaminhar eventuais solicitações de edição em até 07 "
                "(sete) dias após a entrega do conteúdo.<br/>"
                "4.5. A CONTRATANTE compromete-se a enviar o(s) produto(s) necessário(s) para a execução do trabalho no endereço "
                "informado no cabeçalho deste contrato.<br/>"
                "4.6. A CONTRATADA realizará até 03 (três) reedições gratuitas por vídeo, limitadas a ajustes básicos de edição, "
                "como vídeo, música, narração, texto em tela e recortes. Tais reedições não incluem regravações.<br/>"
                "4.7. Regravações somente serão permitidas caso a CONTRATADA se afaste substancialmente do briefing e do conceito "
                "previamente aprovados pela CONTRATANTE.<br/>"
                "4.8. Caso sejam necessárias mais de 03 (três) reedições, regravações ou qualquer outro serviço adicional, será "
                "cobrada taxa extra, a ser negociada entre as partes.<br/>"
                "4.9. A CONTRATANTE deverá aprovar o conteúdo em até 07 (sete) dias úteis após a entrega via Google Drive.<br/>"
                f"4.10. Observações adicionais do job: "
                f"{payload['project_note'] or 'seguir o briefing e os alinhamentos previamente aprovados entre as partes.'}"
            ),
        },
        {
            "key": "5",
            "title": "CLÁUSULA 5 - DA VIGÊNCIA E DO PRAZO DE VEICULAÇÃO DO CONTEÚDO",
            "body": _contract_clause_five_text(payload),
        },
        {
            "key": "6",
            "title": "CLÁUSULA 6 - DO PAGAMENTO",
            "body": (
                f"6.1. Pelos serviços de criação de conteúdo UGC, a CONTRATANTE pagará à CONTRATADA o valor total de "
                f"<b>{payload['total_value']}</b>, correspondente à produção de <b>{payload['deliverables_count_label']}</b> vídeos "
                f"para uso em <b>{payload['mixed_distribution_label']}</b>.<br/>"
                "6.2. O pagamento será realizado da seguinte forma:<br/>"
                f"a) Entrada de <b>{payload['entry_value']}</b> na data da assinatura deste contrato.<br/>"
                f"b) Saldo remanescente de <b>{payload['balance_value']}</b> na entrega e aprovação final do conteúdo, observado o "
                f"vencimento previsto para <b>{payload['payment_due_date_text']}</b>.<br/>"
                "6.3. A CONTRATADA removerá quaisquer marcas d’água dos vídeos após a quitação integral do valor contratado.<br/>"
                "6.4. A CONTRATANTE será responsável por todas as despesas de envio e entrega dos produtos necessários à execução dos serviços.<br/>"
                "6.5. A CONTRATADA aceita pagamento por meio de PIX e/ou transferência bancária, conforme ajustado entre as partes.<br/>"
                "6.6. Os pagamentos deverão ser realizados na conta indicada pela CONTRATADA, conforme os dados abaixo:<br/>"
                f"Chave PIX: <b>{payload['creator_pix_key']}</b>"
            ),
        },
        {
            "key": "7",
            "title": "CLÁUSULA 7 - DOS DIREITOS AUTORAIS E DO USO DE IMAGEM",
            "body": (
                "7.1. A CONTRATADA permanece titular de todos os direitos autorais sobre os conteúdos produzidos, incluindo vídeos, "
                "fotografias, roteiros e demais materiais criados no âmbito deste contrato.<br/>"
                f"7.2. O conteúdo fornecido à CONTRATANTE destina-se exclusivamente ao uso em <b>{payload['mixed_distribution_label']}</b>, "
                "nos limites e prazos previstos neste contrato.<br/>"
                "7.3. Nenhuma licença para venda, sublicenciamento, redistribuição ou cessão a terceiros será presumida ou concedida, "
                "salvo autorização expressa e por escrito da CONTRATADA.<br/>"
                "7.4. A cessão de uso do conteúdo fica restrita ao objeto deste contrato, sendo vedado à CONTRATANTE sublicenciar, "
                "vender ou redistribuir os conteúdos a terceiros sem autorização expressa da CONTRATADA.<br/>"
                "7.5. A CONTRATANTE será responsável por quaisquer perdas, danos, custos ou despesas decorrentes de uso não autorizado "
                "do conteúdo, obrigando-se a indenizar e isentar a CONTRATADA por eventuais prejuízos decorrentes desse uso indevido.<br/>"
                "7.6. A CONTRATADA poderá repostar o conteúdo em suas próprias redes sociais para uso orgânico, incluindo TikTok, "
                "Instagram e outras plataformas, sendo vedada sua utilização em tráfego pago por parte da CONTRATADA, salvo ajuste diverso entre as partes.<br/>"
                "7.7. Caso a CONTRATANTE deseje reutilizar ou renovar a licença de uso de imagem do conteúdo para anúncios pagos, site "
                "ou outras plataformas, após o período inicialmente estipulado, deverá formalizar a solicitação por escrito à CONTRATADA, "
                "por meio de novo contrato ou termo aditivo.<br/>"
                "7.8. A renovação da licença será negociada entre as partes mediante pagamento equivalente a 30% do valor unitário do conteúdo, "
                "por período mínimo de 03 (três) meses, limitado a 12 (doze) meses por renovação.<br/>"
                "7.9. A utilização da imagem, voz ou identidade da CONTRATADA em campanhas ficará restrita ao período de veiculação e "
                "às plataformas previstas neste contrato."
            ),
        },
        {
            "key": "8",
            "title": "CLÁUSULA 8 - DA EXCLUSIVIDADE E CONFIDENCIALIDADE",
            "body": (
                "8.1. O presente contrato não gera vínculo empregatício, societário, de representação, parceria ou subordinação entre as partes.<br/>"
                "8.2. Salvo disposição expressa em sentido contrário, não haverá exclusividade entre as partes, podendo ambas contratar "
                "ou prestar serviços a terceiros, inclusive em atividades similares.<br/>"
                "8.3. As partes comprometem-se a manter confidenciais todas as informações trocadas no âmbito deste contrato, incluindo "
                "estratégias, conteúdos, briefings, dados e demais materiais compartilhados."
            ),
        },
        {
            "key": "9",
            "title": "CLÁUSULA 9 - DA RESPONSABILIDADE DAS PARTES",
            "body": (
                "9.1. Na medida permitida por lei, a CONTRATADA não se responsabiliza por danos ou prejuízos sofridos pela CONTRATANTE "
                "ou por terceiros em decorrência de uso indevido do conteúdo ou de utilização fora dos limites contratados.<br/>"
                "9.2. As partes obrigam-se a defender, indenizar e isentar uma à outra de quaisquer responsabilidades, despesas, reclamações, "
                "danos, condenações, acordos, custos e honorários advocatícios decorrentes do descumprimento deste contrato, ressalvadas as "
                "hipóteses de negligência exclusiva ou conduta dolosa da parte prejudicada."
            ),
        },
        {
            "key": "10",
            "title": "CLÁUSULA 10 - DA LGPD",
            "body": (
                "10.1. Ambas as partes comprometem-se a respeitar a privacidade e os dados pessoais coletados e tratados no âmbito deste "
                "contrato, em conformidade com a Lei Geral de Proteção de Dados - LGPD (Lei nº 13.709/2018).<br/>"
                "10.2. A CONTRATADA autoriza a CONTRATANTE a utilizar seus dados pessoais apenas quando necessário e exclusivamente para "
                "fins de envio de produtos e comunicação relacionada ao objeto deste contrato.<br/>"
                "10.3. A CONTRATANTE declara que utilizará os conteúdos criados exclusivamente para os fins contratados, abstendo-se de "
                "qualquer uso ilícito ou que viole os direitos da CONTRATADA."
            ),
        },
        {
            "key": "11",
            "title": "CLÁUSULA 11 - DAS DISPOSIÇÕES GERAIS E DO FORO",
            "body": (
                "11.1. Qualquer alteração neste contrato somente terá validade se realizada por meio de termo aditivo por escrito, "
                "assinado por ambas as partes.<br/>"
                "11.2. Para dirimir quaisquer controvérsias oriundas deste contrato, as partes elegem o foro da Comarca de Salvador, "
                "Estado da Bahia, com renúncia de qualquer outro, por mais privilegiado que seja."
            ),
        },
    ]


def _contract_html_to_editor_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value or "", flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def _contract_editor_text_to_html(value: str) -> str:
    normalized = "\n".join(line.rstrip() for line in (value or "").splitlines()).strip()
    return escape(normalized or " ").replace("\n", "<br/>")


def _contract_clauses_for_editor(payload: dict) -> list[dict[str, str]]:
    return [
        {**clause, "body_text": _contract_html_to_editor_text(clause["body"])}
        for clause in _contract_clauses(payload)
    ]


def _contract_clauses_from_post(payload: dict, post_data) -> list[dict[str, str]]:
    clauses = []
    for clause in _contract_clauses(payload):
        field_name = f"clause_body_{clause['key']}"
        raw_body = post_data.get(field_name)
        if raw_body is None:
            clauses.append(clause)
            continue
        if raw_body.strip() == _contract_html_to_editor_text(clause["body"]).strip():
            clauses.append(clause)
        else:
            clauses.append({**clause, "body": _contract_editor_text_to_html(raw_body)})
    return clauses


def _save_contract_brand_data(project: Project, post_data) -> bool:
    form = ContractBrandForm(post_data)
    if not form.is_valid():
        return False
    for field_name, value in form.cleaned_data.items():
        setattr(project, field_name, value)
    project.save(
        update_fields=[
            "company_legal_name",
            "company_cnpj",
            "company_address",
            "company_phone",
            "updated_at",
        ]
    )
    return True


def _build_contract_pdf_from_clauses(workspace, user, project: Project, clauses: list[dict[str, str]] | None = None) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    payload = _project_contract_payload(workspace, user, project)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=f"Contrato - {payload['company_name']}",
        pageCompression=0,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1a2649"),
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "ContractSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1a2649"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ContractBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=14,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#24334d"),
        spaceAfter=6,
    )
    signature_style = ParagraphStyle(
        "ContractSignature",
        parent=body_style,
        alignment=TA_CENTER,
        spaceBefore=10,
    )

    story = [Paragraph(payload["contract_title"], title_style)]
    story.extend(Paragraph(paragraph, body_style) for paragraph in _contract_intro_paragraphs(payload))
    for clause in clauses or _contract_clauses(payload):
        story.append(Paragraph(clause["title"], section_style))
        story.append(Paragraph(clause["body"], body_style))
    story.extend(
        [
            Spacer(1, 20),
            Paragraph(
                "E, por estarem justas e contratadas, firmam o presente instrumento em 02 (duas) vias de igual teor e forma, para que produza seus efeitos legais.",
                body_style,
            ),
            Paragraph(f"Salvador/BA, {payload['close_date_text']}.", body_style),
            Spacer(1, 26),
            Paragraph("__________________________________", signature_style),
            Paragraph(f"{payload['creator_name']}<br/>CNPJ nº {payload['creator_cnpj']}", signature_style),
            Spacer(1, 12),
            Paragraph("__________________________________", signature_style),
            Paragraph(f"{payload['company_name']}<br/>CNPJ nº {payload['company_cnpj']}", signature_style),
        ]
    )

    document.build(story)
    return buffer.getvalue()


def _build_contract_pdf(workspace, user, project: Project) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    payload = _project_contract_payload(workspace, user, project)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=f"Contrato - {payload['company_name']}",
        pageCompression=0,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#1a2649"),
        spaceAfter=14,
    )
    section_style = ParagraphStyle(
        "ContractSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1a2649"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ContractBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.6,
        leading=14,
        alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#24334d"),
        spaceAfter=6,
    )
    signature_style = ParagraphStyle(
        "ContractSignature",
        parent=body_style,
        alignment=TA_CENTER,
        spaceBefore=10,
    )

    story = [
        Paragraph(payload["contract_title"], title_style),
        Paragraph(
            (
                f"<b>CONTRATADA:</b><br/>"
                f"{payload['creator_name']}, brasileira, solteira, Criadora de Conteúdo UGC, inscrita no CNPJ sob o nº "
                f"{payload['creator_cnpj']}, residente e domiciliada em {payload['creator_address']}, e-mail "
                f"{payload['creator_email']}.<br/><br/>"
                f"<b>CONTRATANTE:</b><br/>"
                f"{payload['company_name']}, pessoa jurídica de direito privado, inscrita no CNPJ sob o nº "
                f"{payload['company_cnpj']}, com sede em {payload['company_address']}, telefone {payload['company_phone']} "
                f"e e-mail {payload['company_email']}."
            ),
            body_style,
        ),
        Paragraph(
            (
                "As partes acima identificadas têm entre si justo e contratado o presente Contrato de Prestação de "
                "Serviços de Criação de Conteúdo UGC, que se regerá pelas cláusulas e condições a seguir."
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 1 - DO OBJETO", section_style),
        Paragraph(
            (
                "1.1. O presente contrato tem por objeto a prestação de serviços de criação de conteúdo do tipo UGC "
                f"(User Generated Content) pela CONTRATADA, com a finalidade de promover os produtos ou serviços da "
                f"CONTRATANTE, para utilização em <b>{payload['mixed_distribution_label']}</b>.<br/>"
                "1.2. A CONTRATADA compromete-se a personalizar os entregáveis de acordo com as necessidades específicas "
                f"da CONTRATANTE, dentro do escopo dos serviços previamente alinhados para o trabalho "
                f"<b>{payload['service_name']}</b>.<br/>"
                "1.3. Os conteúdos criados poderão incluir, sem limitação: vídeos, imagens, textos e outros formatos, "
                "conforme ajuste prévio entre as partes."
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 2 - DAS OBRIGAÇÕES DA CONTRATADA", section_style),
        Paragraph(
            (
                "2.1. São obrigações da CONTRATADA:<br/>"
                "a) Criar os conteúdos de acordo com o briefing e cronograma fornecidos pela CONTRATANTE.<br/>"
                "b) Garantir que os conteúdos sejam originais e atendam aos padrões de qualidade solicitados pela CONTRATANTE.<br/>"
                "c) Realizar eventuais ajustes no conteúdo criado, caso solicitados pela CONTRATANTE, respeitando o prazo de até "
                "7 (sete) dias corridos após a entrega inicial.<br/>"
                "d) Respeitar as políticas de privacidade, direitos autorais e regulamentações aplicáveis.<br/>"
                "e) Garantir a entrega do material dentro do prazo previamente acordado entre as partes."
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 3 - DAS OBRIGAÇÕES DA CONTRATANTE", section_style),
        Paragraph(
            (
                "3.1. São obrigações da CONTRATANTE:<br/>"
                "a) Fornecer as informações, briefings e materiais necessários para o desenvolvimento do conteúdo.<br/>"
                "b) Efetuar os pagamentos nos prazos e condições estabelecidos neste contrato.<br/>"
                "c) Utilizar os conteúdos criados exclusivamente nos termos acordados neste instrumento.<br/>"
                "d) Garantir que os dados e informações fornecidos à CONTRATADA estejam em conformidade com a Lei Geral de "
                "Proteção de Dados (Lei nº 13.709/2018 - LGPD)."
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 4 - DOS ENTREGÁVEIS", section_style),
        Paragraph(
            (
                f"4.1. As partes acordam que os serviços consistirão em criação de conteúdo UGC, compreendendo a gravação de "
                f"<b>{payload['deliverables_count_label']}</b> roteiros desenvolvidos pela CONTRATADA, edição e entrega do material "
                f"por meio do Google Drive, até <b>{payload['due_date_text']}</b>, conforme cronograma alinhado entre as partes.<br/>"
                f"4.2. A CONTRATADA produzirá <b>{payload['deliverables_count_label']}</b> vídeos, com duração mínima de 15 segundos "
                "e máxima de 90 segundos cada.<br/>"
                "4.3. Antes da gravação, a CONTRATADA submeterá à CONTRATANTE a ideia e o roteiro do conteúdo para aprovação.<br/>"
                "4.4. A CONTRATANTE compromete-se a revisar o material e encaminhar eventuais solicitações de edição em até 07 "
                "(sete) dias após a entrega do conteúdo.<br/>"
                "4.5. A CONTRATANTE compromete-se a enviar o(s) produto(s) necessário(s) para a execução do trabalho no endereço "
                "informado no cabeçalho deste contrato.<br/>"
                "4.6. A CONTRATADA realizará até 03 (três) reedições gratuitas por vídeo, limitadas a ajustes básicos de edição, "
                "como vídeo, música, narração, texto em tela e recortes. Tais reedições não incluem regravações.<br/>"
                "4.7. Regravações somente serão permitidas caso a CONTRATADA se afaste substancialmente do briefing e do conceito "
                "previamente aprovados pela CONTRATANTE.<br/>"
                "4.8. Caso sejam necessárias mais de 03 (três) reedições, regravações ou qualquer outro serviço adicional, será "
                "cobrada taxa extra, a ser negociada entre as partes.<br/>"
                "4.9. A CONTRATANTE deverá aprovar o conteúdo em até 07 (sete) dias úteis após a entrega via Google Drive."
            ),
            body_style,
        ),
        Paragraph(
            (
                f"4.10. Observações adicionais do job: "
                f"{payload['project_note'] or 'seguir o briefing e os alinhamentos previamente aprovados entre as partes.'}"
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 5 - DA VIGÊNCIA E DO PRAZO DE VEICULAÇÃO DO CONTEÚDO", section_style),
        Paragraph(_contract_clause_five_text(payload), body_style),
        Paragraph("CLÁUSULA 6 - DO PAGAMENTO", section_style),
        Paragraph(
            (
                f"6.1. Pelos serviços de criação de conteúdo UGC, a CONTRATANTE pagará à CONTRATADA o valor total de "
                f"<b>{payload['total_value']}</b>, correspondente à produção de <b>{payload['deliverables_count_label']}</b> vídeos "
                f"para uso em <b>{payload['mixed_distribution_label']}</b>.<br/>"
                "6.2. O pagamento será realizado da seguinte forma:<br/>"
                f"a) Entrada de <b>{payload['entry_value']}</b> na data da assinatura deste contrato.<br/>"
                f"b) Saldo remanescente de <b>{payload['balance_value']}</b> na entrega e aprovação final do conteúdo, observado o "
                f"vencimento previsto para <b>{payload['payment_due_date_text']}</b>.<br/>"
                "6.3. A CONTRATADA removerá quaisquer marcas d’água dos vídeos após a quitação integral do valor contratado.<br/>"
                "6.4. A CONTRATANTE será responsável por todas as despesas de envio e entrega dos produtos necessários à execução dos serviços.<br/>"
                "6.5. A CONTRATADA aceita pagamento por meio de PIX e/ou transferência bancária, conforme ajustado entre as partes.<br/>"
                "6.6. Os pagamentos deverão ser realizados na conta indicada pela CONTRATADA, conforme os dados abaixo:<br/>"
                f"Chave PIX: <b>{payload['creator_pix_key']}</b>"
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 7 - DOS DIREITOS AUTORAIS E DO USO DE IMAGEM", section_style),
        Paragraph(
            (
                "7.1. A CONTRATADA permanece titular de todos os direitos autorais sobre os conteúdos produzidos, incluindo vídeos, "
                "fotografias, roteiros e demais materiais criados no âmbito deste contrato.<br/>"
                f"7.2. O conteúdo fornecido à CONTRATANTE destina-se exclusivamente ao uso em <b>{payload['mixed_distribution_label']}</b>, "
                "nos limites e prazos previstos neste contrato.<br/>"
                "7.3. Nenhuma licença para venda, sublicenciamento, redistribuição ou cessão a terceiros será presumida ou concedida, "
                "salvo autorização expressa e por escrito da CONTRATADA.<br/>"
                "7.4. A cessão de uso do conteúdo fica restrita ao objeto deste contrato, sendo vedado à CONTRATANTE sublicenciar, "
                "vender ou redistribuir os conteúdos a terceiros sem autorização expressa da CONTRATADA.<br/>"
                "7.5. A CONTRATANTE será responsável por quaisquer perdas, danos, custos ou despesas decorrentes de uso não autorizado "
                "do conteúdo, obrigando-se a indenizar e isentar a CONTRATADA por eventuais prejuízos decorrentes desse uso indevido.<br/>"
                "7.6. A CONTRATADA poderá repostar o conteúdo em suas próprias redes sociais para uso orgânico, incluindo TikTok, "
                "Instagram e outras plataformas, sendo vedada sua utilização em tráfego pago por parte da CONTRATADA, salvo ajuste diverso entre as partes.<br/>"
                "7.7. Caso a CONTRATANTE deseje reutilizar ou renovar a licença de uso de imagem do conteúdo para anúncios pagos, site "
                "ou outras plataformas, após o período inicialmente estipulado, deverá formalizar a solicitação por escrito à CONTRATADA, "
                "por meio de novo contrato ou termo aditivo.<br/>"
                "7.8. A renovação da licença será negociada entre as partes mediante pagamento equivalente a 30% do valor unitário do conteúdo, "
                "por período mínimo de 03 (três) meses, limitado a 12 (doze) meses por renovação.<br/>"
                "7.9. A utilização da imagem, voz ou identidade da CONTRATADA em campanhas ficará restrita ao período de veiculação e "
                "às plataformas previstas neste contrato."
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 8 - DA EXCLUSIVIDADE E CONFIDENCIALIDADE", section_style),
        Paragraph(
            (
                "8.1. O presente contrato não gera vínculo empregatício, societário, de representação, parceria ou subordinação entre as partes.<br/>"
                "8.2. Salvo disposição expressa em sentido contrário, não haverá exclusividade entre as partes, podendo ambas contratar "
                "ou prestar serviços a terceiros, inclusive em atividades similares.<br/>"
                "8.3. As partes comprometem-se a manter confidenciais todas as informações trocadas no âmbito deste contrato, incluindo "
                "estratégias, conteúdos, briefings, dados e demais materiais compartilhados."
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 9 - DA RESPONSABILIDADE DAS PARTES", section_style),
        Paragraph(
            (
                "9.1. Na medida permitida por lei, a CONTRATADA não se responsabiliza por danos ou prejuízos sofridos pela CONTRATANTE "
                "ou por terceiros em decorrência de uso indevido do conteúdo ou de utilização fora dos limites contratados.<br/>"
                "9.2. As partes obrigam-se a defender, indenizar e isentar uma à outra de quaisquer responsabilidades, despesas, reclamações, "
                "danos, condenações, acordos, custos e honorários advocatícios decorrentes do descumprimento deste contrato, ressalvadas as "
                "hipóteses de negligência exclusiva ou conduta dolosa da parte prejudicada."
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 10 - DA LGPD", section_style),
        Paragraph(
            (
                "10.1. Ambas as partes comprometem-se a respeitar a privacidade e os dados pessoais coletados e tratados no âmbito deste "
                "contrato, em conformidade com a Lei Geral de Proteção de Dados - LGPD (Lei nº 13.709/2018).<br/>"
                "10.2. A CONTRATADA autoriza a CONTRATANTE a utilizar seus dados pessoais apenas quando necessário e exclusivamente para "
                "fins de envio de produtos e comunicação relacionada ao objeto deste contrato.<br/>"
                "10.3. A CONTRATANTE declara que utilizará os conteúdos criados exclusivamente para os fins contratados, abstendo-se de "
                "qualquer uso ilícito ou que viole os direitos da CONTRATADA."
            ),
            body_style,
        ),
        Paragraph("CLÁUSULA 11 - DAS DISPOSIÇÕES GERAIS E DO FORO", section_style),
        Paragraph(
            (
                "11.1. Qualquer alteração neste contrato somente terá validade se realizada por meio de termo aditivo por escrito, "
                "assinado por ambas as partes.<br/>"
                "11.2. Para dirimir quaisquer controvérsias oriundas deste contrato, as partes elegem o foro da Comarca de Salvador, "
                "Estado da Bahia, com renúncia de qualquer outro, por mais privilegiado que seja."
            ),
            body_style,
        ),
        Spacer(1, 20),
        Paragraph(
            "E, por estarem justas e contratadas, firmam o presente instrumento em 02 (duas) vias de igual teor e forma, para que produza seus efeitos legais.",
            body_style,
        ),
        Paragraph(f"Salvador/BA, {payload['close_date_text']}.", body_style),
        Spacer(1, 26),
        Paragraph("__________________________________", signature_style),
        Paragraph(f"{payload['creator_name']}<br/>CNPJ nº {payload['creator_cnpj']}", signature_style),
        Spacer(1, 12),
        Paragraph("__________________________________", signature_style),
        Paragraph(f"{payload['company_name']}<br/>CNPJ nº {payload['company_cnpj']}", signature_style),
    ]

    document.build(story)
    return buffer.getvalue()


def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        try:
            send_signup_confirmation_email(user, request)
            messages.success(request, "Conta criada com sucesso. Enviamos um email de confirmação para você.")
        except Exception:
            messages.warning(request, "Conta criada com sucesso, mas não foi possível enviar o email de confirmação agora.")
        return redirect("dashboard")

    return render(request, "registration/signup.html", {"form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")


def _workspace(request: HttpRequest):
    return get_or_create_workspace_for_user(request.user)


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month")
    context = shell_context(
        "dashboard",
        workspace,
        "Dashboard",
        "Visão executiva do negócio UGC.",
        user=request.user,
        month_filter=month_filter,
    )
    context.update(dashboard_snapshot(workspace, month_filter))
    return render(request, "studio/dashboard.html", context)


@login_required
def prospection(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month")
    search = request.GET.get("search")
    tab = request.GET.get("tab") or "pipeline"
    if tab not in {"pipeline", "banco", "logica"}:
        tab = "pipeline"
    context = shell_context(
        "prospection",
        workspace,
        "Prospecção",
        "Leads, follow-ups e negociações em aberto.",
        user=request.user,
        action_label="Novo lead",
        action_url="prospect_create",
        month_filter=month_filter,
    )
    context.update(prospection_snapshot(workspace, month_filter, search=search))
    context["active_tab"] = tab

    # Paginação do Banco de Marcas (estilo Gmail: 20 por página, com ‹ ›)
    banco_paginator = Paginator(context.get("archived_rows", []), 20)
    banco_page = banco_paginator.get_page(request.GET.get("page"))
    context["archived_rows"] = banco_page.object_list
    context["banco_page"] = banco_page

    return render(request, "studio/prospection.html", context)


@login_required
def prospect_export(request: HttpRequest) -> HttpResponse:
    """Exporta o Banco de Marcas em CSV (compatível com Excel)."""
    import csv
    from io import StringIO
    from .constants import PROSPECT_ARCHIVE_LABELS
    workspace = _workspace(request)
    rows = (
        Prospect.objects.filter(workspace=workspace)
        .exclude(archive_reason="")
        .select_related("niche")
        .order_by("-archived_at")
    )
    buffer = StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Marca", "Instagram", "Nicho", "Canal", "Último contato", "Status", "Arquivado em"])
    for item in rows:
        writer.writerow([
            item.company,
            item.instagram,
            item.niche.name if item.niche_id else "",
            item.channel,
            item.contact_date.strftime("%d/%m/%Y") if item.contact_date else "",
            PROSPECT_ARCHIVE_LABELS.get(item.archive_reason, ""),
            item.archived_at.strftime("%d/%m/%Y") if item.archived_at else "",
        ])
    response = HttpResponse(buffer.getvalue().encode("utf-8-sig"), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="banco-de-marcas.csv"'
    return response


@login_required
@require_POST
def follow_up_confirm(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    added_keys = confirm_follow_up_companies(workspace, request.POST.getlist("company_keys"))
    if added_keys:
        messages.success(request, "Marcas enviadas para o follow-up.")
    return redirect(f"{reverse('prospection')}#follow-up-column")


@login_required
@require_POST
def follow_up_dismiss(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    dismiss_follow_up_company(workspace, request.POST.get("company_key", ""))
    return redirect("prospection")


@login_required
@require_POST
def follow_up_start_prospection(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    prospect = start_follow_up_prospection(workspace, request.POST.get("company_key", ""))
    if prospect:
        messages.success(request, f"{prospect.company} voltou para Prospecção.")
    return redirect("prospection")


@login_required
def jobs(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month")
    context = shell_context(
        "jobs",
        workspace,
        "Trabalhos",
        "Trabalhos assinados e entregas em andamento.",
        user=request.user,
        action_label="Novo trabalho",
        action_url="project_create",
        month_filter=month_filter,
    )
    context.update(
        jobs_snapshot_filtered(
            workspace,
            service_category_filter=request.GET.get("service_category"),
            progress_filter=request.GET.get("progress"),
            niche_filter=request.GET.get("niche"),
            search=request.GET.get("search"),
            month_filter=month_filter,
        )
    )
    return render(request, "studio/jobs.html", context)


@login_required
def finance(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month") or request.POST.get("month")
    editing_entry_id = request.POST.get("outgoing_entry_id") if request.method == "POST" else request.GET.get("edit")
    editing_entry = None
    if editing_entry_id:
        if not editing_entry_id.isdigit():
            raise Http404("Saida nao encontrada.")
        editing_entry = get_object_or_404(
            FinanceEntry.objects.filter(workspace=workspace, kind=FinanceEntry.KIND_OUTGOING),
            pk=int(editing_entry_id),
        )
    editing_fixed_cost_id = request.POST.get("fixed_cost_id") if request.method == "POST" else request.GET.get("edit_fixed_cost")
    editing_fixed_cost = None
    if editing_fixed_cost_id:
        if not editing_fixed_cost_id.isdigit():
            raise Http404("Custo fixo nao encontrado.")
        editing_fixed_cost = get_object_or_404(
            FixedCost.objects.filter(workspace=workspace),
            pk=int(editing_fixed_cost_id),
        )
    editing_cash_box_id = request.POST.get("cash_box_id") if request.method == "POST" else request.GET.get("edit_cash_box")
    editing_cash_box = None
    if editing_cash_box_id:
        if not editing_cash_box_id.isdigit():
            raise Http404("Caixinha nao encontrada.")
        editing_cash_box = get_object_or_404(
            CashBox.objects.filter(workspace=workspace),
            pk=int(editing_cash_box_id),
        )
    editing_cash_box_rule_key = request.POST.get("cash_box_rule") if request.method == "POST" else request.GET.get("edit_cash_box_rule")
    if editing_cash_box_rule_key and editing_cash_box_rule_key not in CASH_BOX_ALLOCATION_SETTINGS:
        raise Http404("Caixinha nao encontrada.")
    add_fixed_cost_kind = request.GET.get("add_fixed_cost")
    if add_fixed_cost_kind not in {FixedCost.KIND_TOOL, FixedCost.KIND_COLLABORATOR}:
        add_fixed_cost_kind = None
    add_cash_box = request.GET.get("add_cash_box") == "1"
    workspace_settings = settings_map(workspace)
    selected_month = parse_month_value(month_filter) if month_filter and month_filter != "all" else None
    today = date.today()
    initial_date = (
        today
        if selected_month is None or (selected_month.year == today.year and selected_month.month == today.month)
        else selected_month
    )
    outgoing_form_kwargs = {"prefix": "outgoing", "workspace": workspace}
    if editing_entry is not None:
        outgoing_form_kwargs["instance"] = editing_entry
    else:
        outgoing_form_kwargs["initial"] = {"occurred_on": initial_date}
    outgoing_form = FinanceEntryForm(**outgoing_form_kwargs)

    fixed_cost_form_kwargs = {"prefix": "fixed_cost"}
    if editing_fixed_cost is not None:
        fixed_cost_form_kwargs["instance"] = editing_fixed_cost
    elif add_fixed_cost_kind is not None:
        fixed_cost_form_kwargs["initial"] = {
            "kind": add_fixed_cost_kind,
            "recurrence": FixedCost.RECURRENCE_MONTHLY,
            "due_day": 1,
            "due_month": 1,
        }
    else:
        fixed_cost_form_kwargs["initial"] = {
            "kind": FixedCost.KIND_TOOL,
            "recurrence": FixedCost.RECURRENCE_MONTHLY,
            "due_day": 1,
            "due_month": 1,
        }
    fixed_cost_form = FixedCostForm(**fixed_cost_form_kwargs)
    fixed_cost_modal_open = editing_fixed_cost is not None or add_fixed_cost_kind is not None
    cash_box_form_kwargs = {"prefix": "cash_box", "workspace": workspace}
    if editing_cash_box is not None:
        cash_box_form_kwargs["instance"] = editing_cash_box
    cash_box_form = CashBoxForm(**cash_box_form_kwargs)
    cash_box_modal_open = editing_cash_box is not None or add_cash_box
    cash_box_rule_form = CashBoxAllocationForm(
        box_key=editing_cash_box_rule_key or "reserve",
        settings_values=workspace_settings,
    )
    cash_box_rule_modal_open = editing_cash_box_rule_key is not None

    if request.method == "POST":
        action = request.POST.get("finance_action")
        if action == "outgoing":
            outgoing_form = FinanceEntryForm(request.POST, **outgoing_form_kwargs)
            if outgoing_form.is_valid():
                entry = outgoing_form.save(commit=False)
                entry.workspace = workspace
                entry.kind = FinanceEntry.KIND_OUTGOING
                entry.save()
                messages.success(request, "Saída atualizada." if editing_entry is not None else "Saída registrada.")
                redirect_url = reverse("finance")
                if month_filter:
                    redirect_url = f"{redirect_url}?month={month_filter}"
                return redirect(redirect_url)
        elif action == "outgoing_delete":
            delete_entry_id = request.POST.get("outgoing_entry_id")
            if delete_entry_id and delete_entry_id.isdigit():
                entry_to_delete = FinanceEntry.objects.filter(
                    workspace=workspace,
                    kind=FinanceEntry.KIND_OUTGOING,
                    pk=int(delete_entry_id),
                ).first()
                if entry_to_delete is not None:
                    entry_to_delete.delete()
                    messages.success(request, "Saída removida.")
            redirect_url = reverse("finance")
            if month_filter:
                redirect_url = f"{redirect_url}?month={month_filter}"
            return redirect(redirect_url)
        elif action == "fixed_cost":
            fixed_cost_form = FixedCostForm(request.POST, **fixed_cost_form_kwargs)
            if fixed_cost_form.is_valid():
                cost = fixed_cost_form.save(commit=False)
                cost.workspace = workspace
                cost.save()
                messages.success(request, "Custo fixo atualizado." if editing_fixed_cost is not None else "Custo fixo adicionado.")
                redirect_url = reverse("finance")
                if month_filter:
                    redirect_url = f"{redirect_url}?month={month_filter}"
                return redirect(redirect_url)
            fixed_cost_modal_open = True
        elif action == "fixed_cost_delete" and editing_fixed_cost is not None:
            editing_fixed_cost.delete()
            messages.success(request, "Custo fixo removido.")
            redirect_url = reverse("finance")
            if month_filter:
                redirect_url = f"{redirect_url}?month={month_filter}"
            return redirect(redirect_url)
        elif action == "cash_box":
            cash_box_form = CashBoxForm(request.POST, **cash_box_form_kwargs)
            if cash_box_form.is_valid():
                cash_box = cash_box_form.save(commit=False)
                cash_box.workspace = workspace
                cash_box.save()
                messages.success(request, "Caixinha atualizada." if editing_cash_box is not None else "Caixinha criada.")
                redirect_url = reverse("finance")
                if month_filter:
                    redirect_url = f"{redirect_url}?month={month_filter}"
                return redirect(redirect_url)
            cash_box_modal_open = True
        elif action == "cash_box_delete" and editing_cash_box is not None:
            editing_cash_box.delete()
            messages.success(request, "Caixinha removida.")
            redirect_url = reverse("finance")
            if month_filter:
                redirect_url = f"{redirect_url}?month={month_filter}"
            return redirect(redirect_url)
        elif action == "cash_box_rule" and editing_cash_box_rule_key is not None:
            cash_box_rule_form = CashBoxAllocationForm(
                request.POST,
                box_key=editing_cash_box_rule_key,
                settings_values=workspace_settings,
            )
            if cash_box_rule_form.is_valid():
                box_config = CASH_BOX_ALLOCATION_SETTINGS[editing_cash_box_rule_key]
                save_settings(
                    workspace,
                    {box_config["key"]: cash_box_rule_form.cleaned_data["allocation_percentage"]},
                )
                messages.success(request, "Caixinha atualizada.")
                redirect_url = reverse("finance")
                if month_filter:
                    redirect_url = f"{redirect_url}?month={month_filter}"
                return redirect(redirect_url)
            cash_box_rule_modal_open = True

    context = shell_context(
        "finance",
        workspace,
        "Financeiro",
        "Fluxo de caixa, despesas e saldo de recebíveis.",
        user=request.user,
        month_filter=month_filter,
    )
    context.update(finance_snapshot(workspace, month_filter))
    context.update(
        {
            "outgoing_form": outgoing_form,
            "outgoing_form_title": "Editar saída" if editing_entry is not None else "Registrar saída",
            "outgoing_form_submit_label": "Salvar alteração" if editing_entry is not None else "Salvar saída",
            "outgoing_form_description": (
                "Corrija valor, data ou descrição desta saída."
                if editing_entry is not None
                else "Use para custos de produção, ferramentas ou investimentos."
            ),
            "editing_entry": editing_entry,
            "fixed_cost_form": fixed_cost_form,
            "editing_fixed_cost": editing_fixed_cost,
            "fixed_cost_modal_open": fixed_cost_modal_open,
            "fixed_cost_form_title": "Editar custo fixo" if editing_fixed_cost is not None else "Adicionar custo fixo",
            "fixed_cost_form_submit_label": "Salvar alteração" if editing_fixed_cost is not None else "Salvar custo fixo",
            "cash_box_form": cash_box_form,
            "editing_cash_box": editing_cash_box,
            "cash_box_modal_open": cash_box_modal_open,
            "cash_box_form_title": "Editar caixinha" if editing_cash_box is not None else "Nova caixinha",
            "cash_box_form_submit_label": "Salvar alteração" if editing_cash_box is not None else "Criar caixinha",
            "cash_box_rule_form": cash_box_rule_form,
            "cash_box_rule_modal_open": cash_box_rule_modal_open,
            "cash_box_rule_key": editing_cash_box_rule_key,
            "cash_box_rule_title": (
                f"Editar {CASH_BOX_ALLOCATION_SETTINGS[editing_cash_box_rule_key]['label']}"
                if editing_cash_box_rule_key is not None
                else "Editar caixinha"
            ),
            "finance_cancel_url": f"{reverse('finance')}?month={month_filter}" if month_filter else reverse("finance"),
        }
    )
    return render(request, "studio/finance.html", context)


@login_required
def distribution(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context(
        "distribution",
        workspace,
        "Distribuição",
        "Controle onde cada material vai rodar entre orgânico e ads.",
        user=request.user,
    )
    context.update(distribution_snapshot(workspace))
    return render(request, "studio/distribution.html", context)


@login_required
def legal(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    context = shell_context(
        "legal",
        workspace,
        "Jurídico",
        "Acompanhe o direito de uso de imagem e os vencimentos de licenciamento.",
        user=request.user,
    )
    context.update(legal_snapshot(workspace, request.user))
    return render(request, "studio/legal.html", context)


@login_required
def legal_contract_preview(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project.objects.filter(workspace=workspace), pk=pk)
    if request.method == "POST" and not _save_contract_brand_data(project, request.POST):
        messages.error(request, "Preencha os dados da marca para visualizar o contrato.")
        return redirect("legal")

    payload = _project_contract_payload(workspace, request.user, project)
    context = shell_context(
        "legal",
        workspace,
        "Pré-visualizar contrato",
        "Revise os dados e ajuste cláusulas antes de baixar o PDF.",
        user=request.user,
    )
    context.update(
        {
            "project": project,
            "payload": payload,
            "intro_paragraphs": [_contract_html_to_editor_text(item) for item in _contract_intro_paragraphs(payload)],
            "clauses": _contract_clauses_for_editor(payload),
            "cancel_url": reverse("legal"),
        }
    )
    return render(request, "studio/legal_contract_preview.html", context)


@login_required
def legal_contract_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project.objects.filter(workspace=workspace), pk=pk)
    if request.method == "POST":
        if not _save_contract_brand_data(project, request.POST):
            messages.error(request, "Preencha os dados da marca para gerar o contrato.")
            return redirect("legal")
    payload = _project_contract_payload(workspace, request.user, project)
    clauses = _contract_clauses_from_post(payload, request.POST) if request.method == "POST" else _contract_clauses(payload)
    if project.contract_status != Project.CONTRACT_STATUS_GENERATED:
        project.contract_status = Project.CONTRACT_STATUS_GENERATED
        project.save(update_fields=["contract_status", "updated_at"])
    pdf_content = _build_contract_pdf_from_clauses(workspace, request.user, project, clauses)
    filename = slugify(f"contrato-{project.company}-{project.service_category_name}") or f"contrato-{project.pk}"
    response = HttpResponse(pdf_content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response


@login_required
@require_POST
def legal_contract_dismiss(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project.objects.filter(workspace=workspace), pk=pk)
    project.contract_status = Project.CONTRACT_STATUS_DISMISSED
    project.save(update_fields=["contract_status", "updated_at"])
    messages.success(request, f"Contrato dispensado para {project.company}.")
    return redirect("legal")


@login_required
def reports(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    month_filter = request.GET.get("month")
    service_type_filter = request.GET.get("type") or None
    context = shell_context(
        "reports",
        workspace,
        "Relatórios",
        "Indicadores estratégicos do negócio.",
        user=request.user,
        month_filter=month_filter,
    )
    context.update(reports_snapshot(workspace, month_filter, service_type_filter=service_type_filter))
    return render(request, "studio/reports.html", context)


@login_required
def settings(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    settings_form = WorkspaceSettingsForm(
        request.POST if request.method == "POST" and request.POST.get("settings_action") == "preferences" else None,
        settings_values=settings_map(workspace),
    )
    service_category_form = ManagedOptionForm(
        request.POST if request.method == "POST" and request.POST.get("settings_action") == "add_service_category" else None,
        label="Nova categoria de serviço",
        help_text="Cadastre aqui as categorias de serviço para selecionar nos trabalhos.",
        prefix="service_category",
    )

    if request.method == "POST":
        action = request.POST.get("settings_action")
        if action == "preferences" and settings_form.is_valid():
            save_settings(workspace, settings_form.cleaned_data)
            messages.success(request, "Configurações atualizadas.")
            return redirect("settings")
        if action == "add_service_category" and service_category_form.is_valid():
            name = service_category_form.cleaned_data["name"].strip()
            service_category, created = ServiceCategory.objects.get_or_create(workspace=workspace, name=name)
            messages.success(request, "Categoria de serviço cadastrada." if created else "Essa categoria já existe.")
            return redirect("settings")
        if action == "delete_service_category":
            service_category = get_object_or_404(ServiceCategory, pk=request.POST.get("service_category_id"), workspace=workspace)
            if service_category.projects.exists():
                messages.warning(request, "Essa categoria já foi usada em trabalhos e não pode mais ser excluída.")
            else:
                service_category.delete()
                messages.success(request, "Categoria de serviço removida.")
            return redirect("settings")

    context = shell_context("settings", workspace, "Configurações", "Preferências visuais e operacionais.", user=request.user)
    context.update(
        {
            "form": settings_form,
            "service_category_form": service_category_form,
            "managed_service_categories": ServiceCategory.objects.filter(workspace=workspace).annotate(usage_count=Count("projects")).order_by("name"),
        }
    )
    return render(request, "studio/settings.html", context)


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    membership = request.user.memberships.select_related("workspace").filter(workspace=workspace).first()
    business_form = WorkspaceBusinessForm(instance=workspace)

    if request.method == "POST":
        action = request.POST.get("profile_action")
        if action == "business":
            business_form = WorkspaceBusinessForm(request.POST, instance=workspace)
            if business_form.is_valid():
                business_form.save()
                messages.success(request, "Dados empresariais atualizados.")
                return redirect("profile")
        elif action == "photo":
            return redirect("profile")

    context = shell_context("profile", workspace, "Perfil", "Dados cadastrais da conta e do workspace ativo.", user=request.user)
    context.update(
        {
            "membership": membership,
            "business_form": business_form,
            "profile_sections": [
                {
                    "title": "Conta",
                    "items": [
                        {"label": "Usuário", "value": request.user.username or "-"},
                        {"label": "Email", "value": request.user.email or "-"},
                        {"label": "Data de cadastro", "value": timezone.localtime(request.user.date_joined).strftime("%d/%m/%Y")},
                        {
                            "label": "Último acesso",
                            "value": timezone.localtime(request.user.last_login).strftime("%d/%m/%Y %H:%M") if request.user.last_login else "Primeiro acesso",
                        },
                    ],
                },
                {
                    "title": "Workspace",
                    "items": [
                        {"label": "Workspace ativo", "value": workspace.name},
                    ],
                },
            ]
        }
    )
    return render(request, "studio/profile.html", context)


@login_required
def prospect_create(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    form = ProspectForm(request.POST or None, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        prospect = form.save(commit=False)
        prospect.workspace = workspace
        prospect.save()
        messages.success(request, "Lead salvo com sucesso.")
        return redirect("prospection")

    context = shell_context("prospection", workspace, "Novo lead", "Registre uma oportunidade comercial.", user=request.user)
    context.update({"form": form, "form_title": "Lead / prospecção", "cancel_url": "prospection"})
    return render(request, "studio/prospect_form.html", context)


@login_required
def prospect_edit(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    form = ProspectForm(request.POST or None, instance=prospect, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Lead atualizado.")
        return redirect("prospection")

    context = shell_context("prospection", workspace, "Editar lead", "Ajuste os dados da oportunidade.", user=request.user)
    context.update({"form": form, "form_title": "Lead / prospecção", "cancel_url": "prospection"})
    return render(request, "studio/prospect_form.html", context)


@login_required
@require_POST
def prospect_delete(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    prospect.delete()
    messages.success(request, "Lead removido.")
    return redirect("prospection")


@login_required
def prospect_convert(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    initial = {
        "company": prospect.company,
        "closing_source": "Prospecção",
        "niche": prospect.niche,
        "service_category": None,
        "stage": "Fechado",
        "status": "Briefing",
        "received_value": 0,
        "deliverables_count": 3,
        "progress": 15,
        "meeting_scheduled": prospect.meeting_scheduled,
        "meeting_date": prospect.meeting_date,
        "note": prospect.note,
        "content_distribution": "",
        "image_license_term_days": None,
    }
    form = ProjectForm(request.POST or None, initial=initial, workspace=workspace)
    has_installments_post = request.method == "POST" and _installments_payload_present(request)
    installments_formset = ProjectInstallmentFormSet(
        request.POST if has_installments_post else None,
        instance=Project(),
        prefix="installments",
    )
    formset_ok = installments_formset.is_valid() if has_installments_post else True
    if request.method == "POST" and form.is_valid() and formset_ok:
        project = form.save(commit=False)
        project.workspace = workspace
        project.save()
        if has_installments_post and form.cleaned_data.get("has_installments") == HAS_INSTALLMENTS_YES:
            installments_formset.instance = project
            _save_installments_formset(installments_formset, project, workspace)
        _sync_auto_monthly_installments(
            project,
            workspace,
            has_installments_yes=(form.cleaned_data.get("has_installments") == HAS_INSTALLMENTS_YES),
        )
        from django.utils import timezone as _tz
        prospect.stage = "Fechado"
        prospect.archive_reason = "fechado"
        prospect.archived_at = _tz.now()
        prospect.save(update_fields=["stage", "archive_reason", "archived_at", "updated_at"])
        messages.success(request, "Lead convertido em trabalho.")
        if project.content_distribution == "Ads" and project.image_license_term_days:
            messages.info(request, "Direito de uso de imagem ativado. O Jurídico vai avisar no vencimento.")
        return redirect("jobs")

    context = shell_context("prospection", workspace, "Converter lead", "Transforme a oportunidade em trabalho.", user=request.user)
    context.update({
        "form": form,
        "form_title": "Trabalho",
        "cancel_url": "prospection",
        "installments_formset": installments_formset,
    })
    return render(request, "studio/project_form.html", context)


@login_required
@require_POST
def installment_confirm(request: HttpRequest, pk: int) -> HttpResponse:
    """Marca uma parcela como recebida na data informada."""
    from datetime import date as _date
    workspace = _workspace(request)
    installment = get_object_or_404(ProjectInstallment, pk=pk, workspace=workspace)
    raw_date = (request.POST.get("paid_on") or "").strip()
    try:
        paid_on = _date.fromisoformat(raw_date) if raw_date else _date.today()
    except ValueError:
        paid_on = _date.today()
    installment.paid = True
    installment.paid_on = paid_on
    installment.save(update_fields=["paid", "paid_on", "updated_at"])
    messages.success(request, f"Recebimento confirmado em {paid_on.strftime('%d/%m/%Y')}.")
    next_url = request.POST.get("next") or reverse("finance")
    return redirect(next_url)


@login_required
@require_POST
def prospect_archive(request: HttpRequest, pk: int) -> HttpResponse:
    """Arquiva um lead no Banco de Marcas com motivo."""
    from django.utils import timezone as _tz
    from .constants import PROSPECT_ARCHIVE_LABELS
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    reason = (request.POST.get("reason") or "").strip()
    if reason not in PROSPECT_ARCHIVE_LABELS:
        messages.error(request, "Motivo inválido.")
        return redirect("prospection")
    prospect.archive_reason = reason
    prospect.archived_at = _tz.now()
    if reason == "fechado":
        prospect.stage = "Fechado"
    prospect.save(update_fields=["stage", "archive_reason", "archived_at", "updated_at"])
    messages.success(request, f"Lead movido para Banco de Marcas como “{PROSPECT_ARCHIVE_LABELS[reason]}”.")
    return redirect(request.POST.get("next") or "prospection")


@login_required
@require_POST
def prospect_reactivate(request: HttpRequest, pk: int) -> HttpResponse:
    """Tira o lead do Banco de Marcas e devolve pro pipeline em Prospecção."""
    from django.utils import timezone as _tz
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    prospect.archive_reason = ""
    prospect.archived_at = None
    prospect.stage = "Prospeccao"
    prospect.last_activity_at = _tz.now()
    prospect.save(update_fields=["stage", "archive_reason", "archived_at", "last_activity_at", "updated_at"])
    messages.success(request, "Marca reativada no pipeline.")
    return redirect(f"{reverse('prospection')}?tab=banco")


@login_required
@require_POST
def prospect_set_stage(request: HttpRequest, pk: int) -> HttpResponse:
    """Move um lead pra outra etapa do pipeline (ex.: Rascunho → Prospecção).
    Se vinha do Banco de Marcas (archive_reason setado), reativa também."""
    from django.utils import timezone as _tz
    workspace = _workspace(request)
    prospect = get_object_or_404(Prospect, pk=pk, workspace=workspace)
    stage = (request.POST.get("stage") or "").strip()
    valid_stages = {"Rascunho", "Prospeccao", "Aguardando retorno", "Follow-up", "Negociacao"}
    if stage not in valid_stages:
        messages.error(request, "Etapa inválida.")
        return redirect("prospection")
    prospect.stage = stage
    prospect.last_activity_at = _tz.now()
    prospect.archive_reason = ""
    prospect.archived_at = None
    prospect.save(update_fields=["stage", "archive_reason", "archived_at", "last_activity_at", "updated_at"])
    return redirect("prospection")


def _save_installments_formset(formset, project, workspace) -> None:
    """Persiste as parcelas vindas do formset, garantindo workspace correto."""
    instances = formset.save(commit=False)
    for instance in instances:
        instance.project = project
        instance.workspace = workspace
        instance.save()
    for obj in formset.deleted_objects:
        obj.delete()


def _installments_payload_present(request: HttpRequest) -> bool:
    """Detecta se o POST veio com o management form do formset de parcelas.
    Permite que callers (ex.: testes legados, prospect_convert) postem o
    form sem o bloco de parcelas sem quebrar a validação."""
    return "installments-TOTAL_FORMS" in request.POST


def _shift_month_start(month_start: date, months: int) -> date:
    month_index = (month_start.year * 12) + (month_start.month - 1) + months
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _repeat_installment_date(source_due_date: date, target_month: date) -> date:
    last_day = calendar.monthrange(target_month.year, target_month.month)[1]
    return date(target_month.year, target_month.month, min(source_due_date.day, last_day))


def _sync_repeating_manual_installments(project: Project, workspace) -> None:
    duration = int(project.contract_duration_months or 0)
    if duration <= 1:
        return

    installments = list(project.installments.all().order_by("due_date", "pk"))
    if not installments:
        return

    base_month = min(item.due_date.replace(day=1) for item in installments)
    base_pattern = [
        item
        for item in installments
        if item.due_date.replace(day=1) == base_month and Decimal(item.amount or 0) > 0
    ]
    if not base_pattern:
        return

    occupied_months = {item.due_date.replace(day=1) for item in installments}
    for month_offset in range(1, duration):
        target_month = _shift_month_start(base_month, month_offset)
        if target_month in occupied_months:
            continue
        for source in base_pattern:
            ProjectInstallment.objects.create(
                project=project,
                workspace=workspace,
                due_date=_repeat_installment_date(source.due_date, target_month),
                amount=source.amount,
                paid=False,
                paid_on=None,
            )


def _sync_auto_monthly_installments(
    project: Project, workspace, has_installments_yes: bool = True
) -> None:
    """Para tipos de contrato plurimensais (Publicidade, Social Media,
    Consultoria de Marketing) com duração maior que 1 mês, gera N parcelas
    com mesmo dia do mês baseado em payment_due_date.

    O valor de cada parcela depende do tipo:
    - Publicidade recorrente: total_value é o valor mensal do contrato.
    - Contratos recorrentes: total_value é "Valor mensal do contrato" → usa
      como está (parcela = total_value).

    Contratos recorrentes (Social Media / Consultoria) sem parcelas manuais
    usam mensalidades virtuais no financeiro. O bloco de parcelas fica livre
    para pagamentos divididos em datas/valores especificos."""
    if project.service_type not in AUTO_MONTHLY_INSTALLMENT_TYPES:
        return
    duration = int(project.contract_duration_months or 0)
    base_date = project.payment_due_date or project.close_date
    is_publicidade = project.service_type == "publicidade"
    if not is_publicidade:
        if has_installments_yes:
            _sync_repeating_manual_installments(project, workspace)
        else:
            project.installments.all().delete()
        return
    project.installments.all().delete()
    should_generate = duration > 1 and base_date is not None
    if not should_generate:
        return
    total = Decimal(project.total_value or 0)
    amount_per_month = total.quantize(Decimal("0.01"))
    base_day = base_date.day
    for index in range(duration):
        month_index = base_date.month - 1 + index
        year = base_date.year + month_index // 12
        month = month_index % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        installment_date = date(year, month, min(base_day, last_day))
        ProjectInstallment.objects.create(
            project=project,
            workspace=workspace,
            due_date=installment_date,
            amount=amount_per_month,
            paid=False,
        )


@login_required
def project_create(request: HttpRequest) -> HttpResponse:
    workspace = _workspace(request)
    form = ProjectForm(request.POST or None, workspace=workspace)
    has_installments_post = request.method == "POST" and _installments_payload_present(request)
    installments_formset = ProjectInstallmentFormSet(
        request.POST if has_installments_post else None,
        instance=Project(),
        prefix="installments",
    )
    formset_ok = installments_formset.is_valid() if has_installments_post else True
    if request.method == "POST" and form.is_valid() and formset_ok:
        project = form.save(commit=False)
        project.workspace = workspace
        project.save()
        if has_installments_post and form.cleaned_data.get("has_installments") == HAS_INSTALLMENTS_YES:
            installments_formset.instance = project
            _save_installments_formset(installments_formset, project, workspace)
        _sync_auto_monthly_installments(
            project,
            workspace,
            has_installments_yes=(form.cleaned_data.get("has_installments") == HAS_INSTALLMENTS_YES),
        )
        messages.success(request, "Trabalho salvo com sucesso.")
        if project.content_distribution == "Ads" and project.image_license_term_days:
            messages.info(request, "Direito de uso de imagem ativado. O Jurídico vai avisar no vencimento.")
        return redirect("jobs")

    context = shell_context("jobs", workspace, "Novo trabalho", "Cadastre um novo trabalho.", user=request.user)
    context.update({
        "form": form,
        "form_title": "Trabalho",
        "cancel_url": "jobs",
        "installments_formset": installments_formset,
    })
    return render(request, "studio/project_form.html", context)


@login_required
def project_edit(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project, pk=pk, workspace=workspace)
    form = ProjectForm(request.POST or None, instance=project, workspace=workspace)
    has_installments_post = request.method == "POST" and _installments_payload_present(request)
    installments_formset = ProjectInstallmentFormSet(
        request.POST if has_installments_post else None,
        instance=project,
        prefix="installments",
    )
    formset_ok = installments_formset.is_valid() if has_installments_post else True
    if request.method == "POST" and form.is_valid() and formset_ok:
        project = form.save()
        if has_installments_post and form.cleaned_data.get("has_installments") == HAS_INSTALLMENTS_YES:
            _save_installments_formset(installments_formset, project, workspace)
        elif (
            form.cleaned_data.get("has_installments") != HAS_INSTALLMENTS_YES
            and project.service_type not in AUTO_MONTHLY_INSTALLMENT_TYPES
        ):
            project.installments.all().delete()
        _sync_auto_monthly_installments(
            project,
            workspace,
            has_installments_yes=(form.cleaned_data.get("has_installments") == HAS_INSTALLMENTS_YES),
        )
        messages.success(request, "Trabalho atualizado.")
        if project.content_distribution == "Ads" and project.image_license_term_days:
            messages.info(request, "Direito de uso de imagem ativado. O Jurídico vai avisar no vencimento.")
        return redirect("jobs")

    context = shell_context("jobs", workspace, "Editar trabalho", "Ajuste valores, datas e status.", user=request.user)
    context.update({
        "form": form,
        "form_title": "Trabalho",
        "cancel_url": "jobs",
        "installments_formset": installments_formset,
    })
    return render(request, "studio/project_form.html", context)


@login_required
@require_POST
def project_delete(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project, pk=pk, workspace=workspace)
    project.delete()
    messages.success(request, "Trabalho removido.")
    return redirect("jobs")


@login_required
@require_POST
def project_mark_delivered(request: HttpRequest, pk: int) -> HttpResponse:
    workspace = _workspace(request)
    project = get_object_or_404(Project, pk=pk, workspace=workspace)
    project.stage = "Entregue"
    project.status = "Concluído"
    project.progress = 100
    project.save(update_fields=["stage", "status", "progress", "updated_at"])
    messages.success(request, f"{project.company} marcado como entregue.")
    return redirect("jobs")
