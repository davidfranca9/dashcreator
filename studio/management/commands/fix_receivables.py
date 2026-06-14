from __future__ import annotations

from collections import Counter
from decimal import Decimal

from django.core.management.base import BaseCommand

from studio.models import Project
from studio.services import _compute_project_schedule


class Command(BaseCommand):
    help = (
        "Junta em 1 'Pagamento' unico PENDENTE os trabalhos inconsistentes "
        "(recebido >= total, mas com parcela nao paga e parcelas que nao batem "
        "com o valor). Apaga as parcelas e zera o 'valor recebido' para o "
        "trabalho ficar como pagamento unico em 'a receber'. "
        "Por padrao roda em --dry-run (so mostra). Use --apply para gravar."
    )

    def add_arguments(self, parser):
        parser.add_argument("--company", default="", help="Filtra por nome (contem).")
        parser.add_argument("--apply", action="store_true", help="Grava as mudancas (sem isso, so simula).")

    def handle(self, *args, **options):
        company = (options["company"] or "").strip()
        apply = options["apply"]
        qs = Project.objects.all().select_related("workspace").prefetch_related("installments")
        if company:
            qs = qs.filter(company__icontains=company)

        targets = []
        for project in qs:
            installments = list(project.installments.all())
            if not installments:
                continue
            total = Decimal(project.total_value or 0)
            received = Decimal(project.received_value or 0)
            if not (received >= total > 0):
                continue
            if not any(not i.paid for i in installments):
                continue  # nenhuma parcela pendente -> nao e o caso
            schedule = _compute_project_schedule(project)
            existing_amounts = Counter(Decimal(i.amount or 0) for i in installments)
            desired_amounts = Counter(Decimal(e["amount"]) for e in schedule)
            if existing_amounts == desired_amounts and len(installments) == len(schedule):
                continue  # bate com o cronograma -> ja esta certo, nao mexe
            targets.append((project, installments, total))

        self.stdout.write("=" * 70)
        self.stdout.write(("APLICANDO" if apply else "SIMULACAO (dry-run)") + " — junta em pagamento unico pendente:")
        for project, installments, total in targets:
            self.stdout.write("-" * 70)
            self.stdout.write(
                f"ws='{project.workspace.name}' | {project.company} (id={project.id}) | total={total} "
                f"received={project.received_value}"
            )
            self.stdout.write("  ANTES: " + " ; ".join(
                f"{i.label or '(sem)'}|{i.amount}|{'pago' if i.paid else 'nao'}" for i in installments
            ))
            self.stdout.write(f"  DEPOIS: 1x Pagamento|{total}|nao (pendente, em 'a receber'); valor recebido -> 0")
            if apply:
                project.installments.all().delete()
                project.received_value = 0
                project.save(update_fields=["received_value", "updated_at"])

        self.stdout.write("=" * 70)
        self.stdout.write(f"{'Aplicado' if apply else 'Simulado'}: {len(targets)} trabalho(s).")
        if not apply and targets:
            self.stdout.write("Revise acima. Para gravar de verdade, rode com --apply.")
