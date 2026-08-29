"""Catálogo de produtos e helpers do checkout Mercado Pago."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class CheckoutProduct:
    key: str
    name: str
    short_description: str
    long_description: str
    price: Decimal
    audience: str  # tipo de AccessCode: "paid" / "non_paid"
    bullet_points: tuple[str, ...]


CHECKOUT_PRODUCTS: dict[str, CheckoutProduct] = {
    "dashcreator": CheckoutProduct(
        key="dashcreator",
        name="Dash Creator",
        short_description="Sistema completo para creators profissionais",
        long_description=(
            "Centralize toda a visão do seu negócio em um único lugar: "
            "faturamento, prospecções, contratos, jurídico e finanças. "
            "Do caos ao posicionamento."
        ),
        price=Decimal("134.90"),
        audience="paid",
        bullet_points=(
            "Dashboard executivo do seu negócio UGC",
            "CRM de marcas com pipeline de prospecção",
            "Financeiro com caixinhas automáticas e custos fixos",
            "Alerta de vencimento de direitos de uso de imagem",
            "Contratos gerados em 1 clique",
            "Acesso imediato após pagamento",
        ),
    ),
}


MINIMUM_CHECKOUT_PRICE = Decimal("100.00")


def _apply_price_override(product: CheckoutProduct) -> CheckoutProduct:
    env_name = f"CHECKOUT_{product.key.upper()}_PRICE"
    raw_price = os.getenv(env_name, "").strip().replace(",", ".")
    if not raw_price:
        return product
    try:
        price = Decimal(raw_price).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return product
    if price < MINIMUM_CHECKOUT_PRICE:
        return product
    return replace(product, price=price)


def get_product(product_key: str) -> CheckoutProduct | None:
    product = CHECKOUT_PRODUCTS.get(product_key)
    if product is None:
        return None
    return _apply_price_override(product)
