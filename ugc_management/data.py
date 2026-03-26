from __future__ import annotations

NAV_ITEMS = [
    {"key": "dashboard", "label": "Dashboard", "subtitle": "Visao executiva do negocio UGC.", "icon": "home"},
    {"key": "prospection", "label": "Prospeccao", "subtitle": "Leads, follow-ups e negociacoes em aberto.", "icon": "search"},
    {"key": "jobs", "label": "Trabalhos", "subtitle": "Projetos assinados e entregas em andamento.", "icon": "briefcase"},
    {"key": "finance", "label": "Financeiro", "subtitle": "Entradas, recebimentos e previsoes de caixa.", "icon": "wallet"},
    {"key": "reports", "label": "Relatorios", "subtitle": "Indicadores estrategicos do negocio.", "icon": "chart"},
    {"key": "settings", "label": "Configuracoes", "subtitle": "Preferencias visuais e operacionais.", "icon": "settings"},
]

PROJECT_STAGES = ["Fechado", "Entregue"]
PROJECT_STATUSES = ["Briefing", "Em gravacao", "Em edicao", "Aguardando cliente", "Aprovado", "Entregue"]
PROSPECT_STAGES = ["Prospeccao", "Negociacao"]

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
        "description": "O app fixa contraste alto para nao depender do tema do notebook.",
        "rows": [
            {
                "id": "ui_lock_light_contrast",
                "label": "Contraste claro travado no app",
                "detail": "Mantem cards claros e textos escuros mesmo com Windows em tema escuro.",
                "type": "check",
                "value": True,
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
