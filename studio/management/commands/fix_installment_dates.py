from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand

from studio.models import Project, ProjectInstallment
from studio.services import _compute_project_schedule


class Command(BaseCommand):
    help = (
        "Conserta as DATAS das parcelas materializadas (ProjectInstallment) "
        "quando divergem do cronograma calculado, preservando as pagas. "
        "Roda em --dry-run por padrao. Use --apply pra gravar. "
        "Bug conhecido: contratos recorrentes (consultoria, social media) que "
        "tiveram close_date ou contract_duration_months alterados depois de "
        "criados nao atualizam as datas das parcelas ja existentes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--company", default="", help="Filtra pelo nome da empresa (contem).")
        parser.add_argument("--project-id", type=int, default=None, help="Roda so num projeto especifico.")
        parser.add_argument("--apply", action="store_true", help="Grava as mudancas (sem isso, so simula).")

    def handle(self, *args, **options):
        company = (options["company"] or "").strip()
        project_id = options["project_id"]
        apply = options["apply"]

        qs = Project.objects.all().select_related("workspace").prefetch_related("installments")
        if project_id:
            qs = qs.filter(pk=project_id)
        if company:
            qs = qs.filter(company__icontains=company)

        targets = []
        for project in qs:
            existing = list(project.installments.all().order_by("due_date", "pk"))
            if not existing:
                continue
            schedule = _compute_project_schedule(project)
            if not schedule:
                continue
            # Divergencia real: qualquer parcela existente com label do cronograma
            # cuja data nao bate com o desejado.
            desired_by_label = {entry["label"]: entry for entry in schedule}
            mismatches = []
            for inst in existing:
                entry = desired_by_label.get(inst.label)
                if entry is None:
                    continue
                if inst.due_date != entry["due_date"]:
                    mismatches.append((inst, entry))
            if not mismatches:
                continue
            targets.append((project, existing, schedule, mismatches))

        self.stdout.write("=" * 78)
        self.stdout.write(
            ("APLICANDO" if apply else "SIMULACAO (dry-run)")
            + f" - {len(targets)} projeto(s) com parcelas de data errada:"
        )

        for project, existing, schedule, mismatches in targets:
            self.stdout.write("-" * 78)
            self.stdout.write(
                f"ws='{project.workspace.name}' | {project.company} (id={project.pk}) | "
                f"type={project.service_type} close={project.close_date} dur={project.contract_duration_months}"
            )
            self.stdout.write("  ANTES (parcelas no banco):")
            for inst in existing:
                self.stdout.write(
                    f"    id={inst.pk} label={inst.label!r} due={inst.due_date} "
                    f"amount={inst.amount} paid={inst.paid}"
                )
            self.stdout.write("  CRONOGRAMA (o que as datas deveriam ser):")
            for entry in schedule:
                self.stdout.write(
                    f"    label={entry['label']!r} due={entry['due_date']} amount={entry['amount']}"
                )
            self.stdout.write(f"  {len(mismatches)} parcela(s) com data errada. Vao ser atualizadas:")
            for inst, entry in mismatches:
                marker = "(pago, so muda data)" if inst.paid else ""
                self.stdout.write(
                    f"    id={inst.pk} '{inst.label}' {inst.due_date} -> {entry['due_date']} {marker}"
                )
                if apply:
                    inst.due_date = entry["due_date"]
                    fields = ["due_date", "updated_at"]
                    # Se estava paid, garante que paid_on tambem acompanhe a nova
                    # data (senao vira paga antes do vencimento novo, que ta ok
                    # mas confunde relatorios).
                    if inst.paid and inst.paid_on and inst.paid_on == inst.due_date:
                        inst.paid_on = entry["due_date"]
                        fields.append("paid_on")
                    inst.save(update_fields=fields)

        self.stdout.write("=" * 78)
        self.stdout.write(f"{'Aplicado' if apply else 'Simulado'}: {len(targets)} projeto(s).")
        if not apply and targets:
            self.stdout.write("Revise acima. Para gravar, rode de novo com --apply.")
