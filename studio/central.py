"""Central TCC: a plataforma interna com tudo do The Creators Club.

Junta num lugar só o que estava espalhado (produtos, preços, sites, vendas,
operação, sistema, tecnologia, riscos) e mostra os números AO VIVO do banco.
Só as contas do time veem (ver is_internal_account). Nada de senha, token ou
dado pessoal: só totais, nomes de produtos e onde cada coisa mora.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from .checkout import get_product
from .constants import PROSPECT_STAGE_CHOICES
from .creator_day import CREATOR_DAY_EVENT, brl
from .evento import evento_snapshot
from .models import (
    AccessCode,
    EventWaitlistEntry,
    InfoLead,
    InfoProduct,
    InfoProductSale,
    PageEvent,
    Project,
    Prospect,
    Purchase,
)

SITE = "https://thecreatorsclub.com.br"
APP = "https://app.thecreatorsclub.com.br"
PORTAL = "https://portal.thecreatorsclub.com.br"
LAYFE = "https://layfeamorim.com"

# "grupo" separa o menu: o que se acompanha todo dia e o que se consulta.
SECOES = [
    {"id": "inicio", "titulo": "Visão geral", "grupo": "Dia a dia"},
    {"id": "evento", "titulo": "Creator Day", "grupo": "Dia a dia"},
    {"id": "vendas", "titulo": "Vendas e inscrições", "grupo": "Dia a dia"},
    {"id": "numeros", "titulo": "Números", "grupo": "Dia a dia"},
    {"id": "pendencias", "titulo": "Pendências", "grupo": "Dia a dia"},
    {"id": "produtos", "titulo": "Produtos e preços", "grupo": "Consulta"},
    {"id": "links", "titulo": "Sites e links", "grupo": "Consulta"},
    {"id": "como-fazer", "titulo": "Como fazer", "grupo": "Consulta"},
    {"id": "sistema", "titulo": "Sistema", "grupo": "Consulta"},
    {"id": "tecnologia", "titulo": "Tecnologia", "grupo": "Consulta"},
]

# ---------------------------------------------------------------- produtos
PRODUTOS = [
    {
        "nome": "Dash Creator", "checkout": "dashcreator", "infoproduto": "Dash Creator",
        "frase": "O sistema que organiza o negócio da UGC creator: trabalhos, prospecção, financeiro com caixinhas, contratos em 1 clique e licença de imagem.",
        "detalhe": "à vista ou 12x de R$ 13,73 · acesso anual · garantia de 7 dias",
        "pagamento": "Checkout próprio (Mercado Pago)", "link": SITE + "/dashcreator/", "link_rotulo": "Página de vendas",
        "situacao": "À venda", "tom": "ok", "confirmar": False,
    },
    {
        "nome": "Creator Day Experience", "checkout": "creatorday",
        "frase": "Evento presencial de skincare, networking e criação. 17 de outubro de 2026, 14h, Piatã, Salvador/BA.",
        "detalhe": "ingresso · a página cita até 12x de R$ 12,21",
        "pagamento": "Checkout próprio (Mercado Pago)", "link": SITE + "/creator-experience/", "link_rotulo": "Página do evento",
        "situacao": "À venda", "tom": "ok", "confirmar": False,
    },
    {
        "nome": "Planner Creator", "infoproduto": "Planner Creator", "preco_fixo": "R$ 157,00",
        "frase": "Planejar o conteúdo do mês em poucas horas, com fluxograma de ideias, planners, planilhas de faturamento e prospecção e mapa de datas.",
        "detalhe": "à vista ou 12x de R$ 15,96 · a página diz \"de R$ 505\" · garantia de 7 dias",
        "pagamento": "Hubla", "link": SITE + "/planner/", "link_rotulo": "Página de vendas",
        "situacao": "À venda", "tom": "ok", "confirmar": True,
    },
    {
        "nome": "Mentoria HPC", "checkout": "hpc", "infoproduto": "Mentoria HPC", "somar_lancadas": True,
        "frase": "High Performance Creator: mentoria em grupo com a Layfe, 04 encontros ao vivo às segundas, 19h, 45 dias de acesso, Comunidade TCC e desafios. Edição especial antes da Black Friday.",
        "detalhe": "à vista ou em até 12x no cartão · a página diz 12x de R$ 60,66",
        "pagamento": "Checkout próprio (Mercado Pago); turmas antigas pela Hubla", "link": SITE + "/hpc/", "link_rotulo": "Página de vendas",
        "situacao": "À venda", "tom": "ok", "confirmar": False,
    },
    {
        "nome": "Renovação HPC", "infoproduto": "Renovação HPC",
        "frase": "Continuação da mentoria (a confirmar se é para quem já fez a Mentoria HPC).",
        "detalhe": "sem página pública",
        "pagamento": "Link Nubank", "link": APP + "/infoprodutos/", "link_rotulo": "Infoprodutos",
        "situacao": "Ativo no cadastro", "tom": "neutro", "confirmar": True,
    },
    {
        "nome": "Acompanhamento 1:1", "infoproduto": "Acompanhamento",
        "frase": "Acompanhamento individual com a Layfe. A home do clube fala em \"Acompanhamento TCC: 4 encontros ao vivo\".",
        "detalhe": "sem página pública: o botão da home leva ao Instagram",
        "pagamento": "Link Nubank", "link": APP + "/infoprodutos/", "link_rotulo": "Infoprodutos",
        "situacao": "Ativo no cadastro", "tom": "neutro", "confirmar": True,
    },
    {
        "nome": "Desafio Postaria Mais", "preco_fixo": "Sem preço",
        "frase": "7 dias de missões com pontos, ranking, mural e indicações, de 14 a 20/09/2026. A última missão prepara a creator para a Black Friday.",
        "detalhe": "a confirmar se é gratuito e qual é o prêmio",
        "pagamento": "Inscrição livre com código por e-mail", "link": SITE + "/desafio/login.html", "link_rotulo": "Link de inscrição",
        "situacao": "Acontecendo", "tom": "espera", "confirmar": True,
    },
    {
        "nome": "Portal do TCC", "preco_fixo": "Acesso pela mentora",
        "frase": "Área de membros da Turma 01: aulas por fase, materiais, tarefas, desafios, entregas, dúvidas e certificados.",
        "detalhe": "a confirmar se está em uso ou se as alunas usam a Hubla",
        "pagamento": "Código individual criado pela mentora", "link": PORTAL, "link_rotulo": "Abrir o portal",
        "situacao": "Uso a confirmar", "tom": "neutro", "confirmar": True,
    },
    {
        "nome": "Desafio da Semana", "preco_fixo": "Sem preço",
        "frase": "Desafio temático em PDF para membras, mostrado em imagens para abrir dentro da Hubla.",
        "detalhe": "a confirmar se é recorrente",
        "pagamento": "Material para membras", "link": LAYFE + "/desafio", "link_rotulo": "Abrir",
        "situacao": "Material", "tom": "neutro", "confirmar": True,
    },
    {
        "nome": "Serviços UGC da Layfe", "preco_fixo": "Sob orçamento",
        "frase": "Conteúdo UGC, curadoria, publicidade, social commerce e social media para marcas. +150 marcas, ROI médio 4,11.",
        "detalhe": "pedidos do portfólio caem na Prospecção da Layfe",
        "pagamento": "Direto com a Layfe", "link": LAYFE + "/portfolio/", "link_rotulo": "Portfólio",
        "situacao": "Ativo", "tom": "ok", "confirmar": False,
    },
]

# ------------------------------------------------------------------- links
LINKS = [
    {
        "grupo": "thecreatorsclub.com.br", "descricao": "Site do clube. Publica pelo git.",
        "itens": [
            ("Home do clube", SITE + "/", "Manifesto, caminhos (Planner, Dash, Acompanhamento) e comunidade", "Público"),
            ("Página de vendas do Dash", SITE + "/dashcreator/", "Vendas do Dash Creator, com Meta Pixel", "Público"),
            ("Página do Planner", SITE + "/planner/", "Vendas do Planner, checkout na Hubla", "Público"),
            ("Checkout do Dash", SITE + "/checkout/dashcreator/", "Pagamento Mercado Pago e código por e-mail", "Compradoras"),
            ("Página da HPC", SITE + "/hpc/", "Vendas da mentoria High Performance Creator (R$ 597)", "Público"),
            ("Checkout da HPC", SITE + "/checkout/hpc/", "Pagamento Mercado Pago e confirmação da vaga por e-mail", "Compradoras"),
            ("Página do Creator Day", SITE + "/creator-experience/", "Evento de 17/10/2026", "Público"),
            ("Checkout do ingresso", SITE + "/checkout/creator-day/", "Pagamento do ingresso e e-mail de confirmação", "Compradoras"),
            ("Prévias do Creator Day", SITE + "/creator-experience/conceitos/", "Imersivo e Editorial, com lista de espera", "Link direto"),
            ("Inscrição no Desafio", SITE + "/desafio/login.html", "Link de divulgação do Desafio Postaria Mais", "Público"),
            ("Painel da organizadora", SITE + "/desafio/admin.html", "Pontos, datas, participantes e moderação", "Time"),
            ("Central TCC", SITE + "/central/", "Esta plataforma, com login do time", "Time"),
        ],
    },
    {
        "grupo": "app.thecreatorsclub.com.br", "descricao": "Sistema: Dash Creator e ferramentas do time.",
        "itens": [
            ("Entrar no app", APP + "/login/", "Login do Dash Creator", "Usuárias"),
            ("Criar conta com código", APP + "/signup/", "Cadastro de quem comprou ou recebeu código", "Novas usuárias"),
            ("Creator Day", APP + "/creator-day/", "Lista de espera e ingressos", "Time"),
            ("CRM", APP + "/crm/", "Leads que chegaram até a Layfe", "Time"),
            ("Infoprodutos", APP + "/infoprodutos/", "Produtos e vendas da Hubla e Nubank", "Time"),
            ("Métricas dos sites", APP + "/metricas/", "Visitas, cliques, Stories e anúncios", "Equipe"),
            ("Admin", APP + "/admin/", "Códigos, cupons, compras e Desafio", "Equipe"),
            ("Compras do checkout", APP + "/admin/studio/purchase/", "Todas as compras, com filtro por produto", "Equipe"),
        ],
    },
    {
        "grupo": "portal.thecreatorsclub.com.br", "descricao": "Portal do TCC. Publica copiando arquivos no servidor.",
        "itens": [
            ("Portal do TCC", PORTAL, "Área da aluna e aba Admin da mentora", "Alunas e mentora"),
        ],
    },
    {
        "grupo": "layfeamorim.com", "descricao": "Site da Layfe, na segunda VPS.",
        "itens": [
            ("Home Sou Marca / Sou Creator", LAYFE + "/", "Triagem, formulários de lista de espera e social media", "Público"),
            ("Portfólio UGC", LAYFE + "/portfolio/", "10 nichos, cases e serviços, com popup de orçamento", "Marcas"),
            ("Desafio da Semana", LAYFE + "/desafio", "PDF em imagens para a Hubla", "Membras"),
        ],
    },
    {
        "grupo": "Instagram e contato", "descricao": "Perfis oficiais confirmados em 16/09/2026.",
        "itens": [
            ("@thecreatorssclubb", "https://www.instagram.com/thecreatorssclubb/", "Instagram do clube", "Público"),
            ("@layfeamorim", "https://www.instagram.com/layfeamorim/", "Instagram da fundadora", "Público"),
            ("@dashhcreator_", "https://www.instagram.com/dashhcreator_/", "Instagram do Dash Creator", "Público"),
            ("WhatsApp (71) 9 9723-8419", "https://wa.me/5571997238419", "Contato comercial e do Creator Day", "Público"),
        ],
    },
]

# ------------------------------------------------------------- como fazer
GUIAS = [
    {
        "titulo": "Liberar acesso ao Dash para alguém (sem compra)",
        "quando": "Aluna da mentoria, parceira ou cortesia. Quem compra no checkout recebe o código sozinha.",
        "passos": [
            "Abra o Admin > Access codes e procure um código sem usuário e ativo.",
            "Se não tiver, peça ao David para gerar: comando generate_access_codes --non-paid 2 no servidor.",
            "Mande para a pessoa: \"Entre em app.thecreatorsclub.com.br/signup/ e use o código TCC-N-XXXXXXXX. Ele é único e funciona uma vez.\"",
            "Depois do cadastro, o código aparece em Access codes com o usuário dela.",
        ],
        "link": APP + "/admin/studio/accesscode/", "link_rotulo": "Abrir Access codes",
    },
    {
        "titulo": "Recuperar quem não pagou o ingresso do Creator Day",
        "quando": "Todo dia, enquanto o ingresso estiver à venda.",
        "passos": [
            "Abra Creator Day > aba Ingressos.",
            "\"Não finalizou\" preencheu os dados e não pagou. \"Aguardando pagamento\" gerou Pix ou boleto.",
            "Clique no WhatsApp da pessoa (já é um link) e mande o link do checkout: thecreatorsclub.com.br/checkout/creator-day/",
            "Quando pagar, a situação vira \"Pago\" sozinha e ela recebe o e-mail do ingresso.",
        ],
        "link": APP + "/creator-day/?tab=ingressos", "link_rotulo": "Abrir Ingressos",
    },
    {
        "titulo": "Criar ou mudar um cupom",
        "quando": "Promoção do Dash Creator ou do ingresso.",
        "passos": [
            "Admin > Coupons > Adicionar.",
            "Code: o código que a pessoa digita. Product key: dashcreator, creatorday ou hpc.",
            "Discount percent: o desconto em %. Active marcado. Salve.",
            "Vale na hora, sem publicar nada. Na lista dá para mudar o % e desativar direto.",
        ],
        "link": APP + "/admin/studio/coupon/", "link_rotulo": "Abrir Cupons",
    },
    {
        "titulo": "Lançar uma venda da Hubla ou do link Nubank",
        "quando": "Renovação, Acompanhamento, Planner e as turmas antigas da HPC não passam pelo checkout próprio.",
        "passos": [
            "Abra Infoprodutos > Entradas.",
            "Lance a venda: produto, comprador, plataforma, valor, data e status Confirmado.",
            "A venda passa a contar no Dashboard e no Financeiro da Layfe.",
        ],
        "link": APP + "/infoprodutos/", "link_rotulo": "Abrir Infoprodutos",
    },
    {
        "titulo": "Tirar o acesso de alguém ao Dash",
        "quando": "Reembolso, fim de cortesia ou uso indevido.",
        "passos": [
            "Desativar o código NÃO tira o acesso de quem já tem conta.",
            "Admin > Users > abra a pessoa > desmarque Active > salve.",
            "Para voltar, marque Active de novo.",
        ],
        "link": APP + "/admin/auth/user/", "link_rotulo": "Abrir Users",
    },
    {
        "titulo": "Cuidar do Desafio Postaria Mais",
        "quando": "Durante o desafio.",
        "passos": [
            "Entre no painel da organizadora com o usuário e a senha do admin.",
            "Participantes: busca, copiar todos os e-mails, dar ou tirar pontos com motivo, desativar.",
            "Missões: mudar a data de liberação (o bônus \"no prazo\" usa essa data).",
            "Comprovações e Mural: conferir entregas e remover posts ou comentários.",
            "\"Fiz e não pontuou\": Admin > DESAFIO > Ponto eventos, filtrando pela participante.",
        ],
        "link": SITE + "/desafio/admin.html", "link_rotulo": "Abrir o painel",
    },
    {
        "titulo": "Cadastrar aluna no Portal do TCC",
        "quando": "Nova aluna da turma.",
        "passos": [
            "Entre no portal como mentora (\"Sou mentora\").",
            "Aba Admin > Matrículas > cadastrar: nome, e-mail, WhatsApp, turma e status.",
            "Copie o acesso (e-mail + código) e mande para a aluna. O portal não manda e-mail sozinho.",
        ],
        "link": PORTAL, "link_rotulo": "Abrir o portal",
    },
    {
        "titulo": "Medir Stories e anúncios",
        "quando": "Antes de postar um link.",
        "passos": [
            "Stories: termine o link com #layfe, #tcc ou #dash (ex.: thecreatorsclub.com.br/dashcreator#dash.promo).",
            "Anúncio: use ?utm_source=instagram&utm_medium=paid&utm_campaign=NOME&utm_content=CRIATIVO.",
            "Veja o resultado em Métricas, escolhendo o site.",
        ],
        "link": APP + "/metricas/", "link_rotulo": "Abrir Métricas",
    },
    {
        "titulo": "Publicar uma alteração no sistema ou no site",
        "quando": "Mudou código do app ou arquivo da pasta landing/.",
        "passos": [
            "git add, git commit e git push origin main.",
            "O Coolify publica sozinho: o site em 2 a 3 minutos e o sistema em 5 a 10.",
            "Só vai pro ar o que está no git. Arquivo copiado direto no servidor some no próximo deploy.",
            "CSS ou JS não mudou no navegador? Suba o ?v= do arquivo ou faça Purge Cache na Cloudflare.",
        ],
        "link": "", "link_rotulo": "",
    },
    {
        "titulo": "Site fora do ar ou deploy que não publica",
        "quando": "Página com erro 503 ou alteração que não aparece.",
        "passos": [
            "Confira o disco do servidor: ssh dashcreator-coolify e df -h /.",
            "Disco cheio: docker builder prune -af; docker image prune -af; journalctl --vacuum-size=200M.",
            "Site com 503: veja docker logs do container do site. Configuração boa do nginx em /root/backup-site-antes-git-20260916/.",
            "Falha baixando pacote no build: é passageira, o sistema segue na versão anterior. Faça outro push.",
        ],
        "link": "", "link_rotulo": "",
    },
]

# ---------------------------------------------------------------- sistema
MODULOS = [
    ("Dashboard", "Carteira de clientes, trabalhos ativos, faturamento mensal e anual, tarefas do dia (manuais e automáticas).", "Todas", APP + "/dashboard/"),
    ("Planejamento", "Pendências (todas, hoje, atrasadas) e calendário do mês.", "Todas", APP + "/planejamento/"),
    ("Trabalhos", "Projetos com marcas: 11 tipos de serviço, parcelas, kanban por funis, entregas e detalhe com mensagens prontas (time).", "Todas", APP + "/trabalhos/"),
    ("Prospecção", "Marcas que a creator foi atrás: 8 etapas, follow-up como ação, sugestões, contatos e conversão em trabalho.", "Todas", APP + "/prospeccao/"),
    ("CRM", "Leads que chegaram: Interesse até Fechado, Perdido à parte, tarefas, histórico e conversão em trabalho.", "Time", APP + "/crm/"),
    ("Creator Day", "Lista de espera das prévias e ingressos do checkout, com resumo de pagos e em aberto.", "Time", APP + "/creator-day/"),
    ("Financeiro", "Entradas confirmadas, saídas, a receber, custo fixo, pró-labore, reserva, investimento e caixinhas.", "Todas", APP + "/financeiro/"),
    ("Distribuição", "Trabalhos separados em Ads e Orgânico, com vencimento da licença.", "Todas", APP + "/distribuicao/"),
    ("Jurídico", "Contrato em PDF com cláusulas editáveis, busca de CNPJ e vencimento do direito de uso de imagem.", "Todas", APP + "/juridico/"),
    ("Infoprodutos", "Produtos digitais, vendas lançadas e alunas com prazo de acesso.", "Time", APP + "/infoprodutos/"),
    ("Relatórios", "Volume, total fechado, via e nicho líder, ticket médio e leitura estratégica do mês.", "Todas", APP + "/relatorios/"),
    ("Perfil e Configurações", "Dados empresariais, CPF ou CNPJ, chave PIX, tema escuro, entrada padrão, pró-labore e dados do contrato.", "Todas", APP + "/perfil/"),
    ("Métricas", "Visitas e cliques dos sites, Stories por perfil e Meta orgânico e pago.", "Equipe", APP + "/metricas/"),
]

REGRAS_ACESSO = [
    "Conta nasce de um código de acesso (checkout ou gerado pelo time). Cada código serve uma pessoa só.",
    "Entra com e-mail ou usuário. Sessão única: entrar em outro aparelho derruba o anterior (exceto layfeamorim).",
    "Time = usuários layfeamorim e davidfranca9 ou contas de equipe no admin. Nome no perfil não conta mais (corrigido em 16/09/2026).",
    "Admin: usuário admin (acesso total). layfeamorim e davidfranca9 só veem as compras.",
]

# ------------------------------------------------------------- tecnologia
SERVIDORES = [
    {"nome": "Servidor principal", "ssh": "dashcreator-coolify", "painel": "Coolify 4.0 beta", "disco": "38 GB (limpar depois de vários deploys)",
     "roda": "Site do clube, sistema, portal, banco Postgres, Evolution API"},
    {"nome": "Segunda VPS", "ssh": "layfe-novo", "painel": "Coolify 4.3", "disco": "38 GB",
     "roda": "layfeamorim.com (site e portfólio)"},
]

DOMINIOS = [
    ("thecreatorsclub.com.br", "Site estático (nginx) + /central/ repassada ao sistema", "Servidor principal", "Cloudflare", "git push"),
    ("app.thecreatorsclub.com.br", "Sistema Django", "Servidor principal", "Direto", "git push"),
    ("portal.thecreatorsclub.com.br", "Front do Portal do TCC", "Servidor principal (container manual)", "Direto", "Copiar arquivos para /data/manual-sites/tcc-portal/"),
    ("evo.thecreatorsclub.com.br", "Evolution API (WhatsApp)", "Servidor principal", "Direto", "Uso desconhecido: não mexer"),
    ("layfeamorim.com", "Site estático (nginx)", "Segunda VPS", "Hostinger", "A documentar"),
]

INTEGRACOES = [
    ("Mercado Pago", "Checkout do Dash e do ingresso, Pix, webhook"),
    ("Brevo", "E-mails: cadastro, senha, código de acesso, ingresso, Desafio"),
    ("Cloudflare", "DNS e cache do site do clube; e-mail de @thecreatorsclub.com.br"),
    ("Coolify + GitHub", "Publicação automática a cada push (davidfranca9/dashcreator)"),
    ("Hetzner", "As duas VPS"),
    ("Hostinger", "DNS de layfeamorim.com"),
    ("Hubla", "Checkout do Planner e das turmas antigas da Mentoria HPC (sem integração com o sistema)"),
    ("Google Apps Script + planilha", "Formulários do layfeamorim.com (planilha Leads Layfe)"),
    ("CallMeBot", "Aviso no WhatsApp a cada lead do layfeamorim.com"),
    ("Meta Pixel", "Só na página de vendas do Dash"),
    ("ViaCEP e APIBrasil", "Busca de CEP e CNPJ no Perfil e no Jurídico"),
    ("Evolution API", "API de WhatsApp no servidor, sem uso no código"),
]

ACESSOS = [
    ("Dash Creator", "app.thecreatorsclub.com.br/login/", "Layfe e David", "Gerenciador de senhas de cada um"),
    ("Admin + painel do Desafio", "/admin/ e /desafio/admin.html", "Usuário admin", "Gerenciador de senhas; trocar com changepassword admin"),
    ("Mentora do Portal", "portal > Sou mentora", "Layfe", "Variável TCC_PORTAL_ADMIN_PASSWORD no Coolify"),
    ("Servidores (SSH)", "dashcreator-coolify e layfe-novo", "David", "Chave SSH no computador do David"),
    ("Coolify, GitHub", "Painéis web", "David", "Contas do David"),
    ("Mercado Pago, Brevo, Cloudflare, Hostinger, Hetzner, Meta", "Painéis web", "A confirmar", "Contas de cada serviço; tokens como variáveis no Coolify"),
    ("Hubla", "hub.la", "Layfe", "Conta Hubla"),
]

VARIAVEIS = [
    ("Django", "DJANGO_SECRET_KEY, DJANGO_DEBUG, DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS, DJANGO_TIMEZONE"),
    ("Banco", "POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT"),
    ("E-mail", "EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS, DEFAULT_FROM_EMAIL"),
    ("Checkout", "MERCADO_PAGO_PUBLIC_KEY, MERCADO_PAGO_ACCESS_TOKEN, CHECKOUT_BASE_URL, CHECKOUT_DASHCREATOR_PRICE, CHECKOUT_CREATORDAY_PRICE"),
    ("Consultas", "APIBRASIL_CEP_URL/TOKEN, APIBRASIL_CNPJ_URL/TOKEN"),
    ("Portal e Desafio", "TCC_PORTAL_ADMIN_PASSWORD, TCC_PORTAL_ALLOWED_ORIGINS, DESAFIO_ALLOWED_ORIGINS"),
]

# -------------------------------------------------------------- pendências
RISCOS = [
    ("alta", "Repositório do GitHub público", "Tem arquivos de banco de desenvolvimento e a senha padrão da mentora no código. Decisão: mudar depois (o deploy usa GitHub App e não quebra)."),
    ("alta", "Senha da mentora do Portal", "Trocar e definir TCC_PORTAL_ADMIN_PASSWORD no Coolify; hoje pode valer a senha padrão do código."),
    ("alta", "Falha de segurança no painel do Desafio (XSS)", "O nome das participantes aparece no top 10 e nas atividades sem proteção."),
    ("alta", "Sem backup automático do banco", "Decisão de 16/09: não configurar agora. Se o disco falhar, os dados vão junto."),
    ("alta", "Disco pequeno no servidor principal", "Cada deploy do sistema ocupa cerca de 3,7 GB. Rodar a limpeza depois de vários pushes."),
    ("media", "Página de vendas do Dash", "Código-fonte perdido (Lovable), título \"Lovable App\" nas redes, imagem de compartilhamento quebrada, \"Testar grátis\" leva a checkout pago."),
    ("media", "Conversão não medida", "Checkouts sem Pixel e sem métrica; home, Planner e Creator Day sem Pixel."),
    ("media", "Link antigo do Creator Day no Mercado Pago", "O mpago.la continua ativo: quem pagar por ele não aparece no sistema."),
    ("media", "Regras do Desafio", "Posts sem limite de pontos, check-in fora das datas, código de indicação igual ao de login, ranking público."),
    ("media", "Portal do TCC fora do git", "Front em container manual; rascunhos e progresso de todas chegam ao navegador de qualquer aluna."),
    ("media", "layfeamorim.com", "Publicação na segunda VPS e Apps Script dos formulários não documentados; formulário mostra sucesso mesmo se falhar."),
    ("media", "Prospecção sem campos de valor", "Valor gerado e ticket médio ficam zerados."),
    ("baixa", "Webhook do Mercado Pago sem assinatura", "Atenuado: o sistema reconsulta o pagamento antes de confirmar."),
    ("baixa", "Logins sem limite de tentativas", "Desafio, Portal e painel."),
    ("baixa", "Métricas aceitam registro de qualquer lugar", "Dá para poluir os números de propósito."),
]

RESOLVIDOS = [
    "Creator comum conseguia virar conta interna e ver compradores do Creator Day",
    "Disco do servidor em 100% (limpo)",
    "Deploy travado na fila do Coolify",
    "Convite do piquenique com painel público e home antiga fora do ar",
    "Site publicado só por cópia manual: agora publica pelo git",
    "README e arquivos de configuração do site abriam no navegador",
    "Compras não apareciam no admin",
    "Formulário das prévias do Creator Day não salvava nada",
]

PONTAS = [
    "Os preços continuam valendo (Dash, Planner, Mentoria HPC, Renovação, Acompanhamento, Creator Day)?",
    "HPC é a High Performance Creator (página /hpc/). Acompanhamento TCC, mentoria UGC e Turma 01 são o mesmo produto?",
    "O Desafio Postaria Mais é gratuito? Qual é o prêmio? Quanto vale uma indicação?",
    "O Portal do TCC está em uso ou a área oficial é a Hubla?",
    "Endereço exato do Creator Day em Piatã.",
    "Para onde vai o e-mail de @thecreatorsclub.com.br?",
    "Quem tem acesso a Mercado Pago, Brevo, Cloudflare, Hostinger, Hetzner, Meta e à planilha Leads Layfe?",
    "Como se publica o layfeamorim.com na segunda VPS?",
    "Para que serve a Evolution API?",
]

CREATOR_DAY_DATA = date(2026, 10, 17)
NIVEIS_RISCO = (("alta", "alta"), ("media", "média"), ("baixa", "baixa"))

SITES_METRICAS = {"tcc": "Home do clube", "dash": "Página do Dash", "layfe": "layfeamorim.com", "portfolio": "Portfólio"}


def _com_barra(linhas):
    """Acrescenta a cada linha (rótulo, n, ...) a largura da barra: % do maior n da lista."""
    maior = max((linha[1] for linha in linhas), default=0)
    return [(*linha, round(linha[1] * 100 / maior) if maior else 0) for linha in linhas]


def _layfe_workspace():
    layfe = get_user_model().objects.filter(username="layfeamorim").first()
    membership = layfe.memberships.select_related("workspace").first() if layfe else None
    return membership.workspace if membership else None


def _checkout(chave: str) -> dict:
    qs = Purchase.objects.filter(product_key=chave)
    pagas = qs.filter(status=Purchase.STATUS_APPROVED)
    pendentes = qs.filter(status=Purchase.STATUS_PENDING)
    return {
        "iniciadas": qs.count(),
        "pagas": pagas.count(),
        "receita": pagas.aggregate(s=Sum("amount"))["s"] or Decimal("0"),
        "aguardando": pendentes.exclude(mp_payment_id="").count(),
        "nao_finalizou": pendentes.filter(mp_payment_id="").count(),
        "recusadas": qs.filter(status__in=[Purchase.STATUS_REJECTED, Purchase.STATUS_CANCELLED]).count(),
    }


def central_snapshot() -> dict:
    agora = timezone.localtime()
    hoje = agora.date()
    trinta = agora - timedelta(days=30)
    User = get_user_model()

    dash = {
        "usuarias": User.objects.filter(is_active=True).count(),
        "entraram_7": User.objects.filter(is_active=True, last_login__gte=agora - timedelta(days=7)).count(),
        "entraram_30": User.objects.filter(is_active=True, last_login__gte=trinta).count(),
        "cadastros_30": User.objects.filter(date_joined__gte=trinta).count(),
        "codigos_livres": AccessCode.objects.filter(is_active=True, assigned_user__isnull=True).count(),
        "codigos_usados": AccessCode.objects.filter(assigned_user__isnull=False).count(),
    }
    checkout = {chave: _checkout(chave) for chave in ("dashcreator", "creatorday", "hpc")}
    for dados in checkout.values():
        dados["receita_txt"] = brl(dados["receita"])
    receita_checkout = sum((d["receita"] for d in checkout.values()), Decimal("0"))
    lista_espera = EventWaitlistEntry.objects.filter(event_key=CREATOR_DAY_EVENT).count()

    # Desafio e Portal moram em outras apps; importados aqui para o studio não depender delas no carregamento.
    from desafio.models import CheckIn, Conclusao, Missao, Participante, Post
    from tcc_portal.models import Aluna, Duvida, Entrega, ProgressoAula

    missao_do_dia = Missao.objects.filter(data_liberacao__lte=hoje).order_by("-dia").first()
    desafio = {
        "inscritas": Participante.objects.filter(ativa=True).count(),
        "missoes": Missao.objects.count(),
        "missao_do_dia": f"Dia {missao_do_dia.dia}: {missao_do_dia.titulo}" if missao_do_dia else "Ainda não começou",
        "conclusoes": Conclusao.objects.count(),
        "posts": Post.objects.count(),
        "checkins_hoje": CheckIn.objects.filter(data=hoje).count(),
    }
    portal = {
        "alunas_ativas": Aluna.objects.filter(status=Aluna.STATUS_ATIVA).count(),
        "alunas_total": Aluna.objects.count(),
        "aulas_assistidas": ProgressoAula.objects.count(),
        "entregas": Entrega.objects.count(),
        "duvidas": Duvida.objects.count(),
    }

    from .metrics import _pretty_label

    eventos = PageEvent.objects.filter(created_at__gte=trinta)
    metricas = []
    for site, nome in SITES_METRICAS.items():
        do_site = eventos.filter(site=site)
        visitas = do_site.filter(kind="pageview")
        if not do_site.exists():
            continue
        metricas.append({
            "nome": nome,
            "visitas": visitas.count(),
            "visitantes": visitas.values("visitor").distinct().count(),
            "cliques": do_site.filter(kind="click").count(),
            "top_cliques": _com_barra([
                (_pretty_label(r["label"]), r["n"])
                for r in do_site.filter(kind="click").exclude(label="").values("label").annotate(n=Count("id")).order_by("-n")[:5]
            ]),
            "link": f"{APP}/metricas/?site={site}",
        })
    visitas_total = sum(m["visitas"] for m in metricas)

    ws = _layfe_workspace()
    negocio = None
    precos_info = {}
    vendas_info = {}
    if ws is not None:
        projetos_ano = Project.objects.filter(workspace=ws, close_date__year=hoje.year)
        prospects = Prospect.objects.filter(workspace=ws)
        leads = InfoLead.objects.filter(workspace=ws)
        por_etapa = dict(prospects.order_by().values_list("stage").annotate(n=Count("id")))
        leads_etapa = dict(leads.order_by().values_list("stage").annotate(n=Count("id")))
        confirmadas = InfoProductSale.objects.filter(workspace=ws, status=InfoProductSale.STATUS_CONFIRMED)
        for p in InfoProduct.objects.filter(workspace=ws):
            precos_info[p.name] = p.price
        for r in confirmadas.order_by().values("product__name").annotate(n=Count("id"), s=Sum("amount")):
            vendas_info[r["product__name"]] = (r["n"], r["s"] or Decimal("0"))
        negocio = {
            "trabalhos_ano": projetos_ano.count(),
            "valor_ano": brl(projetos_ano.aggregate(s=Sum("total_value"))["s"] or Decimal("0")),
            "prospeccao_total": prospects.count(),
            "prospeccao_etapas": _com_barra([(rotulo, por_etapa.get(valor, 0)) for valor, rotulo in PROSPECT_STAGE_CHOICES]),
            "crm_total": leads.count(),
            "crm_etapas": _com_barra([(rotulo, leads_etapa.get(valor, 0)) for valor, rotulo in InfoLead.STAGE_CHOICES]),
            "infoprodutos_vendas": confirmadas.count(),
            "infoprodutos_valor": brl(confirmadas.aggregate(s=Sum("amount"))["s"] or Decimal("0")),
            "por_produto": _com_barra([(nome, n, brl(s)) for nome, (n, s) in sorted(vendas_info.items(), key=lambda x: -x[1][0])]),
        }

    produtos = []
    for base in PRODUTOS:
        item = dict(base)
        if base.get("checkout"):
            produto = get_product(base["checkout"])
            item["preco"] = brl(produto.price) if produto else base.get("preco_fixo", "")
            dados = checkout[base["checkout"]]
            item["vendas"] = f"{dados['pagas']} paga(s) no checkout · {dados['receita_txt']}"
            if base.get("somar_lancadas") and base.get("infoproduto") in vendas_info:
                n, s = vendas_info[base["infoproduto"]]
                item["vendas"] += f" · {n} lançada(s) antes · {brl(s)}"
        elif base.get("infoproduto") and base["infoproduto"] in precos_info:
            item["preco"] = brl(precos_info[base["infoproduto"]])
        else:
            item["preco"] = base.get("preco_fixo", "")
        if base.get("infoproduto") in vendas_info and not base.get("checkout"):
            n, s = vendas_info[base["infoproduto"]]
            item["vendas"] = f"{n} venda(s) lançada(s) · {brl(s)}"
        produtos.append(item)

    cd = checkout["creatorday"]
    onde_ver = [
        ("Ingressos do Creator Day", f"{cd['pagas']} pagos · {cd['aguardando'] + cd['nao_finalizou']} em aberto", "Creator Day > Ingressos", APP + "/creator-day/?tab=ingressos"),
        ("Lista de espera do Creator Day", f"{lista_espera} na lista", "Creator Day > Lista de espera", APP + "/creator-day/?tab=lista"),
        ("Compras do Dash Creator", f"{checkout['dashcreator']['pagas']} pagas · {checkout['dashcreator']['iniciadas']} iniciadas", "Admin > Compras (dashcreator)", APP + "/admin/studio/purchase/?product_key=dashcreator"),
        ("Compras da Mentoria HPC", f"{checkout['hpc']['pagas']} pagas · {checkout['hpc']['iniciadas']} iniciadas", "Admin > Compras (hpc)", APP + "/admin/studio/purchase/?product_key=hpc"),
        ("Contas criadas no Dash", f"{dash['codigos_usados']} códigos usados · {dash['codigos_livres']} livres", "Admin > Access codes", APP + "/admin/studio/accesscode/"),
        ("Vendas da Hubla e do Nubank", f"{negocio['infoprodutos_vendas'] if negocio else 0} lançadas", "Infoprodutos > Entradas", APP + "/infoprodutos/"),
        ("Leads da mentoria e de serviços", f"{negocio['crm_total'] if negocio else 0} leads", "CRM", APP + "/crm/"),
        ("Marcas que pediram orçamento no portfólio", "Etapa Qualificação, canal Portfólio", "Prospecção da Layfe", APP + "/prospeccao/"),
        ("Inscritas do Desafio", f"{desafio['inscritas']} inscritas", "Painel da organizadora", SITE + "/desafio/admin.html"),
        ("Alunas do Portal do TCC", f"{portal['alunas_ativas']} ativas", "Portal > Admin > Matrículas", PORTAL),
        ("Lista de espera da mentoria UGC (layfeamorim.com)", "Planilha", "Planilha Google Leads Layfe", ""),
        ("Visitas e cliques dos sites", f"{visitas_total} visitas em 30 dias", "Métricas", APP + "/metricas/"),
    ]

    alertas = []
    if cd["nao_finalizou"] or cd["aguardando"]:
        alertas.append({
            "tom": "espera",
            "texto": f"{cd['nao_finalizou'] + cd['aguardando']} pessoa(s) começaram a comprar o ingresso do Creator Day e ainda não pagaram.",
            "link": APP + "/creator-day/?tab=ingressos", "acao": "Ver e chamar no WhatsApp",
        })
    hpc = checkout["hpc"]
    if hpc["nao_finalizou"] or hpc["aguardando"]:
        alertas.append({
            "tom": "espera",
            "texto": f"{hpc['nao_finalizou'] + hpc['aguardando']} pessoa(s) começaram a comprar a Mentoria HPC e ainda não pagaram.",
            "link": APP + "/admin/studio/purchase/?product_key=hpc", "acao": "Ver quem é",
        })
    inicio_desafio, fim_desafio = hoje.replace(month=9, day=14), hoje.replace(month=9, day=20)
    if hoje.year == 2026 and inicio_desafio <= hoje <= fim_desafio and desafio["inscritas"] < 20:
        alertas.append({
            "tom": "erro",
            "texto": f"Desafio Postaria Mais acontecendo ({desafio['missao_do_dia']}) com só {desafio['inscritas']} inscrita(s).",
            "link": SITE + "/desafio/admin.html", "acao": "Abrir o painel",
        })
    if dash["codigos_livres"] <= 1:
        alertas.append({
            "tom": "neutro",
            "texto": f"Só {dash['codigos_livres']} código de acesso livre para liberar o Dash sem compra.",
            "link": "#como-fazer", "acao": "Como gerar",
        })
    evento = evento_snapshot(cd, lista_espera)
    if evento["tarefas_atrasadas"]:
        alertas.insert(0, {
            "tom": "espera",
            "texto": f"{evento['tarefas_atrasadas']} tarefa(s) do Creator Day com prazo vencido.",
            "link": "#evento/tarefas", "acao": "Ver tarefas",
        })
    vencidos = [p for p in evento["pagamentos"] if p["vencido"]]
    if vencidos:
        alertas.insert(0, {
            "tom": "erro",
            "texto": f"{len(vencidos)} pagamento(s) de fornecedor do Creator Day vencido(s).",
            "link": "#evento/resumo", "acao": "Ver pagamentos",
        })
    riscos_altos = sum(1 for r in RISCOS if r[0] == "alta")
    alertas.append({
        "tom": "erro",
        "texto": f"{riscos_altos} riscos de prioridade alta em aberto (GitHub público, senha do Portal, falha no Desafio, backup e disco).",
        "link": "#pendencias", "acao": "Ver pendências",
    })

    return {
        "agora": agora,
        "secoes": SECOES,
        "niveis": [(nivel, rotulo, sum(1 for r in RISCOS if r[0] == nivel)) for nivel, rotulo in NIVEIS_RISCO],
        "creator_day_dias": (CREATOR_DAY_DATA - hoje).days,
        "evento": evento,
        "riscos_altos": riscos_altos,
        "cd_em_aberto": cd["nao_finalizou"] + cd["aguardando"],
        "dash": dash,
        "checkout": checkout,
        "receita_checkout": brl(receita_checkout),
        "lista_espera": lista_espera,
        "desafio": desafio,
        "portal": portal,
        "metricas": metricas,
        "visitas_total": visitas_total,
        "negocio": negocio,
        "produtos": produtos,
        "onde_ver": onde_ver,
        "alertas": alertas,
        "links": LINKS,
        "guias": GUIAS,
        "modulos": MODULOS,
        "regras_acesso": REGRAS_ACESSO,
        "servidores": SERVIDORES,
        "dominios": DOMINIOS,
        "integracoes": INTEGRACOES,
        "acessos": ACESSOS,
        "variaveis": VARIAVEIS,
        "riscos": RISCOS,
        "resolvidos": RESOLVIDOS,
        "pontas": PONTAS,
    }
