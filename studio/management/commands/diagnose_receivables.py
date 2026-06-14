from __future__ import annotations

from collections import Counter
from decimal import Decimal

from django.core.management.base import BaseCommand

from studio.models import Project
from studio.services import _compute_project_schedule


class Command(BaseCommand):
    help = (
        "Diagnostico (somente leitura) dos recebiveis/parcelas dos trabalhos. "
        "Mostra valores do projeto, parcelas no banco e o cronograma calculado, "
        "e classifica cada trabalho. Use --company para filtrar e --mismatch-only "
        "para ver so os problematicos (parcelas que nao batem com o valor)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--company", default="", help="Filtra por nome (contem, case-insensitive).")
        parser.add_argument("--unlabeled-only", action="store_true", help="So trabalhos com parcela sem rotulo.")
        parser.add_argument("--mismatch-only", action="store_true", help="So trabalhos problematicos (parcelas sem rotulo que NAO batem com o cronograma).")

    def handle(self, *args, **options):
        company = (options["company"] or "").strip()
        qs = (
            Project.objects.all()
            .select_related("workspace")
            .prefetch_related("installments")
            .order_by("workspace__name", "company")
        )
        if company:
            qs = qs.filter(company__icontains=company)

        total_projects = 0
        with_unlabeled = 0
        will_relabel = 0
        mismatch = 0           # parcelas sem rotulo que nao batem -> continuam "Parcela"
        inconsistent_paid = 0  # received_value diz pago, mas parcela(s) nao paga(s)
        all_ws = set()
        mismatch_ws = set()
        inconsistent_ws = set()

        for project in qs:
            total_projects += 1
            installments = list(project.installments.all().order_by("due_date", "pk"))
            schedule = _compute_project_schedule(project)
            has_unlabeled = any(not i.label for i in installments)

            existing_amounts = Counter(Decimal(i.amount or 0) for i in installments)
            desired_amounts = Counter(Decimal(e["amount"]) for e in schedule)
            would_relabel = (
                bool(schedule)
                and has_unlabeled
                and len(installments) == len(schedule)
                and existing_amounts == desired_amounts
            )
            is_mismatch = has_unlabeled and not would_relabel

            received = Decimal(project.received_value or 0)
            total = Decimal(project.total_value or 0)
            unpaid_amount = sum((Decimal(i.amount or 0) for i in installments if not i.paid), Decimal("0"))
            # "valor recebido" cobre parcelas que estao marcadas como nao pagas
            is_inconsistent = bool(installments) and received >= total > 0 and unpaid_amount > 0

            all_ws.add(project.workspace_id)
            if has_unlabeled:
                with_unlabeled += 1
            if would_relabel:
                will_relabel += 1
            if is_mismatch:
                mismatch += 1
                mismatch_ws.add(project.workspace_id)
            if is_inconsistent:
                inconsistent_paid += 1
                inconsistent_ws.add(project.workspace_id)

            # filtros de exibicao
            if options["unlabeled_only"] and not has_unlabeled:
                continue
            if options["mismatch_only"] and not is_mismatch:
                continue

            self.stdout.write("=" * 70)
            tags = []
            if would_relabel:
                tags.append("AUTO-OK")
            if is_mismatch:
                tags.append("MISMATCH(continua Parcela)")
            if is_inconsistent:
                tags.append("INCONSISTENTE(recebido!=parcelas)")
            self.stdout.write(
                f"[{', '.join(tags) or 'ok'}] ws='{project.workspace.name}' | {project.company} (id={project.id}) | "
                f"type={project.service_type} | total={total} entry={project.entry_value} "
                f"received={received} dur={project.contract_duration_months}"
            )
            self.stdout.write("  PARCELAS no banco:")
            for i in installments:
                self.stdout.write(f"    id={i.id} label={i.label!r} amount={i.amount} due={i.due_date} paid={i.paid}")
            self.stdout.write("  CRONOGRAMA calculado:")
            for e in schedule:
                self.stdout.write(f"    label={e['label']!r} amount={e['amount']} due={e['due_date']} paid={e['paid']}")
            if is_mismatch:
                self.stdout.write(f"     (valores banco={dict(existing_amounts)} vs calculado={dict(desired_amounts)})")

        self.stdout.write("=" * 70)
        self.stdout.write("RESUMO (todos os workspaces / usuarios):")
        self.stdout.write(f"  workspaces (usuarios) analisados: {len(all_ws)}")
        self.stdout.write(f"  trabalhos analisados: {total_projects}")
        self.stdout.write(f"  com parcela sem rotulo: {with_unlabeled}")
        self.stdout.write(f"  serao re-rotulados automaticamente (batem): {will_relabel}")
        self.stdout.write(
            f"  PROBLEMATICOS (mismatch, continuam 'Parcela'): {mismatch} "
            f"trabalhos em {len(mismatch_ws)} workspace(s)"
        )
        self.stdout.write(
            f"  INCONSISTENTES (recebido total mas parcela nao paga): {inconsistent_paid} "
            f"trabalhos em {len(inconsistent_ws)} workspace(s)"
        )
