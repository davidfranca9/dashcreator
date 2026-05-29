from __future__ import annotations

NAV_ITEMS = [
    {"key": "dashboard", "label": "Dashboard", "subtitle": "Visão executiva do negócio UGC.", "url_name": "dashboard", "icon": "dashboard"},
    {"key": "jobs", "label": "Trabalhos", "subtitle": "Projetos assinados e entregas em andamento.", "url_name": "jobs", "icon": "briefcase"},
    {"key": "prospection", "label": "Prospecção", "subtitle": "Leads, follow-ups e negociações em aberto.", "url_name": "prospection", "icon": "target"},
    {"key": "finance", "label": "Financeiro", "subtitle": "Entradas, recebimentos e previsões de caixa.", "url_name": "finance", "icon": "cash"},
    {"key": "distribution", "label": "Distribuição", "subtitle": "Destino do material entregue entre orgânico e ads.", "url_name": "distribution", "icon": "share"},
    {"key": "legal", "label": "Jurídico", "subtitle": "Licenciamento e vencimento do direito de uso de imagem.", "url_name": "legal", "icon": "file-text"},
    {"key": "reports", "label": "Relatórios", "subtitle": "Indicadores estratégicos do negócio.", "url_name": "reports", "icon": "chart-bar"},
    {"key": "profile", "label": "Perfil", "subtitle": "Dados cadastrais da conta e do workspace.", "url_name": "profile", "icon": "user"},
    {"key": "settings", "label": "Configurações", "subtitle": "Preferências visuais e operacionais.", "url_name": "settings", "icon": "settings"},
]

NAV_GROUPS = [
    {"label": "Principal", "keys": ["dashboard", "jobs", "prospection"]},
    {"label": "Gestão", "keys": ["finance", "distribution", "legal", "reports"]},
    {"label": "Conta", "keys": ["profile", "settings"]},
]

PROJECT_STAGE_CHOICES = [
    ("Fechado", "Fechado"),
    ("Entregue", "Entregue"),
]

PROJECT_STATUS_CHOICES = [
    ("Briefing", "Briefing"),
    ("Em produção", "Em produção"),
    ("Aguardando aprovação", "Aguardando aprovação"),
    ("Concluído", "Concluído"),
    ("Cancelado", "Cancelado"),
]

PROJECT_STATUS_TONES = {
    "Briefing": "info",
    "Em produção": "warning",
    "Aguardando aprovação": "purple",
    "Concluído": "success",
    "Cancelado": "danger",
}

LEGACY_PROJECT_STATUS_MAP = {
    "Aguardando produto": "Em produção",
    "Em gravacao": "Em produção",
    "Em edicao": "Em produção",
    "Aguardando cliente": "Aguardando aprovação",
    "Aprovado": "Concluído",
    "Entregue": "Concluído",
}

PROSPECT_STAGE_CHOICES = [
    ("Rascunho", "Rascunho"),
    ("Prospeccao", "Prospecção"),
    ("Aguardando retorno", "Aguardando retorno"),
    ("Negociacao", "Negociação"),
    ("Follow-up", "Follow-up"),
]

# 11 tipos padrão de serviço do brief Dash Creator + 'outros' como fallback
# pra dados legacy. A creator pode usar o ServiceCategory livre como rótulo
# adicional (ex: "UGC Creator – campanhas grandes"); o tipo é o que dirige
# o comportamento do form e os relatórios por tipo.
SERVICE_TYPE_CHOICES = [
    ("ugc_creator", "UGC Creator"),
    ("freelancer", "Freelancer"),
    ("editora_video", "Editora de Vídeo"),
    ("videomaker", "Videomaker"),
    ("storymaker", "Storymaker"),
    ("social_media", "Social Media"),
    ("ugc_manager", "UGC Manager"),
    ("consultoria_marketing", "Consultoria de Marketing"),
    ("publicidade", "Publicidade"),
    ("shop_creator", "Shop Creator"),
    ("afiliacao", "Afiliação / Comissão"),
    ("outros", "Outros"),
]

SERVICE_TYPE_CATEGORIES = [
    {
        "key": "producao",
        "label": "Produção de Conteúdo",
        "types": ["ugc_creator", "freelancer", "editora_video", "videomaker", "storymaker"],
    },
    {
        "key": "gestao",
        "label": "Gestão & Estratégia",
        "types": ["social_media", "ugc_manager", "consultoria_marketing"],
    },
    {
        "key": "publicidade",
        "label": "Publicidade & Parcerias",
        "types": ["publicidade", "shop_creator", "afiliacao"],
    },
    {
        "key": "outros",
        "label": "Outros",
        "types": ["outros"],
    },
]

SERVICE_TYPE_TO_CATEGORY = {
    service_type: category["key"]
    for category in SERVICE_TYPE_CATEGORIES
    for service_type in category["types"]
}

# Tipos cuja regra de pagamento é "valor único pós-produção" (sem entrada,
# sem parcelas múltiplas). Reflete o brief seções 4.1 e 4 (Publicidade,
# Shop Creator). Afiliação tem regra própria (% sobre vendas).
POST_PRODUCTION_PAYMENT_TYPES = {"publicidade", "shop_creator"}
COMMISSION_PAYMENT_TYPES = {"afiliacao"}

LEGACY_DEFAULT_NICHE_NAMES = [
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
    "Viagem",
]

DEFAULT_NICHE_NAMES = [
    "Alimenta\u00e7\u00e3o Saud\u00e1vel e Nutri\u00e7\u00e3o",
    "Arte e Cultura",
    "Culin\u00e1ria e Receitas",
    "Autom\u00f3veis e Carros",
    "DIY e Fa\u00e7a Voc\u00ea Mesmo",
    "Casa",
    "Casamento e Eventos",
    "Beleza e Maquiagem",
    "Haircare",
    "Decora\u00e7\u00e3o e Design de Interiores",
    "Educa\u00e7\u00e3o e Aprendizagem",
    "Filmes e S\u00e9ries",
    "Empreendedorismo e Neg\u00f3cios",
    "Fitness e Bem-Estar",
    "Fotografia e Edi\u00e7\u00e3o de Imagens",
    "Esportes e Atletismo",
    "Finan\u00e7as e Investimentos",
    "Gaming e Jogos Eletr\u00f4nicos",
    "Hobbies e Passatempos",
    "Gastronomia",
    "LGBTQ+ e Diversidade",
    "Tecnologia e Eletr\u00f4nicos",
    "Sa\u00fade Mental e Bem-Estar emocional",
    "Pet Lovers (Amantes de animais de estima\u00e7\u00e3o)",
    "Livros e Literatura",
    "Moda Masculina",
    "Moda Feminina",
    "Marcas Sustent\u00e1veis e \u00c9ticas",
    "M\u00fasica e Entretenimento",
    "Sustentabilidade e Meio Ambiente",
    "Maternidade e Paternidade",
    "Viagens e Turismo",
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

CASH_BOX_ALLOCATION_SETTINGS = {
    "reserve": {
        "key": "finance_reserve_percentage",
        "label": "Reserva",
        "default": "30.00",
        "description": "Percentual separado para reserva antes do fluxo livre.",
    },
    "investment": {
        "key": "finance_investment_percentage",
        "label": "Investimento",
        "default": "20.00",
        "description": "Percentual separado para investimento antes do fluxo livre.",
    },
}

SETTINGS_GROUPS = [
    {
        "title": "Experiência visual",
        "description": "Ajustes visuais para deixar o painel mais confortável no seu dia a dia.",
        "rows": [
            {
                "id": "ui_dark_theme",
                "label": "Tema escuro",
                "detail": "Ativa uma versão escura do painel para trabalhar com menos claridade.",
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
                "label": "Animação discreta na navegação",
                "detail": "Mantém a interface fluida sem exagero.",
                "type": "check",
                "value": True,
            },
        ],
    },
    {
        "title": "Operação",
        "description": "Preferências básicas de trabalho e caixa.",
        "rows": [
            {
                "id": "ops_default_entry_rate",
                "label": "Entrada padrão sugerida",
                "detail": "Percentual padrão ao fechar um job.",
                "type": "combo",
                "options": ["50%", "40%", "30%"],
                "value": "50%",
            },
            {
                "id": "ops_primary_currency",
                "label": "Moeda principal",
                "detail": "Usada em métricas e relatórios.",
                "type": "combo",
                "options": ["BRL (R$)", "USD ($)", "EUR (EUR)"],
                "value": "BRL (R$)",
            },
            {
                "id": "ops_pro_labore_amount",
                "label": "Pró-labore mensal",
                "detail": "Valor fixo retirado primeiro na distribuição financeira.",
                "type": "money",
                "value": "5000.00",
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
    {
        "title": "Jurídico",
        "description": "Dados usados na geração dos contratos do workspace.",
        "rows": [
            {
                "id": "legal_contract_signer_name",
                "label": "Nome no contrato",
                "detail": "Usado como nome da contratada no contrato principal.",
                "type": "text",
                "value": "",
            },
        ],
    },
]

REVENUE_RANGE_CHOICES = [
    ("current_month", "Este mês"),
    ("last_quarter", "Último trimestre"),
    ("last_6_months", "Últimos 6 meses"),
]

PROJECT_DISTRIBUTION_CHOICES = [
    ("", "Selecione"),
    ("Organico", "Orgânico"),
    ("Ads", "Ads"),
    ("Nao se aplica", "Não se aplica"),
]

IMAGE_LICENSE_TERM_CHOICES = [
    (90, "90 dias"),
    (180, "180 dias"),
    (270, "270 dias"),
    (360, "360 dias"),
]
