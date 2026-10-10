"""Manda o e-mail do ingresso para quem já comprou o Creator Day.

Só olha as compras aprovadas do evento. Por padrão não repete envio: quem
já recebeu (notified_at preenchido) fica de fora, a não ser com --reenviar.

    python manage.py enviar_ingressos_creator_day --listar
    python manage.py enviar_ingressos_creator_day
    python manage.py enviar_ingressos_creator_day --reenviar
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from studio.checkout import get_product
from studio.emails import send_creator_day_ticket_email
from studio.models import Purchase


class Command(BaseCommand):
    help = "Envia o ingresso personalizado para as compradoras do Creator Day."

    def add_arguments(self, parser):
        parser.add_argument("--listar", action="store_true", help="Só mostra quem receberia, sem mandar nada")
        parser.add_argument("--reenviar", action="store_true", help="Manda também para quem já recebeu")
        parser.add_argument("--so", action="append", default=[], help="Limita a estes e-mails")

    def handle(self, *args, **opcoes):
        produto = get_product("creatorday")
        if produto is None:
            raise CommandError("Produto creatorday não encontrado no checkout.")

        compras = Purchase.objects.filter(
            product_key="creatorday", status=Purchase.STATUS_APPROVED
        ).order_by("paid_at", "pk")
        if opcoes["so"]:
            alvos = {e.strip().lower() for e in opcoes["so"]}
            compras = [c for c in compras if c.customer_email.lower() in alvos]
        else:
            compras = list(compras)

        pendentes = [c for c in compras if opcoes["reenviar"] or not c.notified_at]
        ja_foram = len(compras) - len(pendentes)

        self.stdout.write(f"{len(compras)} compra(s) paga(s) do Creator Day; {ja_foram} já tinham recebido.")
        for compra in pendentes:
            self.stdout.write(f"  #{compra.pk} {compra.customer_name} <{compra.customer_email}>")

        if opcoes["listar"]:
            self.stdout.write(self.style.WARNING("Nada enviado (--listar)."))
            return

        enviados, falhas = 0, []
        for compra in pendentes:
            try:
                send_creator_day_ticket_email(compra, produto)
            except Exception as erro:  # uma falha não pode parar a fila
                falhas.append((compra, erro))
                self.stdout.write(self.style.ERROR(f"  falhou #{compra.pk} {compra.customer_email}: {erro}"))
                continue
            compra.notified_at = timezone.now()
            compra.save(update_fields=["notified_at", "updated_at"])
            enviados += 1
            self.stdout.write(self.style.SUCCESS(f"  enviado #{compra.pk} {compra.customer_email}"))

        self.stdout.write(self.style.SUCCESS(f"Pronto: {enviados} enviado(s), {len(falhas)} falha(s)."))
