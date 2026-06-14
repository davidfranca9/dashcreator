from __future__ import annotations

from django.core.management.base import BaseCommand

from studio.models import Workspace


class Command(BaseCommand):
    help = (
        "Liga/desliga o modo beta de um workspace (recebe as novidades visuais "
        "antes de todos). Ex.: set_beta --workspace 'Layfe Amorim'. "
        "Use --off para desligar. Sem --workspace, lista os workspaces beta."
    )

    def add_arguments(self, parser):
        parser.add_argument("--workspace", default="", help="Nome (contem) do workspace.")
        parser.add_argument("--off", action="store_true", help="Desliga o beta (padrao e ligar).")

    def handle(self, *args, **options):
        name = (options["workspace"] or "").strip()
        if not name:
            betas = Workspace.objects.filter(is_beta=True).order_by("name")
            self.stdout.write("Workspaces em modo beta:")
            for ws in betas:
                self.stdout.write(f"  - {ws.name} (slug={ws.slug})")
            if not betas:
                self.stdout.write("  (nenhum)")
            return

        matches = list(Workspace.objects.filter(name__icontains=name))
        if not matches:
            self.stdout.write(f"Nenhum workspace encontrado com '{name}'.")
            return
        if len(matches) > 1:
            self.stdout.write("Mais de um workspace bate — seja mais especifico:")
            for ws in matches:
                self.stdout.write(f"  - {ws.name} (slug={ws.slug})")
            return

        ws = matches[0]
        ws.is_beta = not options["off"]
        ws.save(update_fields=["is_beta", "updated_at"])
        estado = "DESLIGADO" if options["off"] else "LIGADO"
        self.stdout.write(f"Beta {estado} para '{ws.name}' (slug={ws.slug}).")
