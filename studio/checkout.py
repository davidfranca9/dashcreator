"""Catálogo de produtos e helpers do checkout Mercado Pago."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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
            "Centralize toda a visão do seu negócio em um único lugar. "
            "Faturamento, prospecções, contratos, jurídico e finanças — "
            "do caos ao posicionamento."
        ),
        price=Decimal("139.90"),
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


def get_product(product_key: str) -> CheckoutProduct | None:
    return CHECKOUT_PRODUCTS.get(product_key)
