from __future__ import annotations

from statistics import mean
from time import perf_counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, reset_queries
from django.test.utils import CaptureQueriesContext

from studio.models import Project, Prospect, Workspace
from studio.services import (
    dashboard_snapshot,
    finance_snapshot,
    jobs_snapshot_filtered,
    prospection_snapshot,
    reports_snapshot,
    shell_context,
)


User = get_user_model()


class Command(BaseCommand):
    help = "Mede tempo e queries das telas principais para um workspace."

    def add_arguments(self, parser):
        parser.add_argument("--workspace", help="Slug do workspace a ser analisado.")
        parser.add_argument("--username", help="Usuario vinculado ao workspace a ser analisado.")
        parser.add_argument("--repeat", type=int, default=3, help="Numero de repeticoes por medicao.")

    def handle(self, *args, **options):
        workspace = self._resolve_workspace(options.get("workspace"), options.get("username"))
        repeat = max(1, options["repeat"])
        membership = workspace.memberships.select_related("user").first()
        user = membership.user if membership else None

        self.stdout.write(self.style.SUCCESS(f"Workspace: {workspace.name} ({workspace.slug})"))
        self.stdout.write(f"Banco: {connection.vendor} | {connection.settings_dict.get('NAME')}")
        self.stdout.write(
            "Dados: "
            f"projetos={Project.objects.filter(workspace=workspace).count()} | "
            f"ativos={Project.objects.filter(workspace=workspace, stage='Fechado').count()} | "
            f"entregues={Project.objects.filter(workspace=workspace, stage='Entregue').count()} | "
            f"leads={Prospect.objects.filter(workspace=workspace).count()}"
        )
        self.stdout.write("")

        benchmark_items = [
            ("shell_context", lambda: shell_context("dashboard", workspace, "Dashboard", "Resumo", user=user)),
            ("dashboard_snapshot", lambda: dashboard_snapshot(workspace)),
            ("prospection_snapshot", lambda: prospection_snapshot(workspace)),
            ("jobs_snapshot_filtered", lambda: jobs_snapshot_filtered(workspace)),
            ("finance_snapshot", lambda: finance_snapshot(workspace)),
            ("reports_snapshot", lambda: reports_snapshot(workspace)),
        ]

        for label, callback in benchmark_items:
            timings_ms: list[float] = []
            query_counts: list[int] = []
            for _ in range(repeat):
                reset_queries()
                previous_force_debug = connection.force_debug_cursor
                connection.force_debug_cursor = True
                start = perf_counter()
                with CaptureQueriesContext(connection) as captured:
                    callback()
                elapsed_ms = (perf_counter() - start) * 1000
                connection.force_debug_cursor = previous_force_debug
                timings_ms.append(round(elapsed_ms, 2))
                query_counts.append(len(captured))

            self.stdout.write(
                f"{label}: avg={mean(timings_ms):.2f}ms | min={min(timings_ms):.2f}ms | "
                f"max={max(timings_ms):.2f}ms | queries={query_counts}"
            )

    def _resolve_workspace(self, workspace_slug: str | None, username: str | None) -> Workspace:
        if workspace_slug:
            try:
                return Workspace.objects.get(slug=workspace_slug)
            except Workspace.DoesNotExist as exc:
                raise CommandError(f"Workspace nao encontrado: {workspace_slug}") from exc

        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f"Usuario nao encontrado: {username}") from exc

            membership = user.memberships.select_related("workspace").first()
            if membership is None:
                raise CommandError(f"O usuario {username} nao possui workspace.")
            return membership.workspace

        raise CommandError("Informe --workspace ou --username.")
