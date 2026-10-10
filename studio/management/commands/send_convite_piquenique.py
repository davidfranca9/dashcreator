from __future__ import annotations

import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

ASSUNTO = "Você recebeu uma carta de Layfe Amorim"
BASE_CONVITE = "https://thecreatorsclub.com.br/convite/"


class Command(BaseCommand):
    help = "Dispara o convite do Piquenique de Encerramento (Turma 01) por email."

    def add_arguments(self, parser):
        parser.add_argument("emails", nargs="+", help="Emails das destinatárias")

    def handle(self, *args, **options):
        falhas = []
        for email in options["emails"]:
            # link único por pessoa: o clique aparece no log do nginx com esse código
            codigo = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower()) or "creator"
            link = f"{BASE_CONVITE}?c={codigo}"
            contexto = {"link": link}
            html = render_to_string("convite/convite_piquenique_email.html", contexto)
            texto = render_to_string("convite/convite_piquenique_email.txt", contexto)
            mensagem = EmailMultiAlternatives(
                ASSUNTO, texto, settings.DEFAULT_FROM_EMAIL, [email]
            )
            mensagem.attach_alternative(html, "text/html")
            try:
                mensagem.send(fail_silently=False)
            except Exception as exc:
                falhas.append(email)
                self.stderr.write(self.style.ERROR(f"FALHOU {email}: {exc}"))
                continue
            self.stdout.write(self.style.SUCCESS(f"Enviado para {email} (código: {codigo})"))
        enviados = len(options["emails"]) - len(falhas)
        self.stdout.write(self.style.SUCCESS(f"Total: {enviados} enviado(s), {len(falhas)} falha(s)."))
        if falhas:
            self.stdout.write(self.style.ERROR("Falharam: " + ", ".join(falhas)))
