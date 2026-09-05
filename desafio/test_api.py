import json
from datetime import date, timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Conclusao, Missao, Participante, Post
from .scoring import total_de


class DesafioApiTest(TestCase):
    def setUp(self):
        hoje = timezone.localdate()
        # Missao 1 ja liberada (ontem), missao 2 ainda bloqueada (amanha).
        self.liberada = Missao.objects.create(dia=1, titulo="Arrumando a casa", data_liberacao=hoje - timedelta(days=1))
        self.bloqueada = Missao.objects.create(dia=2, titulo="Construção de Intenção", data_liberacao=hoje + timedelta(days=1))

    def _post(self, url, payload=None, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return self.client.post(url, data=json.dumps(payload or {}), content_type="application/json", **headers)

    def _inscrever(self, nome="Paula", email="paula@example.com"):
        resposta = self._post(reverse("desafio_cadastro"), {"nome": nome, "email": email, "whatsapp": "11999999999"})
        corpo = resposta.json()
        return corpo["token"], Participante.objects.get(email=email)

    # --- cadastro e login ------------------------------------------------

    def test_cadastro_cria_participante_e_envia_codigo(self):
        resposta = self._post(reverse("desafio_cadastro"), {"nome": "Paula", "email": "Paula@Example.com"})

        self.assertEqual(resposta.status_code, 201)
        participante = Participante.objects.get(email="paula@example.com")
        self.assertTrue(participante.codigo_acesso.startswith("DES-"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(participante.codigo_acesso, mail.outbox[0].body)

    def test_cadastro_repetido_reenvia_codigo_em_vez_de_barrar(self):
        self._inscrever()
        mail.outbox.clear()

        resposta = self._post(reverse("desafio_cadastro"), {"nome": "Paula", "email": "paula@example.com"})

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.json()["ja_inscrita"])
        self.assertEqual(Participante.objects.filter(email="paula@example.com").count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_cadastro_exige_nome_e_email(self):
        self.assertEqual(self._post(reverse("desafio_cadastro"), {"nome": "", "email": ""}).status_code, 400)
        self.assertEqual(self._post(reverse("desafio_cadastro"), {"nome": "Paula", "email": "nao-e-email"}).status_code, 400)

    def test_login_com_email_e_codigo(self):
        _, participante = self._inscrever()

        resposta = self._post(
            reverse("desafio_login"), {"email": participante.email, "codigo": participante.codigo_acesso.lower()}
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIn("token", resposta.json())

    def test_login_com_codigo_errado_falha(self):
        _, participante = self._inscrever()
        resposta = self._post(reverse("desafio_login"), {"email": participante.email, "codigo": "DES-XXXXX"})
        self.assertEqual(resposta.status_code, 401)

    def test_reenviar_codigo_nao_revela_se_email_existe(self):
        self._inscrever()
        mail.outbox.clear()

        inscrita = self._post(reverse("desafio_reenviar_codigo"), {"email": "paula@example.com"})
        nao_inscrita = self._post(reverse("desafio_reenviar_codigo"), {"email": "ninguem@example.com"})

        self.assertEqual(inscrita.json(), nao_inscrita.json())
        self.assertEqual(len(mail.outbox), 1)  # so a inscrita recebe de fato

    # --- protecao das rotas ----------------------------------------------

    def test_estado_exige_autenticacao(self):
        self.assertEqual(self.client.get(reverse("desafio_estado")).status_code, 401)

    def test_token_invalido_recusado(self):
        resposta = self.client.get(reverse("desafio_estado"), HTTP_AUTHORIZATION="Bearer nao-e-token")
        self.assertEqual(resposta.status_code, 401)

    # --- missoes -----------------------------------------------------------

    def test_concluir_missao_liberada_pontua(self):
        token, participante = self._inscrever()

        resposta = self._post(
            reverse("desafio_concluir_missao", args=[1]), {"comprovacao": "https://instagram.com/p/x"}, token=token
        )

        self.assertEqual(resposta.status_code, 200)
        # 20 (missao) + 5 (comprovacao). Sem bonus de prazo: liberou ontem.
        self.assertEqual(total_de(participante), 25)

    def test_nao_da_pra_concluir_missao_bloqueada(self):
        token, participante = self._inscrever()

        resposta = self._post(reverse("desafio_concluir_missao", args=[2]), {}, token=token)

        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Conclusao.objects.filter(participante=participante).exists())
        self.assertEqual(total_de(participante), 0)

    def test_anexar_comprovacao_depois_soma_so_o_bonus(self):
        token, participante = self._inscrever()
        self._post(reverse("desafio_concluir_missao", args=[1]), {}, token=token)
        self.assertEqual(total_de(participante), 20)

        self._post(reverse("desafio_concluir_missao", args=[1]), {"comprovacao": "link"}, token=token)

        self.assertEqual(total_de(participante), 25)

    # --- comunidade --------------------------------------------------------

    def test_publicar_pontua_e_aparece_no_feed(self):
        token, participante = self._inscrever()

        self._post(reverse("desafio_publicar"), {"texto": "arrumei meu perfil hoje"}, token=token)

        self.assertEqual(total_de(participante), 5)
        estado = self.client.get(reverse("desafio_estado"), HTTP_AUTHORIZATION=f"Bearer {token}").json()
        self.assertEqual(estado["feed"][0]["texto"], "arrumei meu perfil hoje")

    def test_comentario_em_post_de_outra_pontua_uma_vez_so(self):
        token_paula, paula = self._inscrever()
        token_bia, bia = self._inscrever(nome="Bia", email="bia@example.com")
        post = Post.objects.create(participante=bia, texto="meu story")

        self._post(reverse("desafio_comentar", args=[post.pk]), {"texto": "arrasou"}, token=token_paula)
        self._post(reverse("desafio_comentar", args=[post.pk]), {"texto": "de novo"}, token=token_paula)

        self.assertEqual(total_de(paula), 2)

    # --- check-in e ranking -------------------------------------------------

    def test_checkin_pontua_uma_vez_por_dia(self):
        token, participante = self._inscrever()

        self._post(reverse("desafio_checkin"), {}, token=token)
        segunda = self._post(reverse("desafio_checkin"), {}, token=token)

        self.assertTrue(segunda.json()["ja_registrado"])
        self.assertEqual(total_de(participante), 5)

    def test_ranking_publico_lista_participantes(self):
        token, _ = self._inscrever()
        self._post(reverse("desafio_publicar"), {"texto": "primeira publicacao"}, token=token)

        resposta = self.client.get(reverse("desafio_ranking"))

        self.assertEqual(resposta.status_code, 200)
        placar = resposta.json()["ranking"]
        self.assertEqual(placar[0]["nome"], "Paula")
        self.assertEqual(placar[0]["total"], 5)

    def test_estado_traz_missoes_com_status_de_liberacao(self):
        token, _ = self._inscrever()

        estado = self.client.get(reverse("desafio_estado"), HTTP_AUTHORIZATION=f"Bearer {token}").json()

        por_dia = {m["dia"]: m for m in estado["missoes"]}
        self.assertTrue(por_dia[1]["liberada"])
        self.assertFalse(por_dia[2]["liberada"])
