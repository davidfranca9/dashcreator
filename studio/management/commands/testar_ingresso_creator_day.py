"""Manda o e-mail novo do Creator Day (texto da Layfe + ingresso personalizado)
para quem você quiser, sem depender de uma compra de verdade.

    python manage.py testar_ingresso_creator_day davidfranca9@gmail.com --nome "Juliana Silva"
    python manage.py testar_ingresso_creator_day --salvar ingresso.png   (só gera a imagem)
"""
from django.core.management.base import BaseCommand, CommandError

from studio.checkout import get_product
from studio.emails import send_creator_day_ticket_email
from studio.ingresso import gerar_ingresso
from studio.models import Purchase


class Command(BaseCommand):
    help = "Envia o e-mail de teste do ingresso do Creator Day (ou só salva a imagem)."

    def add_arguments(self, parser):
        parser.add_argument("emails", nargs="*", help="Para quem mandar o teste")
        parser.add_argument("--nome", default="Juliana Silva", help="Nome que sai no ingresso")
        parser.add_argument("--pedido", type=int, default=1, help="Número do pedido, que vira o código")
        parser.add_argument("--salvar", help="Caminho para salvar o PNG do ingresso")

    def handle(self, *args, **opcoes):
        produto = get_product("creatorday")
        if produto is None:
            raise CommandError("Produto creatorday não encontrado no checkout.")

        if opcoes["salvar"]:
            from studio.ingresso import codigo_do_ingresso

            fake = Purchase(pk=opcoes["pedido"])
            with open(opcoes["salvar"], "wb") as arquivo:
                arquivo.write(gerar_ingresso(opcoes["nome"], codigo_do_ingresso(fake)))
            self.stdout.write(self.style.SUCCESS(f"Ingresso salvo em {opcoes['salvar']}"))

        for email in opcoes["emails"]:
            compra = Purchase(
                pk=opcoes["pedido"],
                product_key=produto.key,
                product_name=produto.name,
                amount=produto.price,
                customer_name=opcoes["nome"],
                customer_email=email,
            )
            send_creator_day_ticket_email(compra, produto)
            self.stdout.write(self.style.SUCCESS(f"E-mail de teste enviado para {email} (ingresso de {opcoes['nome']})"))

        if not opcoes["emails"] and not opcoes["salvar"]:
            raise CommandError("Diga um e-mail para mandar o teste ou use --salvar para só gerar a imagem.")
