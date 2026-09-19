"""Foro e cidade do contrato do Jurídico: saem do CEP da creator, não de Salvador fixo."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from studio.models import Project, ServiceCategory
from studio.services import get_or_create_workspace_for_user
from studio.views import creator_city_state

SENHA = "SenhaForte123!"


class ForoDoContratoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("creator", email="creator@example.com", password=SENHA)
        self.ws = get_or_create_workspace_for_user(self.user)
        categoria = ServiceCategory.objects.create(workspace=self.ws, name="UGC")
        self.projeto = Project.objects.create(
            workspace=self.ws, company="Marca Teste", company_legal_name="Marca Teste LTDA",
            company_cnpj="12.345.678/0001-90", company_address="Rua A, 1", company_phone="(11) 90000-0000",
            service_category=categoria, deliverables_count=2, total_value=Decimal("1000"), entry_value=Decimal("500"),
            close_date=date(2026, 9, 1), due_date=date(2026, 9, 30),
        )
        self.client.force_login(self.user)

    def contrato(self) -> str:
        r = self.client.get(reverse("legal_contract_preview", args=[self.projeto.pk]))
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_usa_a_cidade_do_perfil(self):
        self.ws.business_city, self.ws.business_state = "São Paulo", "SP"
        self.ws.save()
        pagina = self.contrato()
        self.assertIn("foro da Comarca de São Paulo, Estado de São Paulo", pagina)
        self.assertIn("São Paulo/SP,", pagina)
        self.assertNotIn("Salvador", pagina)

    def test_artigo_do_estado_muda_conforme_a_uf(self):
        for cidade, uf, esperado in (("Salvador", "BA", "Estado da Bahia"), ("Fortaleza", "CE", "Estado do Ceará"),
                                     ("Curitiba", "PR", "Estado do Paraná"), ("Recife", "PE", "Estado de Pernambuco")):
            self.ws.business_city, self.ws.business_state = cidade, uf
            self.ws.save()
            self.assertIn(f"foro da Comarca de {cidade}, {esperado}", self.contrato())

    def test_so_com_cep_busca_a_cidade_uma_vez_e_guarda(self):
        self.ws.business_zip_code = "01310-100"
        self.ws.save()
        with patch("studio.views._viacep_lookup", return_value={"street": "Avenida Paulista", "zip_code": "01310-100", "city": "São Paulo", "state": "SP"}) as busca:
            pagina = self.contrato()
            self.contrato()
        self.assertEqual(busca.call_count, 1)
        self.ws.refresh_from_db()
        self.assertEqual((self.ws.business_city, self.ws.business_state), ("São Paulo", "SP"))
        self.assertIn("foro da Comarca de São Paulo", pagina)

    def test_sem_cidade_nao_inventa_salvador(self):
        pagina = self.contrato()
        self.assertIn("foro da comarca do domicílio da CONTRATADA", pagina)
        self.assertNotIn("Salvador", pagina)
        self.assertIn("Preencha o CEP em", pagina)

    def test_cep_sem_resposta_nao_quebra_o_contrato(self):
        self.ws.business_zip_code = "99999-999"
        self.ws.save()
        with patch("studio.views._viacep_lookup", return_value=None):
            self.assertIn("foro da comarca do domicílio da CONTRATADA", self.contrato())

    def test_pdf_sai_com_a_cidade_certa(self):
        self.ws.business_city, self.ws.business_state = "Belo Horizonte", "MG"
        self.ws.save()
        r = self.client.post(reverse("legal_contract_pdf", args=[self.projeto.pk]), {
            "company_legal_name": "Marca Teste LTDA", "company_cnpj": "12.345.678/0001-90",
            "company_address": "Rua A, 1", "company_phone": "(11) 90000-0000",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertGreater(len(r.content), 1000)

    def test_busca_de_cep_devolve_cidade_e_estado(self):
        with patch("studio.views._viacep_lookup", return_value={"street": "Avenida Paulista", "zip_code": "01310-100", "city": "São Paulo", "state": "SP"}):
            r = self.client.post(reverse("business_zip_lookup"), {"cep": "01310100"})
        self.assertEqual(r.json(), {"ok": True, "street": "Avenida Paulista", "zip_code": "01310-100", "city": "São Paulo", "state": "SP"})

    def test_perfil_salva_cidade_e_estado(self):
        r = self.client.post(reverse("profile"), {
            "profile_action": "business", "business_full_name": "Creator Teste", "business_zip_code": "01310-100",
            "business_street": "Avenida Paulista", "business_number": "1000", "business_complement": "",
            "business_city": "  São Paulo ", "business_state": "sp", "business_cnpj": "", "business_pis": "",
            "instagram_url": "", "tiktok_url": "", "portfolio_url": "",
        })
        self.assertIn(r.status_code, (200, 302))
        self.ws.refresh_from_db()
        self.assertEqual((self.ws.business_city, self.ws.business_state), ("São Paulo", "SP"))

    def test_creator_city_state_sem_cep_nao_chama_a_internet(self):
        with patch("studio.views._viacep_lookup") as busca:
            self.assertEqual(creator_city_state(self.ws), ("", ""))
        busca.assert_not_called()

    def test_contrato_antigo_continua_com_as_datas(self):
        self.ws.business_city, self.ws.business_state = "Salvador", "BA"
        self.ws.save()
        self.projeto.close_date = date.today() - timedelta(days=5)
        self.projeto.save()
        self.assertIn("Salvador/BA,", self.contrato())
