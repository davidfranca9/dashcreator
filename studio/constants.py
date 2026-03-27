from __future__ import annotations

NAV_ITEMS = [
    {"key": "dashboard", "label": "Dashboard", "subtitle": "Visao executiva do negocio UGC.", "url_name": "dashboard"},
    {"key": "prospection", "label": "Prospecção", "subtitle": "Leads, follow-ups e negociacoes em aberto.", "url_name": "prospection"},
    {"key": "jobs", "label": "Trabalhos", "subtitle": "Projetos assinados e entregas em andamento.", "url_name": "jobs"},
    {"key": "finance", "label": "Financeiro", "subtitle": "Entradas, recebimentos e previsoes de caixa.", "url_name": "finance"},
    {"key": "reports", "label": "Relatorios", "subtitle": "Indicadores estrategicos do negocio.", "url_name": "reports"},
    {"key": "profile", "label": "Perfil", "subtitle": "Dados cadastrais da conta e do workspace.", "url_name": "profile"},
    {"key": "settings", "label": "Configuracoes", "subtitle": "Preferencias visuais e operacionais.", "url_name": "settings"},
]

NAV_GROUPS = [
    {"label": "ERP", "keys": ["dashboard", "jobs", "prospection", "finance", "reports"]},
    {"label": "Perfil", "keys": ["profile", "settings"]},
]

PROJECT_STAGE_CHOICES = [
    ("Fechado", "Fechado"),
    ("Entregue", "Entregue"),
]

PROJECT_STATUS_CHOICES = [
    ("Briefing", "Briefing"),
    ("Em gravacao", "Em gravacao"),
    ("Em edicao", "Em edicao"),
    ("Aguardando cliente", "Aguardando aprovacao"),
    ("Aprovado", "Aprovado"),
    ("Entregue", "Entregue"),
]

PROSPECT_STAGE_CHOICES = [
    ("Prospeccao", "Prospecção"),
    ("Negociacao", "Negociacao"),
]

DEFAULT_NICHE_NAMES = [
    "Tech",
    "Haircare",
    "Beleza",
    "Moda e Acess\u00f3rios",
    "Sa\u00fade e Bem-estar",
    "Skincare",
    "Gastronomia",
    "Infoproduto e Educa\u00e7\u00e3o",
    "Aplicativo",
    "Eventos e Experi\u00eancias",
    "Casa e Decora\u00e7\u00e3o",
    "Relacionamento",
]

COMPANY_COLORS = {
    "Nike": ("#d5e2f4", "#edf4fd", "#39b8d0"),
    "Shein": ("#d6ddef", "#eef3fb", "#4d8cff"),
    "Boticario": ("#dbeed9", "#eef8ec", "#31b286"),
    "Reserva": ("#f6e1d1", "#fbf1ea", "#f59a3d"),
    "Amaro": ("#e4dbf4", "#f2effc", "#7f6fff"),
    "Natura": ("#d3ece6", "#ecfaf6", "#20b7a7"),
    "Insider": ("#d8e5fa", "#eef4fd", "#3d82f6"),
    "Eudora": ("#f2dff2", "#faf0fa", "#c765c7"),
    "Track&Field": ("#d8edf1", "#eef8fa", "#36b7d3"),
    "Magalu": ("#d9e3fb", "#eff4ff", "#3b7cff"),
    "Localiza": ("#deefd8", "#eef8ea", "#6cbe45"),
    "Riachuelo": ("#efe0d8", "#fbf1ec", "#e18352"),
    "Adidas": ("#dbe4ef", "#eef3f8", "#61748e"),
}

SETTINGS_GROUPS = [
    {
        "title": "Experiencia visual",
        "description": "Ajustes visuais para deixar o painel mais confortavel no seu dia a dia.",
        "rows": [
            {
                "id": "ui_dark_theme",
                "label": "Tema escuro",
                "detail": "Ativa uma versao escura do painel para trabalhar com menos claridade.",
                "type": "check",
                "value": False,
            },
            {
                "id": "ui_soft_card_shadows",
                "label": "Sombras suaves nos cards",
                "detail": "Ajuda a separar blocos sem deixar a tela pesada.",
                "type": "check",
                "value": True,
            },
            {
                "id": "ui_subtle_navigation_animation",
                "label": "Animacao discreta na navegacao",
                "detail": "Mantem a interface fluida sem exagero.",
                "type": "check",
                "value": True,
            },
        ],
    },
    {
        "title": "Operacao",
        "description": "Preferencias basicas de trabalho e caixa.",
        "rows": [
            {
                "id": "ops_default_entry_rate",
                "label": "Entrada padrao sugerida",
                "detail": "Percentual padrao ao fechar um job.",
                "type": "combo",
                "options": ["50%", "40%", "30%"],
                "value": "50%",
            },
            {
                "id": "ops_primary_currency",
                "label": "Moeda principal",
                "detail": "Usada em metricas e relatorios.",
                "type": "combo",
                "options": ["BRL (R$)", "USD ($)", "EUR (EUR)"],
                "value": "BRL (R$)",
            },
            {
                "id": "ops_follow_up_reminders",
                "label": "Lembretes de follow-up",
                "detail": "Sinaliza leads sem resposta a mais de 3 dias.",
                "type": "check",
                "value": True,
            },
        ],
    },
]

REVENUE_RANGE_CHOICES = [
    ("current_month", "Este mes"),
    ("last_quarter", "Ultimo trimestre"),
    ("last_6_months", "Ultimos 6 meses"),
]
