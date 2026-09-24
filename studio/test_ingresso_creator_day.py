"""Ingresso personalizado do Creator Day e o e-mail novo da confirmação."""
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from .checkout import get_product
from .checkout_views import _approve_purchase
from .ingresso import codigo_do_ingresso, gerar_ingresso
from .models import Purchase


def _compra(**extra):
    dados = {
        "product_key": "creatorday",
        "product_name": "Creator Day Experience",
        "amount": Decimal("120.00"),
        "customer_name": "Juliana Silva",
        "customer_email": "juliana@example.com",
    }
    dados.update(extra)
    return Purchase.objects.create(**dados)


class IngressoTest(TestCase):
    def test_gera_png_no_tamanho_certo(self):
        png = gerar_ingresso("Juliana Silva", "CDX2026-0001")
        imagem = Image.open(BytesIO(png))
        self.assertEqual(imagem.format, "PNG")
        self.assertEqual(imagem.size, (1440, 1660))
        self.assertLess(len(png), 2_500_000, "ingresso pesado demais para anexar no e-mail")

    def test_nome_e_codigo_mudam_a_imagem(self):
        uma = gerar_ingresso("Juliana Silva", "CDX2026-0001")
        outra = gerar_ingresso("Maria Eduarda de Albuquerque", "CDX2026-0001")
        terceira = gerar_ingresso("Juliana Silva", "CDX2026-0042")
        self.assertNotEqual(uma, outra)
        self.assertNotEqual(uma, terceira)

    def test_nome_gigante_nao_estoura(self):
        png = gerar_ingresso("Maria Antonieta de Albuquerque Vasconcelos Nascimento", "CDX2026-0099")
        self.assertEqual(Image.open(BytesIO(png)).size, (1440, 1660))

    def test_codigo_vem_do_pedido(self):
        compra = _compra()
        self.assertEqual(codigo_do_ingresso(compra), f"CDX2026-{compra.pk:04d}")


@override_settings(CREATOR_DAY_EMAIL_INGRESSO=True)
class EmailComIngressoTest(TestCase):
    def test_compra_aprovada_manda_o_texto_novo_com_o_ingresso(self):
        compra = _compra()
        _approve_purchase(compra, {"id": "pay_cd", "payment_method_id": "pix"})

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, "Seu lugar na 2ª edição do Creator Day Experience está garantido")
        self.assertIn("Oi, oi, oiiii, diva!", email.body)
        self.assertIn("Glow Day", email.body)
        self.assertIn(f"CDX2026-{compra.pk:04d}", email.body)
        self.assertIn("Layfe Amorim", email.body)
        self.assertNotIn("—", email.body + email.subject)

        html, tipo_html = email.alternatives[0]
        self.assertEqual(tipo_html, "text/html")
        self.assertIn("Oi, oi, oiiii, diva!", html)
        self.assertIn("cid:ingresso", html)

        anexos = [a for a in email.attachments if isinstance(a, tuple)]
        embutidas = [a for a in email.attachments if not isinstance(a, tuple)]
        self.assertEqual(len(anexos), 1, "o ingresso precisa ir anexado")
        nome, conteudo, tipo = anexos[0]
        self.assertTrue(nome.startswith("ingresso-creator-day-juliana-silva"), nome)
        self.assertEqual(tipo, "image/png")
        self.assertEqual(Image.open(BytesIO(conteudo)).format, "PNG")
        self.assertEqual(len(embutidas), 1, "o ingresso também aparece dentro do e-mail")

    def test_falha_ao_montar_a_imagem_nao_derruba_o_email(self):
        compra = _compra()
        with patch("studio.ingresso.gerar_ingresso", side_effect=RuntimeError("quebrou")), self.assertLogs("studio.emails", level="ERROR"):
            _approve_purchase(compra, {"id": "pay_cd", "payment_method_id": "pix"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Oi, oi, oiiii, diva!", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].attachments, [])

    def test_comando_de_teste_manda_para_quem_pedir(self):
        call_command("testar_ingresso_creator_day", "david@example.com", nome="Layfe Amorim", pedido=7)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["david@example.com"])
        self.assertIn("CDX2026-0007", mail.outbox[0].body)
        anexos = [a for a in mail.outbox[0].attachments if isinstance(a, tuple)]
        self.assertTrue(anexos[0][0].startswith("ingresso-creator-day-layfe-amorim"), anexos[0][0])


class EmailSemIngressoTest(TestCase):
    @override_settings(CREATOR_DAY_EMAIL_INGRESSO=False)
    def test_desligado_continua_com_o_email_antigo(self):
        compra = _compra()
        _approve_purchase(compra, {"id": "pay_cd", "payment_method_id": "pix"})
        email = mail.outbox[0]
        self.assertEqual(email.subject, "Seu ingresso do Creator Day Experience está confirmado")
        self.assertEqual(email.attachments, [])
