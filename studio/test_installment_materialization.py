"""Testes da materialização de recebíveis calculados (Entrada/Saldo/Mensalidade)
em parcelas reais confirmáveis, garantindo que o faturamento não muda."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from studio.models import Niche, Project, ProjectInstallment, ServiceCategory
from studio.services import (
    _project_finance_events,
    ensure_computed_installments,
    finance_snapshot,
    get_or_create_workspace_for_user,
    reconcile_computed_installments,
)

User = get_user_model()


def _event_signature(events):
    """(kind, amount, due_date, paid) — ignora installment_id e paid_on derivado."""
    return sorted(
        (
            e["kind"],
            str(Decimal(str(e["amount"])).quantize(Decimal("0.01"))),
            e["due_date"].isoformat(),
            bool(e["paid"]),
        )
        for e in events
    )


class InstallmentMaterializationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="mat", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.niche = Niche.objects.get(workspace=self.workspace, name="Beleza e Maquiagem")
        self.category = ServiceCategory.objects.create(workspace=self.workspace, name="Pacote")

    def _single_payment_project(self):
        # Entrada 300 (recebida) + Saldo 700 (a receber)
        return Project.objects.create(
            workspace=self.workspace,
            company="Reconflex",
            closing_source="Instagram",
            niche=self.niche,
            service_category=self.category,
            service_type="ugc_creator",
            project_name="Pacote",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=1000,
            entry_value=300,
            received_value=300,
            deliverables_count=3,
            progress=20,
            close_date=date.today() - timedelta(days=5),
            payment_due_date=date.today() + timedelta(days=10),
            due_date=date.today() + timedelta(days=20),
        )

    def _recurring_project(self):
        return Project.objects.create(
            workspace=self.workspace,
            company="Amara",
            closing_source="Inbound",
            niche=self.niche,
            service_category=self.category,
            service_type="social_media",
            project_name="Social mensal",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=3500,
            monthly_value=500,
            contract_duration_months=3,
            entry_value=0,
            received_value=0,
            deliverables_count=1,
            progress=20,
            close_date=date.today() - timedelta(days=40),
            payment_due_date=date.today() - timedelta(days=10),
            due_date=date.today() + timedelta(days=50),
        )

    def test_single_payment_events_unchanged_after_materialize(self):
        project = self._single_payment_project()
        before = _event_signature(_project_finance_events(project))
        self.assertFalse(project.installments.exists())

        ensure_computed_installments(project)
        project.refresh_from_db()

        after = _event_signature(_project_finance_events(project))
        self.assertEqual(before, after, "faturamento/eventos mudaram após materializar")
        labels = set(project.installments.values_list("label", flat=True))
        self.assertEqual(labels, {"Entrada", "Saldo"})
        self.assertTrue(project.installments.get(label="Entrada").paid)
        self.assertFalse(project.installments.get(label="Saldo").paid)
        self.assertTrue(all(e.get("installment_id") for e in _project_finance_events(project)))

    def test_recurring_events_unchanged_after_materialize(self):
        project = self._recurring_project()
        before = _event_signature(_project_finance_events(project))

        ensure_computed_installments(project)
        project.refresh_from_db()

        after = _event_signature(_project_finance_events(project))
        self.assertEqual(before, after)
        self.assertEqual(project.installments.count(), 3)
        self.assertTrue(all(e.get("installment_id") for e in _project_finance_events(project)))

    def test_finance_snapshot_backfills_and_totals_match(self):
        project = self._single_payment_project()
        snap1 = finance_snapshot(self.workspace)
        self.assertTrue(project.installments.exists(), "snapshot deveria materializar")
        snap2 = finance_snapshot(self.workspace)
        self.assertEqual(
            snap1["finance_desktop"]["receivable_total"],
            snap2["finance_desktop"]["receivable_total"],
        )
        self.assertTrue(any(i["installment_id"] for i in snap2["schedule"]))

    def test_ensure_is_idempotent(self):
        project = self._single_payment_project()
        ensure_computed_installments(project)
        count1 = project.installments.count()
        ensure_computed_installments(project)
        reconcile_computed_installments(project)
        self.assertEqual(project.installments.count(), count1)

    def test_confirm_installment_marks_paid(self):
        project = self._single_payment_project()
        ensure_computed_installments(project)
        saldo = project.installments.get(label="Saldo")
        self.assertFalse(saldo.paid)
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("installment_confirm", args=[saldo.pk]),
            {"paid_on": date.today().isoformat()},
        )
        self.assertIn(resp.status_code, (302, 303))
        saldo.refresh_from_db()
        self.assertTrue(saldo.paid)

    def _full_payment_project(self, total=250):
        # Pagamento único (sem entrada/saldo): total cheio numa data só.
        return Project.objects.create(
            workspace=self.workspace,
            company="Ilike",
            closing_source="Instagram",
            niche=self.niche,
            service_category=self.category,
            service_type="ugc_creator",
            project_name="Pacote",
            content_type="",
            stage="Fechado",
            status="Briefing",
            total_value=total,
            entry_value=0,
            received_value=0,
            deliverables_count=1,
            progress=20,
            close_date=date.today() - timedelta(days=37),
            payment_due_date=date.today() - timedelta(days=37),
            due_date=date.today() + timedelta(days=10),
        )

    def test_full_payment_labeled_pagamento_not_parcela(self):
        project = self._full_payment_project(total=250)
        ensure_computed_installments(project)
        labels = list(project.installments.values_list("label", flat=True))
        self.assertEqual(labels, ["Pagamento"])
        kinds = [e["kind"] for e in _project_finance_events(project)]
        self.assertEqual(kinds, ["Pagamento"])
        self.assertNotIn("Parcela", kinds)
        self.assertNotIn("Entrada", kinds)

    def test_relabels_legacy_unlabeled_full_payment(self):
        # Simula o backfill antigo: parcela sem rótulo que casa com o pagamento.
        project = self._full_payment_project(total=250)
        ProjectInstallment.objects.create(
            workspace=self.workspace, project=project, label="",
            amount=250, due_date=date.today() - timedelta(days=37), paid=False,
        )
        ensure_computed_installments(project)
        project.refresh_from_db()
        self.assertEqual(list(project.installments.values_list("label", flat=True)), ["Pagamento"])

    def test_does_not_collapse_genuine_manual_split(self):
        # Divisão manual de propósito (3x 300) não bate com o pagamento único
        # calculado (900) → NÃO vira "Pagamento" nem é colapsada; só numera.
        project = self._full_payment_project(total=900)
        for n in range(3):
            ProjectInstallment.objects.create(
                workspace=self.workspace, project=project, label="",
                amount=300, due_date=date.today() + timedelta(days=10 * n), paid=False,
            )
        ensure_computed_installments(project)
        project.refresh_from_db()
        self.assertEqual(project.installments.count(), 3)  # não colapsou
        labels = sorted(project.installments.values_list("label", flat=True))
        self.assertEqual(labels, ["Parcela 1", "Parcela 2", "Parcela 3"])
        self.assertNotIn("Pagamento", {e["kind"] for e in _project_finance_events(project)})

    def test_numbers_real_installment_split(self):
        # 2 parcelas de 200 que NÃO batem com o pagamento único calculado (400)
        # → parcelamento real → numera "Parcela 1", "Parcela 2".
        project = self._full_payment_project(total=400)
        for due in (date.today() - timedelta(days=10), date.today() + timedelta(days=20)):
            ProjectInstallment.objects.create(
                workspace=self.workspace, project=project, label="",
                amount=200, due_date=due, paid=False,
            )
        ensure_computed_installments(project)
        project.refresh_from_db()
        labels = sorted(project.installments.values_list("label", flat=True))
        self.assertEqual(labels, ["Parcela 1", "Parcela 2"])

    def test_fix_receivables_collapses_inconsistent_to_single_pending(self):
        from django.core.management import call_command
        project = self._full_payment_project(total=500)  # entry=0
        project.received_value = 500  # trabalho diz recebido=total (inconsistente)
        project.save(update_fields=["received_value"])
        ProjectInstallment.objects.create(
            workspace=self.workspace, project=project, label="",
            amount=250, due_date=date.today() - timedelta(days=20), paid=True,
        )
        ProjectInstallment.objects.create(
            workspace=self.workspace, project=project, label="",
            amount=250, due_date=date.today() - timedelta(days=5), paid=False,
        )
        call_command("fix_receivables", "--apply", verbosity=0)
        project.refresh_from_db()
        self.assertEqual(project.received_value, 0)
        self.assertEqual(project.installments.count(), 0)
        # ao carregar o financeiro, vira 1 Pagamento pendente do valor cheio
        ensure_computed_installments(project)
        events = _project_finance_events(project)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["kind"], "Pagamento")
        self.assertFalse(events[0]["paid"])
        self.assertEqual(events[0]["amount"], Decimal("500"))

    def test_labeled_installments_do_not_seed_manual_monthly_repetition(self):
        """Parcelas ja calculadas/rotuladas nao podem virar molde mensal manual."""
        from studio.views import _sync_auto_monthly_installments

        project = self._recurring_project()
        project.service_type = "consultoria_marketing"
        project.contract_duration_months = 6
        project.close_date = date(2026, 1, 15)
        project.payment_due_date = date(2026, 1, 15)
        project.due_date = date(2026, 6, 30)
        project.save(
            update_fields=[
                "service_type",
                "contract_duration_months",
                "close_date",
                "payment_due_date",
                "due_date",
                "updated_at",
            ]
        )
        for index in range(1, 7):
            ProjectInstallment.objects.create(
                workspace=self.workspace,
                project=project,
                label=f"Parcela {index}",
                amount=3500,
                due_date=date(2026, 1, 15),
                paid=True,
                paid_on=date(2026, 1, 15),
            )

        _sync_auto_monthly_installments(project, self.workspace, has_installments_yes=True)

        self.assertEqual(project.installments.count(), 6)
        self.assertFalse(project.installments.filter(due_date__gte=date(2026, 2, 1)).exists())

    def test_reconcile_preserves_confirmed_parcela(self):
        """Editar/recalcular não pode apagar nem desfazer uma confirmação."""
        project = self._single_payment_project()
        reconcile_computed_installments(project)
        saldo = project.installments.get(label="Saldo")
        saldo.paid = True
        saldo.paid_on = date.today()
        saldo.save(update_fields=["paid", "paid_on", "updated_at"])
        confirmed_pk = saldo.pk

        # muda o valor do contrato e reconcilia de novo
        project.total_value = 1500
        project.save(update_fields=["total_value", "updated_at"])
        # limpa o cache de prefetch para refletir o novo total
        project = Project.objects.get(pk=project.pk)
        reconcile_computed_installments(project)

        self.assertTrue(
            ProjectInstallment.objects.filter(pk=confirmed_pk, paid=True).exists(),
            "reconcile apagou/desfez a confirmação",
        )
