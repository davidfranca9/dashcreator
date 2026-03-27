from __future__ import annotations

import secrets
import string

from django.core.management.base import BaseCommand

from studio.models import AccessCode


class Command(BaseCommand):
    help = "Gera codigos de acesso para usuarios pagantes e nao pagantes."

    def add_arguments(self, parser):
        parser.add_argument("--paid", type=int, default=25, help="Quantidade de codigos para usuarios pagantes.")
        parser.add_argument("--non-paid", dest="non_paid", type=int, default=25, help="Quantidade de codigos para usuarios nao pagantes.")
        parser.add_argument("--prefix", default="TCC", help="Prefixo usado nos codigos.")
        parser.add_argument("--length", type=int, default=8, help="Tamanho da parte aleatoria do codigo.")

    def handle(self, *args, **options):
        prefix = (options["prefix"] or "TCC").strip().upper()
        length = max(4, options["length"])
        paid_codes = self._create_codes(prefix, "P", AccessCode.AUDIENCE_PAID, options["paid"], length)
        non_paid_codes = self._create_codes(prefix, "N", AccessCode.AUDIENCE_NON_PAID, options["non_paid"], length)

        self.stdout.write(self.style.SUCCESS(f"Codigos pagantes gerados: {len(paid_codes)}"))
        for code in paid_codes:
            self.stdout.write(code)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Codigos nao pagantes gerados: {len(non_paid_codes)}"))
        for code in non_paid_codes:
            self.stdout.write(code)

    def _create_codes(self, prefix: str, audience_prefix: str, audience: str, quantity: int, length: int) -> list[str]:
        alphabet = string.ascii_uppercase + string.digits
        created_codes: list[str] = []

        for _ in range(max(0, quantity)):
            while True:
                random_part = "".join(secrets.choice(alphabet) for _ in range(length))
                code = f"{prefix}-{audience_prefix}-{random_part}"
                if not AccessCode.objects.filter(code=code).exists():
                    AccessCode.objects.create(code=code, audience=audience)
                    created_codes.append(code)
                    break

        return created_codes
