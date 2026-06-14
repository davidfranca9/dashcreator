from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from studio.models import Project
from studio.services import _compute_project_schedule


class Command(BaseCommand):
    help = (
        "Diagnostico (somente leitura) dos recebiveis/parcelas de um trabalho. "
        "Mostra valores do projeto, parcelas no banco e o cronograma calculado, "
        "mais se a re-rotulagem automatica bateria. Use --company para filtrar."
    )

    def add_arguments(self, parser):
        parser.add_argument("--company", default="", help="Filtra por nome (contem, case-insensitive).")
        parser.add_argument("--unlabeled-only", action="store_true", help="So trabalhos com parcela sem rotulo.")

    def handle(self, *args, **options):
        company = (options["company"] or "").strip()
        qs = Project.objects.all().prefetch_related("installments").order_by("company")
        if company:
            qs = qs.filter(company__icontains=company)

        for project in qs:
            installments = list(project.installments.all().order_by("due_date", "pk"))
            if options["unlabeled_only"] and not any(not i.label for i in installments):
                continue

            self.stdout.write("=" * 70)
            self.stdout.write(
                f"{project.company} | type={project.service_type} | total={project.total_value} "
                f"entry={project.entry_value} received={project.received_value} "
                f"dur={project.contract_duration_months}"
            )
            self.stdout.write("  PARCELAS no banco:")
            for i in installments:
                self.stdout.write(
                    f"    id={i.id} label={i.label!r} amount={i.amount} due={i.due_date} paid={i.paid}"
                )
            schedule = _compute_project_schedule(project)
            self.stdout.write("  CRONOGRAMA calculado:")
            for e in schedule:
                self.stdout.write(f"    label={e['label']!r} amount={e['amount']} due={e['due_date']} paid={e['paid']}")

            from collections import Counter
            existing_amounts = Counter(Decimal(i.amount or 0) for i in installments)
            desired_amounts = Counter(Decimal(e["amount"]) for e in schedule)
            would_relabel = (
                bool(schedule)
                and len(installments) == len(schedule)
                and existing_amounts == desired_amounts
                and any(not i.label for i in installments)
            )
            self.stdout.write(f"  -> re-rotularia automaticamente? {'SIM' if would_relabel else 'NAO'}")
            if not would_relabel and any(not i.label for i in installments):
                self.stdout.write(
                    f"     (valores banco={dict(existing_amounts)} vs calculado={dict(desired_amounts)})"
                )
