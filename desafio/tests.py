from datetime import date, timedelta

from django.test import TestCase

from .models import CheckIn, Comentario, Conclusao, Missao, Participante, PontoEvento, Post
from .scoring import (
    avaliar_streak,
    pontuar_checkin,
    pontuar_comentario,
    pontuar_conclusao,
    pontuar_publicacao,
    ranking,
    total_de,
)


class DesafioScoringTest(TestCase):
    def setUp(self):
        self.paula = Participante.objects.create(nome="Paula", email="paula@example.com")
        self.bia = Participante.objects.create(nome="Bia", email="bia@example.com")
        self.missoes = [
            Missao.objects.create(dia=dia, titulo=f"Missao {dia}", data_liberacao=date(2026, 9, 13 + dia))
            for dia in range(1, 8)
        ]

    def _concluir(self, participante, missao, *, quando=None, comprovacao=""):
        conclusao = Conclusao.objects.create(
            participante=participante,
            missao=missao,
            comprovacao=comprovacao,
            concluida_em=quando or missao.data_liberacao,
        )
        pontuar_conclusao(conclusao)
        return conclusao

    # --- regras basicas -------------------------------------------------

    def test_publicacao_vale_5(self):
        pontuar_publicacao(Post.objects.create(participante=self.paula, texto="oi"))
        self.assertEqual(total_de(self.paula), 5)

    def test_checkin_vale_5_por_dia(self):
        for dia in (date(2026, 9, 14), date(2026, 9, 15)):
            pontuar_checkin(CheckIn.objects.create(participante=self.paula, data=dia))
        self.assertEqual(total_de(self.paula), 10)

    def test_missao_no_prazo_com_comprovacao_soma_35(self):
        # 20 (missao) + 10 (no prazo) + 5 (comprovacao)
        self._concluir(self.paula, self.missoes[0], comprovacao="https://instagram.com/p/x")
        self.assertEqual(total_de(self.paula), 35)

    def test_missao_atrasada_sem_comprovacao_soma_so_20(self):
        atrasada = self.missoes[0].data_liberacao + timedelta(days=3)
        self._concluir(self.paula, self.missoes[0], quando=atrasada)
        self.assertEqual(total_de(self.paula), 20)

    def test_comentario_em_post_de_outra_vale_2(self):
        post = Post.objects.create(participante=self.bia, texto="meu story")
        pontuar_comentario(Comentario.objects.create(post=post, participante=self.paula, texto="arrasou"))
        self.assertEqual(total_de(self.paula), 2)

    # --- regras que impedem farm de pontos -------------------------------

    def test_comentario_no_proprio_post_nao_pontua(self):
        post = Post.objects.create(participante=self.paula, texto="meu post")
        pontuar_comentario(Comentario.objects.create(post=post, participante=self.paula, texto="eu mesma"))
        self.assertEqual(total_de(self.paula), 0)

    def test_credito_da_missao_nao_dobra_ao_reenviar(self):
        """Anexar a comprovacao depois soma so os 5 novos, nao repete os 20+10."""
        conclusao = self._concluir(self.paula, self.missoes[0])
        self.assertEqual(total_de(self.paula), 30)

        conclusao.comprovacao = "https://instagram.com/p/x"
        conclusao.save(update_fields=["comprovacao"])
        pontuar_conclusao(conclusao)

        self.assertEqual(total_de(self.paula), 35)

    def test_publicacao_nao_credita_duas_vezes_o_mesmo_post(self):
        post = Post.objects.create(participante=self.paula, texto="oi")
        pontuar_publicacao(post)
        pontuar_publicacao(post)
        self.assertEqual(total_de(self.paula), 5)

    def test_checkin_repetido_no_mesmo_dia_nao_dobra(self):
        checkin = CheckIn.objects.create(participante=self.paula, data=date(2026, 9, 14))
        pontuar_checkin(checkin)
        pontuar_checkin(checkin)
        self.assertEqual(total_de(self.paula), 5)

    # --- streak ----------------------------------------------------------

    def test_streak_de_3_dias_seguidos_paga_7(self):
        for missao in self.missoes[:3]:
            self._concluir(self.paula, missao)
        # 3 missoes no prazo (90) + bonus de 3 dias (7)
        self.assertEqual(total_de(self.paula), 97)

    def test_streak_de_7_dias_acumula_os_tres_niveis(self):
        for missao in self.missoes:
            self._concluir(self.paula, missao)
        # 7 missoes no prazo (210) + 7 + 15 + 50 de streak
        self.assertEqual(total_de(self.paula), 282)

    def test_dias_nao_consecutivos_nao_geram_streak(self):
        self._concluir(self.paula, self.missoes[0])
        self._concluir(self.paula, self.missoes[2], quando=self.missoes[2].data_liberacao)
        self._concluir(self.paula, self.missoes[4], quando=self.missoes[4].data_liberacao)
        streak = self.paula.pontos.filter(tipo=PontoEvento.TIPO_STREAK)
        self.assertFalse(streak.exists())

    def test_streak_nao_paga_o_mesmo_nivel_duas_vezes(self):
        for missao in self.missoes[:3]:
            self._concluir(self.paula, missao)
        avaliar_streak(self.paula)
        avaliar_streak(self.paula)
        self.assertEqual(self.paula.pontos.filter(tipo=PontoEvento.TIPO_STREAK).count(), 1)

    # --- ranking ---------------------------------------------------------

    def test_ranking_ordena_por_pontos(self):
        self._concluir(self.paula, self.missoes[0], comprovacao="link")
        pontuar_publicacao(Post.objects.create(participante=self.bia, texto="oi"))

        placar = ranking()

        self.assertEqual(placar[0]["nome"], "Paula")
        self.assertEqual(placar[0]["posicao"], 1)
        self.assertEqual(placar[0]["total"], 35)
        self.assertEqual(placar[1]["nome"], "Bia")
        self.assertEqual(placar[1]["total"], 5)

    def test_ranking_inclui_quem_ainda_nao_pontuou(self):
        placar = ranking()
        self.assertEqual({linha["nome"] for linha in placar}, {"Paula", "Bia"})
        self.assertTrue(all(linha["total"] == 0 for linha in placar))


class DesafioModelTest(TestCase):
    def test_email_normalizado_no_cadastro(self):
        participante = Participante.objects.create(nome="Paula", email="  Paula@Example.COM ")
        self.assertEqual(participante.email, "paula@example.com")

    def test_codigo_de_acesso_gerado_automaticamente(self):
        participante = Participante.objects.create(nome="Paula", email="p@example.com")
        self.assertTrue(participante.codigo_acesso.startswith("DES-"))

    def test_mesma_missao_nao_pode_ser_concluida_duas_vezes(self):
        from django.db import IntegrityError

        participante = Participante.objects.create(nome="Paula", email="p@example.com")
        missao = Missao.objects.create(dia=1, titulo="M1", data_liberacao=date(2026, 9, 14))
        Conclusao.objects.create(participante=participante, missao=missao, concluida_em=date(2026, 9, 14))

        with self.assertRaises(IntegrityError):
            Conclusao.objects.create(participante=participante, missao=missao, concluida_em=date(2026, 9, 15))
