"""Testes da feature de Infoprodutos: produtos, entradas (vendas) e edição."""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from studio.models import InfoProduct, InfoProductSale
from studio.services import get_or_create_workspace_for_user, infoproducts_snapshot

User = get_user_model()


class InfoproductsTest(TestCase):
    def setUp(self):
        # username com "layfeamorim" garante acesso a infoprodutos.
        self.user = User.objects.create_user(username="layfeamorim", password="x123456")
        self.workspace = get_or_create_workspace_for_user(self.user)
        self.client.force_login(self.user)
        self.product = InfoProduct.objects.create(
            workspace=self.workspace, name="Mentoria Creator",
            product_type=InfoProduct.TYPE_MENTORSHIP, status=InfoProduct.STATUS_ACTIVE,
            price=697, platform="Hubla", access_duration="6_months", track_progress=True,
        )

    def test_page_loads_and_lists_products_in_dropdown(self):
        resp = self.client.get(reverse("infoproducts"))
        self.assertEqual(resp.status_code, 200)
        # produto disponível para o dropdown de entrada + autofill
        opts = [o["name"] for o in resp.context["product_options"]]
        self.assertIn("Mentoria Creator", opts)
        self.assertIn(str(self.product.id), resp.context["product_autofill"])
        self.assertEqual(resp.context["product_autofill"][str(self.product.id)]["platform"], "Hubla")

    def test_register_sale_creates_entry(self):
        resp = self.client.post(reverse("infoproducts"), {
            "infoproduct_action": "create_sale",
            "product": self.product.id,
            "buyer_name": "Maria Silva",
            "buyer_email": "maria@email.com",
            "platform": "Hubla",
            "amount": "697,00",
            "sale_date": date.today().isoformat(),
            "status": InfoProductSale.STATUS_CONFIRMED,
            "progress": "0",
        })
        self.assertRedirects(resp, reverse("infoproducts"))
        sale = InfoProductSale.objects.get(workspace=self.workspace, buyer_name="Maria Silva")
        self.assertEqual(str(sale.amount), "697.00")
        # aparece nas entradas e na receita
        snap = infoproducts_snapshot(self.workspace)
        self.assertEqual(len(snap["entries"]), 1)
        self.assertEqual(snap["kpis"][1]["value"], "R$697")

    def test_edit_product_prefills_modal(self):
        resp = self.client.get(reverse("infoproducts"), {"edit": self.product.id})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["open_product_modal"])
        self.assertEqual(resp.context["editing_product"], self.product)
        # form vem preenchido com o valor atual
        self.assertEqual(resp.context["product_form"]["name"].value(), "Mentoria Creator")

    def test_update_product_saves(self):
        resp = self.client.post(reverse("infoproducts"), {
            "infoproduct_action": "update_product",
            "product_id": self.product.id,
            "name": "Mentoria Creator PRO",
            "product_type": InfoProduct.TYPE_MENTORSHIP,
            "status": InfoProduct.STATUS_ACTIVE,
            "price": "997,00",
            "platform": "Hubla",
            "access_duration": "6_months",
            "track_progress": "on",
        })
        self.assertRedirects(resp, reverse("infoproducts"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Mentoria Creator PRO")
        self.assertEqual(str(self.product.price), "997.00")

    def test_month_filter_in_context(self):
        resp = self.client.get(reverse("infoproducts"))
        self.assertIn("month_choices", resp.context)
        self.assertIn("selected_month", resp.context)
