"""Creator Day Experience: lista de espera do site e ingressos do checkout,
mostrados na página interna /creator-day/ do app (só contas do time)."""
from __future__ import annotations

from decimal import Decimal

from .models import EventWaitlistEntry, Purchase

# Mesmo código do produto no checkout (studio/checkout.py)
CREATOR_DAY_EVENT = "creatorday"

_CARD_BRANDS = {"master", "visa", "elo", "amex", "hipercard", "cabal", "diners"}
_BOLETO = {"bolbradesco", "pec", "boleto"}


def brl(value: Decimal) -> str:
    texto = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def whatsapp_link(numero: str) -> str:
    digitos = "".join(ch for ch in numero or "" if ch.isdigit())
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return f"https://wa.me/{digitos}" if len(digitos) >= 12 else ""


def payment_label(method: str) -> str:
    method = (method or "").lower()
    if not method:
        return "Não escolheu"
    if method == "pix":
        return "Pix"
    if method in _BOLETO:
        return "Boleto"
    if method.startswith("deb"):
        return "Cartão de débito"
    if method in _CARD_BRANDS:
        return "Cartão de crédito"
    return method


def ticket_status(purchase: Purchase) -> tuple[str, str]:
    """(rótulo, tom) da situação do ingresso na tabela."""
    if purchase.status == Purchase.STATUS_APPROVED:
        return "Pago", "ok"
    if purchase.status == Purchase.STATUS_REJECTED:
        return "Recusado", "erro"
    if purchase.status == Purchase.STATUS_CANCELLED:
        return "Cancelado", "erro"
    if purchase.mp_payment_id:
        # Pix ou boleto gerado, esperando cair
        return "Aguardando pagamento", "espera"
    return "Não finalizou", "neutro"


def creator_day_snapshot() -> dict:
    inscritos = list(EventWaitlistEntry.objects.filter(event_key=CREATOR_DAY_EVENT))
    compras = list(Purchase.objects.filter(product_key=CREATOR_DAY_EVENT))
    pagas = [c for c in compras if c.status == Purchase.STATUS_APPROVED]

    waitlist = [
        {
            "name": e.name,
            "email": e.email,
            "whatsapp": e.whatsapp,
            "wa": whatsapp_link(e.whatsapp),
            "page": e.get_page_display(),
            "created_at": e.created_at,
        }
        for e in inscritos
    ]
    tickets = []
    for c in compras:
        rotulo, tom = ticket_status(c)
        tickets.append({
            "name": c.customer_name,
            "email": c.customer_email,
            "whatsapp": c.customer_phone,
            "wa": whatsapp_link(c.customer_phone),
            "amount": brl(c.amount),
            "coupon": c.coupon_code,
            "status": rotulo,
            "tone": tom,
            "payment": payment_label(c.payment_method),
            "created_at": c.created_at,
        })

    return {
        "waitlist": waitlist,
        "tickets": tickets,
        "kpis": {
            "inscritos": len(inscritos),
            "compras": len(compras),
            "pagos": len(pagas),
            "em_aberto": sum(1 for c in compras if c.status == Purchase.STATUS_PENDING),
            "recebido": brl(sum((c.amount for c in pagas), Decimal("0"))),
        },
    }
