"""Views do checkout Mercado Pago (Payment Brick)."""
from __future__ import annotations

import json
import logging
import secrets
import string
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .checkout import CheckoutProduct, get_product
from .emails import send_access_code_email
from .models import AccessCode, Purchase, normalize_access_code

logger = logging.getLogger(__name__)


CHECKOUT_ALLOWED_ORIGINS = {
    "https://thecreatorsclub.com.br",
    "https://www.thecreatorsclub.com.br",
}
CHECKOUT_PUBLIC_BASE = "https://thecreatorsclub.com.br"


def _cors_headers(request: HttpRequest) -> dict:
    origin = request.headers.get("Origin", "")
    if origin in CHECKOUT_ALLOWED_ORIGINS:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Vary": "Origin",
        }
    return {}


def _json(request: HttpRequest, data: dict, status: int = 200) -> JsonResponse:
    response = JsonResponse(data, status=status)
    for key, value in _cors_headers(request).items():
        response[key] = value
    return response


# ---------- Helpers ----------

def _mp_sdk():
    """Importa o SDK do Mercado Pago só quando precisa pra não derrubar a
    aplicação se a dependência ainda não estiver instalada em dev."""
    import mercadopago  # type: ignore
    return mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)


def _absolute_url(request: HttpRequest, path: str) -> str:
    base = (settings.CHECKOUT_BASE_URL or "").rstrip("/")
    if base:
        return f"{base}{path}"
    return request.build_absolute_uri(path)


def _generate_access_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(10))
        if not AccessCode.objects.filter(code=candidate).exists():
            return candidate


def _parse_mp_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # MP usa ISO 8601 com offset tipo "2026-05-22T11:30:00.000-03:00"
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# ---------- Views públicas ----------

@require_GET
def checkout_page(request: HttpRequest, product_key: str) -> HttpResponse:
    product = get_product(product_key)
    if product is None:
        raise Http404("Produto não encontrado.")
    if not settings.MERCADO_PAGO_PUBLIC_KEY:
        return render(
            request,
            "checkout/checkout_unavailable.html",
            {"product": product},
            status=503,
        )
    context = {
        "product": product,
        "mp_public_key": settings.MERCADO_PAGO_PUBLIC_KEY,
        "preference_endpoint": reverse("checkout_preference"),
        "success_url": reverse("checkout_success"),
        "price_text": f"R$ {product.price:.2f}".replace(".", ","),
    }
    return render(request, "checkout/checkout_page.html", context)


@csrf_exempt
def checkout_preference(request: HttpRequest) -> JsonResponse:
    if request.method == "OPTIONS":
        return _json(request, {})
    if request.method != "POST":
        return _json(request, {"error": "method_not_allowed"}, status=405)
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return _json(request, {"error": "invalid_payload"}, status=400)

    product_key = (payload.get("product_key") or "").strip()
    product = get_product(product_key)
    if product is None:
        return _json(request, {"error": "unknown_product"}, status=404)

    customer_name = (payload.get("customer_name") or "").strip()
    customer_email = (payload.get("customer_email") or "").strip().lower()
    customer_cpf = (payload.get("customer_cpf") or "").strip()
    customer_phone = (payload.get("customer_phone") or "").strip()

    if not customer_name or not customer_email:
        return _json(request, {"error": "missing_customer"}, status=400)
    if not settings.MERCADO_PAGO_ACCESS_TOKEN:
        return _json(request, {"error": "mp_not_configured"}, status=503)

    purchase = Purchase.objects.create(
        product_key=product.key,
        product_name=product.name,
        amount=product.price,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_cpf=customer_cpf,
        customer_phone=customer_phone,
    )

    sdk = _mp_sdk()
    success_url = f"{CHECKOUT_PUBLIC_BASE}/checkout/sucesso/?p={purchase.pk}"
    failure_url = f"{CHECKOUT_PUBLIC_BASE}/checkout/erro/?p={purchase.pk}"
    preference_payload = {
        "items": [
            {
                "id": product.key,
                "title": product.name,
                "description": product.short_description,
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(product.price),
            }
        ],
        "payer": {
            "name": customer_name,
            "email": customer_email,
        },
        "external_reference": str(purchase.pk),
        "back_urls": {
            "success": success_url,
            "failure": failure_url,
            "pending": success_url,
        },
        "notification_url": _absolute_url(request, reverse("checkout_webhook")),
        "statement_descriptor": "THECREATORSCLUB",
    }
    if customer_cpf:
        preference_payload["payer"]["identification"] = {
            "type": "CPF",
            "number": "".join(filter(str.isdigit, customer_cpf)),
        }

    try:
        mp_response = sdk.preference().create(preference_payload)
    except Exception:  # pragma: no cover - rede / SDK
        logger.exception("Falha ao criar preference no MP")
        purchase.delete()
        return _json(request, {"error": "mp_request_failed"}, status=502)

    if mp_response.get("status") not in (200, 201):
        logger.error("MP preference status=%s body=%s", mp_response.get("status"), mp_response.get("response"))
        purchase.delete()
        return _json(request, {"error": "mp_preference_error"}, status=502)

    preference_data = mp_response["response"]
    purchase.mp_preference_id = preference_data.get("id", "")
    purchase.save(update_fields=["mp_preference_id", "updated_at"])

    return _json(request, {
        "preference_id": preference_data.get("id"),
        "purchase_id": purchase.pk,
    })


@require_GET
def checkout_success(request: HttpRequest) -> HttpResponse:
    purchase_id = request.GET.get("p")
    purchase = None
    if purchase_id and purchase_id.isdigit():
        purchase = Purchase.objects.filter(pk=int(purchase_id)).first()
    return render(request, "checkout/checkout_success.html", {"purchase": purchase})


@require_GET
def checkout_failure(request: HttpRequest) -> HttpResponse:
    purchase_id = request.GET.get("p")
    purchase = None
    if purchase_id and purchase_id.isdigit():
        purchase = Purchase.objects.filter(pk=int(purchase_id)).first()
    return render(request, "checkout/checkout_failure.html", {"purchase": purchase})


# ---------- Webhook ----------

@csrf_exempt
@require_POST
def checkout_webhook(request: HttpRequest) -> HttpResponse:
    """Recebe a notificação do MP, busca o status do pagamento e, quando
    aprovado, gera um AccessCode e dispara o email para o comprador.

    O MP manda dois formatos possíveis: query string com `type=payment&data.id=...`
    ou body JSON com `{"type": "payment", "data": {"id": ...}}`.
    """
    payment_id = (
        request.GET.get("data.id")
        or request.GET.get("id")
        or ""
    )
    body = b""
    if not payment_id:
        body = request.body or b""
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError:
            data = {}
        payment_id = str(((data.get("data") or {}).get("id")) or data.get("id") or "")

    notif_type = request.GET.get("type") or request.GET.get("topic") or ""

    if not payment_id or (notif_type and notif_type != "payment"):
        # Ignora silenciosamente eventos que não são de pagamento.
        return HttpResponse(status=200)

    sdk = _mp_sdk()
    try:
        mp_payment = sdk.payment().get(payment_id)
    except Exception:
        logger.exception("Erro consultando payment %s no MP", payment_id)
        return HttpResponse(status=502)

    if mp_payment.get("status") not in (200, 201):
        logger.warning("MP payment lookup retornou %s", mp_payment.get("status"))
        return HttpResponse(status=200)

    payment_data = mp_payment["response"]
    external_reference = payment_data.get("external_reference")
    if not external_reference or not str(external_reference).isdigit():
        return HttpResponse(status=200)

    purchase = Purchase.objects.filter(pk=int(external_reference)).first()
    if purchase is None:
        return HttpResponse(status=200)

    mp_status = (payment_data.get("status") or "").lower()
    payment_method_id = payment_data.get("payment_method_id") or ""

    if mp_status == "approved":
        _approve_purchase(purchase, payment_data)
    elif mp_status in {"rejected", "cancelled"}:
        purchase.status = Purchase.STATUS_REJECTED if mp_status == "rejected" else Purchase.STATUS_CANCELLED
        purchase.mp_payment_id = str(payment_data.get("id") or "")
        purchase.payment_method = payment_method_id
        purchase.save(update_fields=["status", "mp_payment_id", "payment_method", "updated_at"])
    else:
        # pending, in_process, authorized... só atualiza metadata
        purchase.mp_payment_id = str(payment_data.get("id") or "")
        purchase.payment_method = payment_method_id
        purchase.save(update_fields=["mp_payment_id", "payment_method", "updated_at"])

    return HttpResponse(status=200)


def _approve_purchase(purchase: Purchase, payment_data: dict) -> None:
    """Idempotente: se já temos AccessCode gerado pra essa compra, não
    cria outro e não reenviamos email (o MP pode notificar repetido)."""
    if purchase.status == Purchase.STATUS_APPROVED and purchase.access_code_id:
        return

    code_value = _generate_access_code()
    access_code = AccessCode.objects.create(
        code=normalize_access_code(code_value),
        audience=AccessCode.AUDIENCE_PAID,
        is_active=True,
    )
    paid_at = _parse_mp_datetime(payment_data.get("date_approved")) or timezone.now()
    purchase.status = Purchase.STATUS_APPROVED
    purchase.mp_payment_id = str(payment_data.get("id") or "")
    purchase.payment_method = payment_data.get("payment_method_id") or ""
    purchase.paid_at = paid_at
    purchase.access_code = access_code
    purchase.save(update_fields=[
        "status",
        "mp_payment_id",
        "payment_method",
        "paid_at",
        "access_code",
        "updated_at",
    ])

    try:
        send_access_code_email(purchase, access_code)
        purchase.notified_at = timezone.now()
        purchase.save(update_fields=["notified_at", "updated_at"])
    except Exception:
        logger.exception("Falha ao enviar email do código de acesso (purchase=%s)", purchase.pk)
