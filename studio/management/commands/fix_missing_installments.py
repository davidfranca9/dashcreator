from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from studio.models import Project, ProjectInstallment
from studio.services import _compute_project_schedule


class Command(BaseCommand):
    help = (
        "Materializa parcelas do cronograma calculado nos projetos que ainda "
        "nao tem parcela alguma (ProjectInstallment.count()=0). Idempotente "
        "e conservador: nao mexe em projetos que ja tem parcelas, so cria as "
        "que estao faltando. Rode primeiro sem --apply pra ver o preview, "
        "depois com --apply pra gravar."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Grava as mudancas (sem isso, so simula).")
        parser.add_argument("--company", default="", help="Filtra por empresa (contem, case-insensitive).")
        parser.add_argument("--workspace", default="", help="Filtra por workspace (contem, case-insensitive).")

    def handle(self, *args, **options):
        apply = options["apply"]
        company = (options["company"] or "").strip()
        workspace = (options["workspace"] or "").strip()

        qs = (
            Project.objects.all()
            .select_related("workspace")
            .prefetch_related("installments")
        )
        if company:
            qs = qs.filter(company__icontains=company)
        if workspace:
            qs = qs.filter(workspace__name__icontains=workspace)

        total_projects = qs.count()
        skipped_has = 0
        skipped_empty = 0
        targets = 0
        created_total = 0

        for project in qs:
            existing_count = project.installments.count()
            if existing_count > 0:
                skipped_has += 1
                continue
            schedule = _compute_project_schedule(project)
            if not schedule:
                skipped_empty += 1
                continue
            targets += 1
            self.stdout.write("-" * 70)
            self.stdout.write(
                f"[{project.workspace.name}] {project.company} (id={project.pk}) "
                f"| type={project.service_type} | close={project.close_date} due={project.due_date}"
            )
            for entry in schedule:
                amount = Decimal(entry.get("amount") or 0)
                if amount <= 0:
                    continue
                paid = bool(entry.get("paid"))
                paid_on = entry.get("paid_on")
                label = entry.get("label") or "Parcela"
                due_date = entry.get("due_date")
                verb = "CRIA " if apply else "CRIARIA"
                self.stdout.write(
                    f"  {verb}: {label!r} R$ {amount} venc={due_date} paid={paid}"
                )
                if apply:
                    ProjectInstallment.objects.create(
                        project=project,
                        workspace_id=project.workspace_id,
                        label=label,
                        amount=amount,
                        due_date=due_date,
                        paid=paid,
                        paid_on=paid_on,
                    )
                    created_total += 1

        self.stdout.write("=" * 70)
        self.stdout.write(f"Projetos analisados: {total_projects}")
        self.stdout.write(f"  Ja tem parcelas (skip): {skipped_has}")
        self.stdout.write(f"  Cronograma vazio (skip): {skipped_empty}")
        self.stdout.write(f"  Alvos: {targets} projeto(s)")
        if apply:
            self.stdout.write(f"  Parcelas CRIADAS: {created_total}")
            self.stdout.write("Feito.")
        else:
            self.stdout.write(f"  Rode com --apply pra gravar. (simulacao)")
