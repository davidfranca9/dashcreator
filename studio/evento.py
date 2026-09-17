"""Gestão do Creator Day Experience na Central (aba Creator Day).

Fornecedores e parceiros, orçamento, checklist de tarefas e roteiro do dia,
tudo cadastrado pelo time na própria Central. Os ingressos vêm do checkout
(studio/creator_day.py) e entram no orçamento sozinhos.
"""
from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal, InvalidOperation

from django import forms
from django.utils import timezone

from .creator_day import CREATOR_DAY_EVENT, brl, whatsapp_link
from .models import EventScheduleItem, EventSupplier, EventTask

EVENTO = {
    "chave": CREATOR_DAY_EVENT,
    "nome": "Creator Day Experience",
    "data": date(2026, 10, 17),
    "hora": "14h",
    "local": "Piatã, Salvador/BA",
    "tema": "Skincare e cuidados com a pele",
    "ingresso": "R$ 120,00",
    "whatsapp": "(71) 9 9723-8419",
}

# Situações que já viraram compromisso (entram no orçamento) e as que ainda são cotação.
FECHADOS = {"fechado", "pago"}
EM_COTACAO = {"cotar", "orcamento", "negociando"}
TOM_SITUACAO = {"cotar": "neutro", "orcamento": "info", "negociando": "espera", "fechado": "ok", "pago": "ok", "cancelado": "erro"}

CHECKLIST_SUGERIDO = [
    ("local", "Fechar o espaço em Piatã e confirmar o endereço exato", -45),
    ("local", "Visitar o espaço: tomadas, banheiros, luz natural e plano B para chuva", -30),
    ("fornecedores", "Cotar comida e bebida (pelo menos 3 orçamentos)", -40),
    ("fornecedores", "Fechar foto e vídeo do evento", -30),
    ("fornecedores", "Fechar decoração e ambientação", -25),
    ("fornecedores", "Convidar marcas de skincare para parceria ou permuta", -40),
    ("kit", "Definir o kit de boas-vindas e pedir os brindes", -25),
    ("divulgacao", "Calendário de posts e stories até o evento", -35),
    ("divulgacao", "Convidar creators locais", -30),
    ("vendas", "Acompanhar quem não finalizou a compra e chamar no WhatsApp", -20),
    ("vendas", "Mandar informações finais para quem comprou (endereço, horário, o que levar)", -3),
    ("programacao", "Fechar o roteiro do dia e quem conduz cada momento", -14),
    ("dia", "Montar lista de presença e credenciamento", -2),
    ("dia", "Separar kit de apoio: extensão, fita, tesoura, lenço, carregador", -1),
    ("pos", "Mandar agradecimento e fotos para quem participou", 3),
    ("pos", "Pagar o que faltar e fechar as contas do evento", 7),
]

ROTEIRO_SUGERIDO = [
    (time(14, 0), time(14, 30), "Chegada e credenciamento", "Entrega do kit e foto na entrada"),
    (time(14, 30), time(15, 0), "Boas-vindas", "Abertura com a Layfe e apresentação da tarde"),
    (time(15, 0), time(16, 0), "Skincare guiado", "Experiência com as marcas parceiras"),
    (time(16, 0), time(16, 45), "Pausa e conexões", "Comida, bebida e tempo para conversar"),
    (time(16, 45), time(17, 30), "Troca de conhecimento", "Roda de conversa sobre criação de conteúdo"),
    (time(17, 30), time(18, 0), "Momento de desacelerar", "Atividade guiada de encerramento"),
    (time(18, 0), time(18, 30), "Fotos e encerramento", "Fotos da turma e despedida"),
]


class ValorField(forms.DecimalField):
    """Aceita valor do jeito brasileiro: 1.500,00, 1500,5 ou R$ 1500."""

    def to_python(self, value):
        if isinstance(value, str):
            texto = value.replace("R$", "").replace(" ", "").strip()
            if "," in texto:
                texto = texto.replace(".", "").replace(",", ".")
            value = texto
        try:
            return super().to_python(value)
        except forms.ValidationError:
            raise forms.ValidationError("Valor inválido. Use por exemplo 1.500,00.")


class FornecedorForm(forms.ModelForm):
    amount = ValorField(required=False, max_digits=10, decimal_places=2, min_value=0)
    paid_amount = ValorField(required=False, max_digits=10, decimal_places=2, min_value=0)

    class Meta:
        model = EventSupplier
        fields = ["name", "category", "delivers", "contact_name", "whatsapp", "email", "instagram",
                  "status", "deal", "amount", "paid_amount", "due_date", "notes"]

    def clean_paid_amount(self):
        return self.cleaned_data.get("paid_amount") or Decimal("0")

    def clean_instagram(self):
        return (self.cleaned_data.get("instagram") or "").strip().lstrip("@")


class TarefaForm(forms.ModelForm):
    class Meta:
        model = EventTask
        fields = ["title", "area", "owner", "due_date", "notes"]


class RoteiroForm(forms.ModelForm):
    class Meta:
        model = EventScheduleItem
        fields = ["start", "end", "title", "owner", "details"]


def _decimal(valor) -> Decimal:
    try:
        return Decimal(valor or 0)
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _pago(f: EventSupplier) -> Decimal:
    """Quanto já saiu para o fornecedor. Situação "Pago" conta como quitado."""
    if f.status == "pago" and f.amount is not None:
        return _decimal(f.amount)
    if f.amount is None:
        return _decimal(f.paid_amount)
    return min(_decimal(f.paid_amount), _decimal(f.amount))


def _valor_campo(valor) -> str:
    """Decimal para o campo do formulário: 1500.00 -> 1.500,00."""
    return brl(valor).removeprefix("R$ ") if valor is not None else ""


def criar_sugestao(tipo: str) -> int:
    """Cria o checklist ou o roteiro sugerido, só se ainda estiver vazio."""
    chave = EVENTO["chave"]
    if tipo == "tarefas" and not EventTask.objects.filter(event_key=chave).exists():
        EventTask.objects.bulk_create([
            EventTask(event_key=chave, area=area, title=titulo, due_date=EVENTO["data"] + timedelta(days=dias))
            for area, titulo, dias in CHECKLIST_SUGERIDO
        ])
        return len(CHECKLIST_SUGERIDO)
    if tipo == "roteiro" and not EventScheduleItem.objects.filter(event_key=chave).exists():
        EventScheduleItem.objects.bulk_create([
            EventScheduleItem(event_key=chave, start=inicio, end=fim, title=titulo, details=detalhe)
            for inicio, fim, titulo, detalhe in ROTEIRO_SUGERIDO
        ])
        return len(ROTEIRO_SUGERIDO)
    return 0


def evento_snapshot(ingressos: dict, lista_espera: int) -> dict:
    """Tudo da aba Creator Day. `ingressos` é o resumo do checkout do produto creatorday."""
    chave = EVENTO["chave"]
    hoje = timezone.localdate()
    fornecedores = list(EventSupplier.objects.filter(event_key=chave))
    tarefas = list(EventTask.objects.filter(event_key=chave))
    roteiro = list(EventScheduleItem.objects.filter(event_key=chave))
    rotulo_categoria = dict(EventSupplier.CATEGORY_CHOICES)

    # ---------- orçamento
    receita_ingressos = _decimal(ingressos.get("receita"))
    patrocinios = sum((_decimal(f.amount) for f in fornecedores if f.deal == "patrocinio" and f.status in FECHADOS), Decimal("0"))
    custos = [f for f in fornecedores if f.deal == "pago" and f.status in FECHADOS]
    custo_total = sum((_decimal(f.amount) for f in custos), Decimal("0"))
    ja_pago = sum((_pago(f) for f in custos), Decimal("0"))
    cotacoes = [f for f in fornecedores if f.deal == "pago" and f.status in EM_COTACAO]
    em_cotacao = sum((_decimal(f.amount) for f in cotacoes), Decimal("0"))
    entradas = receita_ingressos + patrocinios

    # ---------- fornecedores por categoria (todas as categorias aparecem, mesmo vazias)
    itens = []
    for f in fornecedores:
        falta = _decimal(f.amount) - _pago(f) if f.amount is not None and f.deal == "pago" else Decimal("0")
        itens.append({
            "obj": f,
            "situacao": f.get_status_display(),
            "tom": TOM_SITUACAO.get(f.status, "neutro"),
            "acordo": f.get_deal_display(),
            "parceiro": f.deal != "pago",
            "valor": brl(f.amount) if f.amount is not None else "",
            "falta": brl(falta) if falta > 0 and f.status in FECHADOS else "",
            "whatsapp_link": whatsapp_link(f.whatsapp),
            "vencido": bool(f.due_date and f.due_date < hoje and falta > 0 and f.status in FECHADOS),
        })
    por_categoria = [
        {"chave": valor, "rotulo": rotulo, "itens": [i for i in itens if i["obj"].category == valor]}
        for valor, rotulo in EventSupplier.CATEGORY_CHOICES
    ]
    categorias_sem = [c["rotulo"] for c in por_categoria if c["chave"] != "outros" and not any(i["obj"].status != "cancelado" for i in c["itens"])]
    pagamentos = sorted(
        [i for i in itens if i["falta"] and i["obj"].due_date],
        key=lambda i: i["obj"].due_date,
    )[:5]
    por_situacao = [
        (rotulo, sum(1 for f in fornecedores if f.status == valor), TOM_SITUACAO[valor])
        for valor, rotulo in EventSupplier.STATUS_CHOICES
    ]

    # ---------- tarefas
    rotulo_area = dict(EventTask.AREA_CHOICES)
    feitas = sum(1 for t in tarefas if t.done)
    atrasadas = {t.pk for t in tarefas if not t.done and t.due_date and t.due_date < hoje}
    tarefas_info = [
        {"obj": t, "area": rotulo_area.get(t.area, t.area), "atrasada": t.pk in atrasadas,
         "hoje": bool(not t.done and t.due_date == hoje)}
        for t in tarefas
    ]
    por_area = [
        {"chave": valor, "rotulo": rotulo, "itens": [i for i in tarefas_info if i["obj"].area == valor],
         "feitas": sum(1 for t in tarefas if t.area == valor and t.done)}
        for valor, rotulo in EventTask.AREA_CHOICES
    ]
    proximas = [i for i in tarefas_info if not i["obj"].done][:5]

    dados_edicao = {
        "fornecedor": {
            str(f.pk): {
                "name": f.name, "category": f.category, "delivers": f.delivers, "contact_name": f.contact_name,
                "whatsapp": f.whatsapp, "email": f.email, "instagram": f.instagram, "status": f.status, "deal": f.deal,
                "amount": _valor_campo(f.amount), "paid_amount": _valor_campo(f.paid_amount) if f.paid_amount else "",
                "due_date": f.due_date.isoformat() if f.due_date else "", "notes": f.notes,
            }
            for f in fornecedores
        },
        "tarefa": {
            str(t.pk): {"title": t.title, "area": t.area, "owner": t.owner,
                        "due_date": t.due_date.isoformat() if t.due_date else "", "notes": t.notes}
            for t in tarefas
        },
        "roteiro": {
            str(r.pk): {"start": r.start.strftime("%H:%M"), "end": r.end.strftime("%H:%M") if r.end else "",
                        "title": r.title, "owner": r.owner, "details": r.details}
            for r in roteiro
        },
    }

    return {
        "info": EVENTO,
        "dias": (EVENTO["data"] - hoje).days,
        "ingressos": ingressos,
        "lista_espera": lista_espera,
        "orcamento": {
            "receita_ingressos": brl(receita_ingressos),
            "patrocinios": brl(patrocinios),
            "entradas": brl(entradas),
            "custos": brl(custo_total),
            "ja_pago": brl(ja_pago),
            "falta_pagar": brl(max(custo_total - ja_pago, Decimal("0"))),
            "saldo": ("− " if entradas < custo_total else "") + brl(abs(entradas - custo_total)),
            "saldo_negativo": entradas - custo_total < 0,
            "em_cotacao": brl(em_cotacao),
            "cotacoes": len(cotacoes),
            "custos_n": len(custos),
            "pago_pct": round(ja_pago * 100 / custo_total) if custo_total else 0,
        },
        "fornecedores_total": sum(1 for f in fornecedores if f.status != "cancelado"),
        "parceiros_total": sum(1 for f in fornecedores if f.deal != "pago" and f.status != "cancelado"),
        "por_categoria": por_categoria,
        "categorias_sem": categorias_sem,
        "rotulo_categoria": rotulo_categoria,
        "pagamentos": pagamentos,
        "por_situacao": por_situacao,
        "tarefas_total": len(tarefas),
        "tarefas_feitas": feitas,
        "tarefas_pct": round(feitas * 100 / len(tarefas)) if tarefas else 0,
        "tarefas_atrasadas": len(atrasadas),
        "por_area": por_area,
        "proximas": proximas,
        "roteiro": roteiro,
        "checklist_sugerido_total": len(CHECKLIST_SUGERIDO),
        "dados_edicao": dados_edicao,
        "categorias": EventSupplier.CATEGORY_CHOICES,
        "situacoes": EventSupplier.STATUS_CHOICES,
        "acordos": EventSupplier.DEAL_CHOICES,
        "areas": EventTask.AREA_CHOICES,
        "hoje": hoje,
    }
