"""Aba Creator Day da Central: fornecedores, orçamento, tarefas e roteiro."""
from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from studio.evento import CHECKLIST_SUGERIDO, ROTEIRO_SUGERIDO, evento_snapshot
from studio.models import EventScheduleItem, EventSupplier, EventTask, Purchase
from studio.services import get_or_create_workspace_for_user

SENHA = "SenhaForte123!"


@override_settings(CENTRAL_ACESSO_DIRETO=True)
class CentralEventoTests(TestCase):
    def setUp(self):
        U = get_user_model()
        self.layfe = U.objects.create_user("layfeamorim", email="layfe@example.com", password=SENHA)
        get_or_create_workspace_for_user(self.layfe)
        self.maria = U.objects.create_user("maria", email="maria@example.com", password=SENHA)
        get_or_create_workspace_for_user(self.maria)
        self.client.post("/central/entrar/", {"username": "layfe@example.com", "password": SENHA})

    def fornecedor(self, **extra):
        dados = {"name": "Buffet Sabor", "category": "comida", "status": "fechado", "deal": "pago",
                 "amount": "1.500,00", "paid_amount": "500", "due_date": "2026-10-10"}
        dados.update(extra)
        return self.client.post("/central/evento/fornecedor/salvar/", dados)

    def test_cadastra_fornecedor_com_valor_brasileiro(self):
        r = self.fornecedor(instagram="@buffetsabor")
        self.assertRedirects(r, "/central/#evento/fornecedores", fetch_redirect_response=False)
        f = EventSupplier.objects.get()
        self.assertEqual((f.event_key, f.amount, f.paid_amount, f.instagram), ("creatorday", Decimal("1500.00"), Decimal("500"), "buffetsabor"))
        painel = self.client.get("/central/")
        self.assertContains(painel, "Buffet Sabor")
        self.assertContains(painel, "Fornecedor salvo.")
        self.assertNotContains(painel, "—")

    def test_edita_e_exclui_fornecedor(self):
        self.fornecedor()
        f = EventSupplier.objects.get()
        self.client.post(f"/central/evento/fornecedor/{f.pk}/salvar/", {"name": "Buffet Sabor Novo", "category": "comida", "status": "pago", "deal": "pago", "amount": "1500"})
        f.refresh_from_db()
        self.assertEqual((f.name, f.status), ("Buffet Sabor Novo", "pago"))
        self.client.post(f"/central/evento/fornecedor/{f.pk}/excluir/")
        self.assertFalse(EventSupplier.objects.exists())

    def test_valor_invalido_nao_salva_e_avisa(self):
        self.fornecedor(amount="mil reais")
        self.assertFalse(EventSupplier.objects.exists())
        self.assertContains(self.client.get("/central/"), "Não salvou.")

    def test_quem_nao_e_do_time_nao_mexe(self):
        self.fornecedor()
        f = EventSupplier.objects.get()
        fora = self.client_class()
        fora.post("/central/entrar/", {"username": "maria@example.com", "password": SENHA})
        r = fora.post("/central/evento/fornecedor/salvar/", {"name": "Invasora", "category": "outros", "status": "cotar", "deal": "pago"})
        self.assertRedirects(r, "/central/entrar/", fetch_redirect_response=False)
        fora.post(f"/central/evento/fornecedor/{f.pk}/excluir/")
        anonimo = self.client_class()
        anonimo.post("/central/evento/sugestao/tarefas/")
        self.assertEqual(list(EventSupplier.objects.values_list("name", flat=True)), ["Buffet Sabor"])
        self.assertFalse(EventTask.objects.exists())

    def test_so_aceita_post_e_tipos_conhecidos(self):
        self.assertEqual(self.client.get("/central/evento/fornecedor/salvar/").status_code, 405)
        self.assertEqual(self.client.post("/central/evento/usuario/salvar/", {}).status_code, 404)

    def test_checklist_e_roteiro_sugeridos_so_quando_vazios(self):
        self.client.post("/central/evento/sugestao/tarefas/")
        self.client.post("/central/evento/sugestao/tarefas/")
        self.client.post("/central/evento/sugestao/roteiro/")
        self.assertEqual(EventTask.objects.count(), len(CHECKLIST_SUGERIDO))
        self.assertEqual(EventScheduleItem.objects.count(), len(ROTEIRO_SUGERIDO))
        self.assertTrue(all(t.due_date for t in EventTask.objects.all()))

    def test_marca_tarefa_pelo_javascript(self):
        t = EventTask.objects.create(event_key="creatorday", title="Fechar o espaço")
        r = self.client.post(f"/central/evento/tarefa/{t.pk}/feita/", HTTP_X_CENTRAL_FETCH="1")
        self.assertEqual(r.json(), {"feita": True, "feitas": 1, "total": 1})
        t.refresh_from_db()
        self.assertTrue(t.done and t.done_at)
        r = self.client.post(f"/central/evento/tarefa/{t.pk}/feita/")
        self.assertRedirects(r, "/central/#evento/tarefas", fetch_redirect_response=False)
        t.refresh_from_db()
        self.assertFalse(t.done)

    def test_roteiro_salva_horario(self):
        self.client.post("/central/evento/roteiro/salvar/", {"start": "14:00", "end": "14:30", "title": "Credenciamento"})
        item = EventScheduleItem.objects.get()
        self.assertEqual((item.start, item.end, item.event_key), (time(14, 0), time(14, 30), "creatorday"))

    def test_orcamento_conta_so_o_que_esta_fechado(self):
        Purchase.objects.create(product_key="creatorday", product_name="Creator Day Experience", amount=Decimal("120"),
                                status=Purchase.STATUS_APPROVED, customer_email="a@a.com", customer_name="A")
        EventSupplier.objects.create(event_key="creatorday", name="Espaço", category="local", status="pago", deal="pago", amount=Decimal("800"))
        EventSupplier.objects.create(event_key="creatorday", name="Buffet", category="comida", status="fechado", deal="pago",
                                     amount=Decimal("500"), paid_amount=Decimal("200"), due_date=timezone.localdate() - timedelta(days=1))
        EventSupplier.objects.create(event_key="creatorday", name="Foto", category="foto", status="orcamento", deal="pago", amount=Decimal("900"))
        EventSupplier.objects.create(event_key="creatorday", name="Marca X", category="skincare", status="fechado", deal="patrocinio", amount=Decimal("1000"))
        EventSupplier.objects.create(event_key="creatorday", name="Marca Y", category="skincare", status="fechado", deal="permuta")
        e = evento_snapshot({"receita": Decimal("120"), "pagas": 1}, 0)
        o = e["orcamento"]
        self.assertEqual((o["entradas"], o["custos"], o["ja_pago"], o["falta_pagar"], o["saldo"], o["em_cotacao"]),
                         ("R$ 1.120,00", "R$ 1.300,00", "R$ 1.000,00", "R$ 300,00", "− R$ 180,00", "R$ 900,00"))
        self.assertTrue(o["saldo_negativo"])
        self.assertEqual([p["obj"].name for p in e["pagamentos"]], ["Buffet"])
        self.assertTrue(e["pagamentos"][0]["vencido"])
        self.assertIn("Decoração e ambientação", e["categorias_sem"])
        self.assertNotIn("Comida e bebida", e["categorias_sem"])
        painel = self.client.get("/central/")
        self.assertContains(painel, "pagamento(s) de fornecedor do Creator Day vencido(s)")

    def test_tarefa_atrasada_aparece_nos_avisos(self):
        EventTask.objects.create(event_key="creatorday", title="Cotar comida", due_date=date(2020, 1, 1))
        painel = self.client.get("/central/")
        self.assertContains(painel, "tarefa(s) do Creator Day com prazo vencido")
        self.assertContains(painel, "Atrasada")
