"""Catálogo de produtos e helpers do checkout Mercado Pago."""
from __future__ import annotations

import os
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation


# O que a compra aprovada entrega: código de acesso ao Dash Creator ou
# confirmação sem código (ingresso de evento, vaga na mentoria): só marca a
# compra como paga e manda o email de confirmação do produto.
FULFILLMENT_ACCESS_CODE = "access_code"
FULFILLMENT_TICKET = "ticket"


@dataclass(frozen=True)
class CheckoutProduct:
    key: str
    name: str
    short_description: str
    long_description: str
    price: Decimal
    audience: str  # tipo de AccessCode: "paid" / "non_paid"
    bullet_points: tuple[str, ...]
    fulfillment: str = FULFILLMENT_ACCESS_CODE
    # Páginas estáticas do thecreatorsclub.com.br para onde o Mercado Pago volta
    success_path: str = "/checkout/sucesso/"
    failure_path: str = "/checkout/erro/"
    # Pares (rótulo, valor) que vão no email do ingresso, ex.: ("Data", "...")
    details: tuple[tuple[str, str], ...] = ()
    # Prefixo dos templates do email de confirmação (checkout/<prefixo>_subject.txt e _email.txt)
    email_template: str = "ticket"
    # Manda o ingresso personalizado (PNG com o nome), quando CREATOR_DAY_EMAIL_INGRESSO estiver ligado
    personalized_ticket: bool = False

    @property
    def is_ticket(self) -> bool:
        return self.fulfillment == FULFILLMENT_TICKET


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
    "creatorday": CheckoutProduct(
        key="creatorday",
        name="Creator Day Experience",
        short_description="Ingresso: 17/10/2026, 14h, Piatã, Salvador/BA",
        long_description=(
            "Uma tarde de skincare, networking e criação para creators. "
            "Seu ingresso garante acesso ao Creator Day Experience."
        ),
        price=Decimal("120.00"),
        audience="",
        bullet_points=(
            "Skincare guiado",
            "Novas conexões com criadores locais",
            "Trocas de conhecimento",
            "Momento de desacelerar",
        ),
        fulfillment=FULFILLMENT_TICKET,
        success_path="/checkout/creator-day/sucesso/",
        failure_path="/checkout/creator-day/erro/",
        details=(
            ("Data", "17 de outubro de 2026, às 14h"),
            ("Local", "Piatã, Salvador/BA"),
        ),
        personalized_ticket=True,
    ),
    "hpc": CheckoutProduct(
        key="hpc",
        name="High Performance Creator",
        short_description="Mentoria em grupo com a Layfe: 04 encontros ao vivo, segundas às 19h",
        long_description=(
            "A mentoria para transformar o seu Instagram em um ímã de marcas: "
            "conteúdo, portfólio, roteiros e prospecção, com acompanhamento ao vivo."
        ),
        price=Decimal("597.00"),
        audience="",
        bullet_points=(
            "Acompanhamento 100% ao vivo e em grupo",
            "01 mês de acesso à Comunidade TCC",
            "Desafios com premiações semanais",
            "Guia O Jogo da Prospecção",
            "Diagnóstico completo do seu perfil",
        ),
        fulfillment=FULFILLMENT_TICKET,
        success_path="/checkout/hpc/sucesso/",
        failure_path="/checkout/hpc/erro/",
        details=(
            ("Encontros", "04 encontros ao vivo, às segundas, 19h"),
            ("Acesso", "45 dias"),
        ),
        email_template="mentoria",
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
