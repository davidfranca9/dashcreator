"""Testes da API do painel da organizadora."""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from . import scoring
from .models import CheckIn, Comentario, Conclusao, Missao, Participante, PontoEvento, Post


class AdminApiTests(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.staff = get_user_model().objects.create_user(
            username="organizadora", password="senha-forte-123", is_staff=True
        )
        self.comum = get_user_model().objects.create_user(username="qualquer", password="senha-forte-123")

        self.ana = Participante.objects.create(nome="Ana Souza", email="ana@example.com")
        self.bia = Participante.objects.create(nome="Bia Lima", email="bia@example.com", indicada_por=self.ana)
        self.missao = Missao.objects.create(dia=1, titulo="Arrumando a casa", data_liberacao=self.hoje)

    # ---------- helpers ----------

    def entrar(self, usuario="organizadora", senha="senha-forte-123"):
        resposta = self.client.post(
            "/desafio/api/admin/login/",
            data=json.dumps({"usuario": usuario, "senha": senha}),
            content_type="application/json",
        )
        return resposta

    def com_token(self):
        token = self.entrar().json()["token"]
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def post_json(self, url, corpo=None, **extra):
        return self.client.post(url, data=json.dumps(corpo or {}), content_type="application/json", **extra)

    # ---------- login ----------

    def test_login_de_staff_devolve_token(self):
        resposta = self.entrar()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("token", resposta.json())

    def test_login_com_senha_errada_e_recusado(self):
        self.assertEqual(self.entrar(senha="errada").status_code, 401)

    def test_usuario_sem_staff_nao_entra_no_painel(self):
        self.assertEqual(self.entrar(usuario="qualquer").status_code, 401)

    def test_mensagem_de_erro_nao_revela_se_o_usuario_existe(self):
        inexistente = self.entrar(usuario="ninguem").json()["erro"]
        senha_errada = self.entrar(senha="errada").json()["erro"]
        self.assertEqual(inexistente, senha_errada)

    def test_painel_sem_token_e_bloqueado(self):
        self.assertEqual(self.client.get("/desafio/api/admin/painel/").status_code, 401)

    def test_token_de_participante_nao_serve_no_painel(self):
        cadastro = self.post_json(
            "/desafio/api/cadastro/", {"nome": "Carla", "email": "carla@example.com"}
        ).json()
        resposta = self.client.get(
            "/desafio/api/admin/painel/", HTTP_AUTHORIZATION=f"Bearer {cadastro['token']}"
        )
        self.assertEqual(resposta.status_code, 401)

    # ---------- painel ----------

    def test_painel_traz_metricas_ranking_e_listas(self):
        CheckIn.objects.create(participante=self.ana, data=self.hoje)
        post = Post.objects.create(participante=self.ana, texto="Bom dia!")
        Comentario.objects.create(post=post, participante=self.bia, texto="Arrasou")
        conclusao = Conclusao.objects.create(
            participante=self.ana, missao=self.missao, comprovacao="https://instagram.com/p/x", concluida_em=self.hoje
        )
        scoring.pontuar_conclusao(conclusao)

        dados = self.client.get("/desafio/api/admin/painel/", **self.com_token()).json()

        self.assertEqual(dados["metricas"]["inscritas"], 2)
        self.assertEqual(dados["metricas"]["checkins_hoje"], 1)
        self.assertEqual(dados["metricas"]["indicacoes"], 1)
        self.assertEqual(dados["metricas"]["posts"], 1)
        self.assertEqual(dados["metricas"]["comentarios"], 1)
        self.assertEqual(len(dados["ranking"]), 2)
        self.assertEqual(len(dados["comprovacoes"]), 1)
        self.assertEqual(dados["comprovacoes"][0]["participante"], "Ana Souza")
        self.assertEqual(len(dados["mural"]), 1)
        self.assertEqual(len(dados["mural"][0]["comentarios"]), 1)

    def test_painel_conta_missao_sem_inflar_com_o_join(self):
        """Somar pontos e contar check-in na mesma query multiplicaria as linhas."""
        for dia in range(3):
            CheckIn.objects.create(participante=self.ana, data=self.hoje - timedelta(days=dia))
        conclusao = Conclusao.objects.create(participante=self.ana, missao=self.missao, concluida_em=self.hoje)
        scoring.pontuar_conclusao(conclusao)

        dados = self.client.get("/desafio/api/admin/painel/", **self.com_token()).json()
        ana = next(p for p in dados["participantes"] if p["id"] == self.ana.pk)

        self.assertEqual(ana["checkins"], 3)
        self.assertEqual(ana["missoes"], 1)
        self.assertEqual(ana["pontos"], scoring.total_de(self.ana))

    def test_painel_mostra_quem_indicou_cada_participante(self):
        dados = self.client.get("/desafio/api/admin/painel/", **self.com_token()).json()
        bia = next(p for p in dados["participantes"] if p["id"] == self.bia.pk)
        self.assertEqual(bia["indicada_por"], "Ana Souza")

    def test_missao_traz_progresso_sobre_o_total_de_ativas(self):
        conclusao = Conclusao.objects.create(participante=self.ana, missao=self.missao, concluida_em=self.hoje)
        scoring.pontuar_conclusao(conclusao)

        dados = self.client.get("/desafio/api/admin/painel/", **self.com_token()).json()
        missao = dados["missoes"][0]

        self.assertEqual(missao["concluidas"], 1)
        self.assertEqual(missao["no_prazo"], 1)
        self.assertEqual(missao["total_ativas"], 2)

    # ---------- ajuste de pontos ----------

    def test_organizadora_pode_lancar_pontos(self):
        resposta = self.post_json(
            "/desafio/api/admin/pontos/",
            {"participante_id": self.ana.pk, "pontos": 15, "motivo": "entregou por WhatsApp"},
            **self.com_token(),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(scoring.total_de(self.ana), 15)

    def test_pode_tirar_ponto_com_valor_negativo(self):
        self.post_json("/desafio/api/admin/pontos/", {"participante_id": self.ana.pk, "pontos": 20}, **self.com_token())
        self.post_json("/desafio/api/admin/pontos/", {"participante_id": self.ana.pk, "pontos": -5}, **self.com_token())
        self.assertEqual(scoring.total_de(self.ana), 15)

    def test_dois_ajustes_iguais_entram_os_dois(self):
        """A trava de idempotencia protege os pontos automaticos, mas nao pode
        engolir um segundo lancamento manual identico."""
        corpo = {"participante_id": self.ana.pk, "pontos": 10, "motivo": "bonus"}
        self.post_json("/desafio/api/admin/pontos/", corpo, **self.com_token())
        self.post_json("/desafio/api/admin/pontos/", corpo, **self.com_token())
        self.assertEqual(scoring.total_de(self.ana), 20)

    def test_ajuste_fica_registrado_no_extrato(self):
        self.post_json(
            "/desafio/api/admin/pontos/",
            {"participante_id": self.ana.pk, "pontos": 7, "motivo": "caso especial"},
            **self.com_token(),
        )
        evento = PontoEvento.objects.get(participante=self.ana)
        self.assertEqual(evento.tipo, PontoEvento.TIPO_AJUSTE)
        self.assertIn("caso especial", evento.referencia)

    def test_ajuste_de_zero_e_recusado(self):
        resposta = self.post_json(
            "/desafio/api/admin/pontos/", {"participante_id": self.ana.pk, "pontos": 0}, **self.com_token()
        )
        self.assertEqual(resposta.status_code, 400)

    def test_ajuste_em_participante_inexistente_devolve_404(self):
        resposta = self.post_json(
            "/desafio/api/admin/pontos/", {"participante_id": 9999, "pontos": 5}, **self.com_token()
        )
        self.assertEqual(resposta.status_code, 404)

    # ---------- participante ----------

    def test_desativar_tira_do_ranking_e_reativar_devolve(self):
        scoring.pontuar_checkin(CheckIn.objects.create(participante=self.ana, data=self.hoje))
        url = f"/desafio/api/admin/participantes/{self.ana.pk}/alternar/"

        self.post_json(url, {}, **self.com_token())
        self.assertFalse(Participante.objects.get(pk=self.ana.pk).ativa)
        self.assertNotIn(self.ana.pk, [linha["participante_id"] for linha in scoring.ranking()])

        self.post_json(url, {}, **self.com_token())
        self.assertTrue(Participante.objects.get(pk=self.ana.pk).ativa)
        self.assertIn(self.ana.pk, [linha["participante_id"] for linha in scoring.ranking()])

    def test_desativar_preserva_os_pontos_da_participante(self):
        scoring.pontuar_checkin(CheckIn.objects.create(participante=self.ana, data=self.hoje))
        self.post_json(f"/desafio/api/admin/participantes/{self.ana.pk}/alternar/", {}, **self.com_token())
        self.assertEqual(scoring.total_de(self.ana), 5)

    # ---------- missoes ----------

    def test_mudar_data_de_liberacao(self):
        nova = self.hoje + timedelta(days=5)
        resposta = self.post_json(
            f"/desafio/api/admin/missoes/{self.missao.dia}/data/",
            {"data_liberacao": nova.isoformat()},
            **self.com_token(),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Missao.objects.get(pk=self.missao.pk).data_liberacao, nova)

    def test_data_invalida_e_recusada(self):
        resposta = self.post_json(
            f"/desafio/api/admin/missoes/{self.missao.dia}/data/", {"data_liberacao": "14-09"}, **self.com_token()
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertEqual(Missao.objects.get(pk=self.missao.pk).data_liberacao, self.hoje)

    # ---------- moderacao ----------

    def test_remover_post_e_comentario(self):
        post = Post.objects.create(participante=self.ana, texto="Publicação fora do tema")
        comentario = Comentario.objects.create(post=post, participante=self.bia, texto="comentário ruim")

        self.post_json(f"/desafio/api/admin/comentarios/{comentario.pk}/remover/", {}, **self.com_token())
        self.assertFalse(Comentario.objects.filter(pk=comentario.pk).exists())

        self.post_json(f"/desafio/api/admin/posts/{post.pk}/remover/", {}, **self.com_token())
        self.assertFalse(Post.objects.filter(pk=post.pk).exists())

    def test_remover_post_mantem_os_pontos_de_quem_comentou(self):
        post = Post.objects.create(participante=self.ana, texto="Publicação")
        scoring.pontuar_publicacao(post)
        comentario = Comentario.objects.create(post=post, participante=self.bia, texto="oi")
        scoring.pontuar_comentario(comentario)

        self.post_json(f"/desafio/api/admin/posts/{post.pk}/remover/", {}, **self.com_token())
        self.assertEqual(scoring.total_de(self.bia), 2)

    def test_moderacao_exige_login(self):
        post = Post.objects.create(participante=self.ana, texto="Publicação")
        self.assertEqual(self.post_json(f"/desafio/api/admin/posts/{post.pk}/remover/").status_code, 401)
        self.assertTrue(Post.objects.filter(pk=post.pk).exists())
