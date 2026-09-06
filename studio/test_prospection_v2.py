"""Testes da reorganizacao da Prospeccao: etapas novas, follow-up como acao,
Recuperacao com motivo, e o Dashboard de analise."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Prospect, ProspectEvent
from .services import get_or_create_workspace_for_user, prospection_attention, prospection_dashboard


class ProspeccaoPipelineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="creator", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)

    def marca(self, nome="Nivea", **extra):
        dados = {
            "workspace": self.workspace,
            "company": nome,
            "contact": "Marketing",
            "stage": "Primeiro Contato",
            "contact_date": date.today(),
        }
        dados.update(extra)
        return Prospect.objects.create(**dados)

    # ---------- etapas ----------

    def test_pipeline_tem_as_etapas_novas_na_ordem(self):
        resposta = self.client.get(reverse("prospection"))
        chaves = [c["key"] for c in resposta.context["pipeline_columns"]]
        self.assertEqual(
            chaves,
            [
                "Rascunho",
                "Primeiro Contato",
                "Qualificacao",
                "Proposta",
                "Follow-up",
                "Negociacao",
                "Fechado",
                "Recuperacao",
            ],
        )

    def test_cada_coluna_mostra_a_contagem(self):
        self.marca("Nivea")
        self.marca("Avon")
        self.marca("Dove", stage="Qualificacao")
        resposta = self.client.get(reverse("prospection"))
        contagens = {c["key"]: c["count"] for c in resposta.context["pipeline_columns"]}
        self.assertEqual(contagens["Primeiro Contato"], 2)
        self.assertEqual(contagens["Qualificacao"], 1)

    def test_mover_de_etapa_registra_no_historico(self):
        marca = self.marca()
        self.client.post(reverse("prospect_set_stage", args=[marca.pk]), {"stage": "Qualificacao"})
        marca.refresh_from_db()
        self.assertEqual(marca.stage, "Qualificacao")
        self.assertTrue(marca.events.filter(text__contains="Qualifica").exists())

    def test_entrar_em_proposta_carimba_a_data_de_envio(self):
        marca = self.marca()
        self.client.post(reverse("prospect_set_stage", args=[marca.pk]), {"stage": "Proposta"})
        marca.refresh_from_db()
        self.assertIsNotNone(marca.proposal_sent_at)

        # Volta e entra de novo: continua sendo a MESMA proposta.
        carimbo = marca.proposal_sent_at
        self.client.post(reverse("prospect_set_stage", args=[marca.pk]), {"stage": "Negociacao"})
        self.client.post(reverse("prospect_set_stage", args=[marca.pk]), {"stage": "Proposta"})
        marca.refresh_from_db()
        self.assertEqual(marca.proposal_sent_at, carimbo)

    # ---------- recuperacao ----------

    def test_recuperacao_exige_motivo(self):
        marca = self.marca()
        self.client.post(reverse("prospect_set_stage", args=[marca.pk]), {"stage": "Recuperacao"})
        marca.refresh_from_db()
        self.assertEqual(marca.stage, "Primeiro Contato")

    def test_recuperacao_com_motivo_grava_e_entra_no_historico(self):
        marca = self.marca()
        self.client.post(
            reverse("prospect_set_stage", args=[marca.pk]),
            {"stage": "Recuperacao", "recovery_reason": "sem_budget"},
        )
        marca.refresh_from_db()
        self.assertEqual(marca.stage, "Recuperacao")
        self.assertEqual(marca.recovery_reason, "sem_budget")
        self.assertIsNotNone(marca.recovery_at)
        self.assertTrue(marca.events.filter(text__contains="budget").exists())

    def test_sair_da_recuperacao_limpa_o_motivo(self):
        marca = self.marca(stage="Recuperacao", recovery_reason="orcamento", recovery_at=timezone.now())
        self.client.post(reverse("prospect_set_stage", args=[marca.pk]), {"stage": "Primeiro Contato"})
        marca.refresh_from_db()
        self.assertEqual(marca.recovery_reason, "")
        self.assertIsNone(marca.recovery_at)

    def test_recuperacao_nao_e_arquivo(self):
        """A marca em Recuperacao continua no painel, visivel e acionavel."""
        marca = self.marca(stage="Recuperacao", recovery_reason="sem_parcerias")
        resposta = self.client.get(reverse("prospection"))
        coluna = next(c for c in resposta.context["pipeline_columns"] if c["key"] == "Recuperacao")
        self.assertEqual(coluna["count"], 1)
        self.assertFalse(marca.is_archived)

    def test_reativar_do_arquivo_cai_em_recuperacao(self):
        marca = self.marca(archive_reason="sem_retorno", archived_at=timezone.now())
        self.client.post(reverse("prospect_reactivate", args=[marca.pk]))
        marca.refresh_from_db()
        self.assertEqual(marca.stage, "Recuperacao")
        self.assertEqual(marca.archive_reason, "")

    # ---------- follow-up como acao ----------

    def test_follow_up_nao_muda_a_etapa(self):
        marca = self.marca(stage="Proposta")
        self.client.post(reverse("prospect_follow_up", args=[marca.pk]), {"channel": "e-mail"})
        marca.refresh_from_db()
        self.assertEqual(marca.stage, "Proposta")
        self.assertTrue(marca.events.filter(kind=ProspectEvent.KIND_FOLLOW_UP).exists())

    def test_follow_up_zera_o_contador_de_dias_parados(self):
        antigo = timezone.now() - timedelta(days=20)
        marca = self.marca(stage="Proposta", stage_changed_at=antigo)
        self.client.post(reverse("prospect_follow_up", args=[marca.pk]))
        marca.refresh_from_db()
        self.assertGreater(marca.stage_changed_at, antigo)

    # ---------- retorno do primeiro contato ----------

    def test_retorno_do_contato_fica_no_card_sem_virar_coluna(self):
        marca = self.marca()
        self.client.post(reverse("prospect_outcome", args=[marca.pk]), {"contact_outcome": "email"})
        marca.refresh_from_db()
        self.assertEqual(marca.contact_outcome, "email")
        self.assertEqual(marca.stage, "Primeiro Contato")

        resposta = self.client.get(reverse("prospection"))
        chaves = [c["key"] for c in resposta.context["pipeline_columns"]]
        self.assertNotIn("email", chaves)


class ProspeccaoSemAutomacaoTests(TestCase):
    """As duas regras que moviam e arquivavam marca sozinhas foram removidas."""

    def setUp(self):
        self.user = User.objects.create_user(username="creator2", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)

    def test_marca_parada_nao_muda_de_etapa_sozinha(self):
        marca = Prospect.objects.create(
            workspace=self.workspace,
            company="Avon",
            contact="Marketing",
            stage="Primeiro Contato",
            last_activity_at=timezone.now() - timedelta(days=40),
            stage_changed_at=timezone.now() - timedelta(days=40),
        )
        self.client.get(reverse("prospection"))
        marca.refresh_from_db()
        self.assertEqual(marca.stage, "Primeiro Contato")

    def test_marca_antiga_nao_e_arquivada_sozinha(self):
        marca = Prospect.objects.create(
            workspace=self.workspace,
            company="Boticario",
            contact="Marketing",
            stage="Recuperacao",
            last_activity_at=timezone.now() - timedelta(days=200),
            stage_changed_at=timezone.now() - timedelta(days=200),
        )
        self.client.get(reverse("prospection"))
        marca.refresh_from_db()
        self.assertEqual(marca.archive_reason, "")

    def test_parada_vira_sugestao_no_dashboard(self):
        Prospect.objects.create(
            workspace=self.workspace,
            company="Natura",
            contact="Marketing",
            stage="Proposta",
            stage_changed_at=timezone.now() - timedelta(days=12),
        )
        atencao = prospection_attention(self.workspace)
        self.assertEqual(len(atencao["proposta_parada"]), 1)
        self.assertEqual(atencao["proposta_parada"][0]["company"], "Natura")


class ProspeccaoDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="creator3", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)

    def marca(self, nome, **extra):
        dados = {"workspace": self.workspace, "company": nome, "contact": "Marketing", "stage": "Primeiro Contato"}
        dados.update(extra)
        return Prospect.objects.create(**dados)

    def test_rascunho_nao_conta_como_prospectada(self):
        self.marca("Nivea", stage="Rascunho")
        self.marca("Avon")
        dados = prospection_dashboard(self.workspace)
        self.assertEqual(dados["total_prospectadas"], 1)
        self.assertEqual(dados["total_rascunho"], 1)

    def test_taxa_de_resposta_usa_o_retorno_registrado(self):
        self.marca("Nivea", contact_outcome="email")
        self.marca("Avon")
        dados = prospection_dashboard(self.workspace)
        self.assertEqual(dados["total_responderam"], 1)
        self.assertEqual(dados["taxa_resposta"], 50)

    def test_valor_gerado_e_ticket_medio_usam_o_valor_final(self):
        self.marca("Nivea", stage="Fechado", final_value=3000)
        self.marca("Avon", stage="Fechado", final_value=1000)
        dados = prospection_dashboard(self.workspace)
        self.assertEqual(dados["total_fechadas"], 2)
        self.assertEqual(int(dados["valor_gerado"]), 4000)
        self.assertEqual(int(dados["ticket_medio"]), 2000)

    def test_fechamento_antigo_sem_valor_final_cai_pro_valor_pedido(self):
        self.marca("Nivea", stage="Fechado", proposal_value=2500)
        dados = prospection_dashboard(self.workspace)
        self.assertEqual(int(dados["valor_gerado"]), 2500)

    def test_taxa_de_conversao_ignora_rascunho(self):
        self.marca("Nivea", stage="Rascunho")
        self.marca("Avon", stage="Fechado", final_value=100)
        self.marca("Dove")
        dados = prospection_dashboard(self.workspace)
        self.assertEqual(dados["taxa_conversao"], 50)

    def test_aba_dashboard_abre_com_os_grupos_de_atencao(self):
        resposta = self.client.get(reverse("prospection"), {"tab": "dashboard"})
        self.assertEqual(resposta.status_code, 200)
        chaves = [g["key"] for g in resposta.context["attention_groups"]]
        self.assertEqual(chaves, ["sem_resposta", "proposta_parada", "negociacao_parada", "para_reativar"])


class ProspeccaoConversaoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="creator4", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)

    def test_converter_em_trabalho_leva_o_valor_final(self):
        marca = Prospect.objects.create(
            workspace=self.workspace,
            company="Nivea",
            contact="Marketing",
            stage="Negociacao",
            proposal_value=3000,
            brand_offer_value=1800,
            final_value=2200,
        )
        resposta = self.client.get(reverse("prospect_convert", args=[marca.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context["form"].initial["received_value"], 2200)

    def test_sem_valor_final_leva_o_valor_pedido(self):
        marca = Prospect.objects.create(
            workspace=self.workspace,
            company="Avon",
            contact="Marketing",
            stage="Negociacao",
            proposal_value=1500,
        )
        resposta = self.client.get(reverse("prospect_convert", args=[marca.pk]))
        self.assertEqual(resposta.context["form"].initial["received_value"], 1500)


class ProspeccaoPainelSemRecorteDeMesTests(TestCase):
    """O painel ativo mostra toda prospeccao em andamento.

    Antes, o pipeline so trazia quem teve atividade no mes selecionado. Isso
    zerava a Recuperacao (que por definicao guarda marca parada ha tempo) e
    deixava o Dashboard apontando cards que o painel nao mostrava.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="creator5", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)
        self.antiga = Prospect.objects.create(
            workspace=self.workspace,
            company="Shein",
            contact="Marketing",
            stage="Recuperacao",
            recovery_reason="sem_parcerias",
            last_activity_at=timezone.now() - timedelta(days=95),
            stage_changed_at=timezone.now() - timedelta(days=95),
        )

    def test_marca_parada_ha_meses_continua_no_painel(self):
        resposta = self.client.get(reverse("prospection"))
        coluna = next(c for c in resposta.context["pipeline_columns"] if c["key"] == "Recuperacao")
        self.assertEqual(coluna["count"], 1)

    def test_painel_e_dashboard_falam_da_mesma_marca(self):
        resposta = self.client.get(reverse("prospection"))
        coluna = next(c for c in resposta.context["pipeline_columns"] if c["key"] == "Recuperacao")
        no_painel = {item["company"] for item in coluna["items"]}
        pra_reativar = {item["company"] for item in resposta.context["attention"]["para_reativar"]}
        self.assertIn("Shein", no_painel)
        self.assertIn("Shein", pra_reativar)


class ProspeccaoFechamentoTests(TestCase):
    """A coluna Fechados e o Dashboard tem que contar a mesma coisa.

    Arrastar pra Fechado arquiva com motivo "fechado"; fechar pelo botao so
    muda a etapa. Se a coluna olhasse so pro arquivo, o card sumiria da tela
    dependendo do caminho que a creator usou.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="creator6", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)

    def marca(self, nome, **extra):
        dados = {"workspace": self.workspace, "company": nome, "contact": "Marketing", "stage": "Negociacao"}
        dados.update(extra)
        return Prospect.objects.create(**dados)

    def test_coluna_fechados_conta_etapa_e_arquivo(self):
        self.marca("Nike", stage="Fechado", final_value=5000)
        self.marca("Adidas", stage="Negociacao", archive_reason="fechado", final_value=3000)

        resposta = self.client.get(reverse("prospection"))
        coluna = next(c for c in resposta.context["pipeline_columns"] if c["key"] == "Fechado")
        self.assertEqual(coluna["count"], 2)

    def test_coluna_fechados_bate_com_o_dashboard(self):
        self.marca("Nike", stage="Fechado", final_value=5000)
        self.marca("Adidas", stage="Negociacao", archive_reason="fechado", final_value=3000)

        resposta = self.client.get(reverse("prospection"))
        coluna = next(c for c in resposta.context["pipeline_columns"] if c["key"] == "Fechado")
        self.assertEqual(coluna["count"], resposta.context["dashboard"]["total_fechadas"])

    def test_marca_descartada_nao_entra_em_fechados(self):
        self.marca("Shein", archive_reason="sem_retorno")
        resposta = self.client.get(reverse("prospection"))
        coluna = next(c for c in resposta.context["pipeline_columns"] if c["key"] == "Fechado")
        self.assertEqual(coluna["count"], 0)


class ProspeccaoNumerosCoerentesTests(TestCase):
    """A barra de conversao do topo e o Dashboard contam a mesma coisa.

    Existiam duas definicoes de "abordagem" na mesma tela: uma incluia
    Rascunho, a outra nao, e a barra chegava a dizer "0 fechados de 14" ao
    lado de um KPI marcando 1 fechado.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="creator7", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)
        Prospect.objects.create(workspace=self.workspace, company="Nivea", contact="M", stage="Rascunho")
        Prospect.objects.create(workspace=self.workspace, company="Avon", contact="M", stage="Primeiro Contato")
        Prospect.objects.create(
            workspace=self.workspace, company="Nike", contact="M", stage="Fechado", final_value=5000
        )

    def test_barra_de_conversao_bate_com_o_dashboard(self):
        resposta = self.client.get(reverse("prospection"))
        painel = resposta.context["dashboard"]
        self.assertEqual(resposta.context["conversion_rate"], painel["taxa_conversao"])
        self.assertEqual(resposta.context["total_closed"], painel["total_fechadas"])
        self.assertEqual(resposta.context["total_addressed"], painel["total_prospectadas"])

    def test_rascunho_nao_conta_como_abordagem_no_topo(self):
        resposta = self.client.get(reverse("prospection"))
        self.assertEqual(resposta.context["total_addressed"], 2)
        self.assertEqual(resposta.context["conversion_rate"], 50)

    def test_barra_bate_com_a_coluna_de_fechados(self):
        resposta = self.client.get(reverse("prospection"))
        coluna = next(c for c in resposta.context["pipeline_columns"] if c["key"] == "Fechado")
        self.assertEqual(resposta.context["total_closed"], coluna["count"])


class ProspeccaoArquivadasTests(TestCase):
    """As marcas que a antiga regra automatica enterrou nao voltam sozinhas,
    mas precisam estar visiveis: sao a fila natural de recuperacao."""

    def setUp(self):
        self.user = User.objects.create_user(username="creator8", password="segura123")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)
        for nome in ("Shein", "Amaro", "Renner"):
            Prospect.objects.create(
                workspace=self.workspace,
                company=nome,
                contact="Marketing",
                stage="Recuperacao",
                archive_reason="sem_retorno",
                archived_at=timezone.now(),
            )

    def test_dashboard_conta_as_arquivadas_por_falta_de_retorno(self):
        dados = prospection_dashboard(self.workspace)
        self.assertEqual(dados["total_arquivadas_sem_retorno"], 3)

    def test_arquivadas_nao_voltam_sozinhas_pro_painel(self):
        resposta = self.client.get(reverse("prospection"))
        coluna = next(c for c in resposta.context["pipeline_columns"] if c["key"] == "Recuperacao")
        self.assertEqual(coluna["count"], 0)

    def test_dashboard_aponta_onde_encontrar_as_arquivadas(self):
        resposta = self.client.get(reverse("prospection"), {"tab": "dashboard"})
        self.assertContains(resposta, "?tab=banco&amp;banco_status=sem_retorno")

    def test_contatos_lista_as_arquivadas_pelo_filtro(self):
        resposta = self.client.get(
            reverse("prospection"), {"tab": "banco", "banco_status": "sem_retorno"}
        )
        self.assertEqual(len(resposta.context["archived_rows"]), 3)
