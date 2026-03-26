# UGC Management SaaS

Reescrita completa do sistema em Django, preparada para web e pronta para deploy em servidor Hetzner com Docker Compose.

## O que esta pronto

- Dashboard com cards, grafico de faturamento, pipeline e atividade recente
- Prospeccao com leads por etapa e conversao para projeto
- Trabalhos com projetos ativos e entregues
- Financeiro com agenda de recebimentos e distribuicao do caixa
- Relatorios com indicadores estrategicos
- Configuracoes persistidas por workspace
- Login, criacao de conta e workspace automatico
- Estrutura Docker para subir com PostgreSQL + Caddy

## Rodando localmente

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Abra `http://127.0.0.1:8000/signup/` para criar a primeira conta.

## Importando os dados do app desktop antigo

1. Crie ou acesse um usuario no novo sistema.
2. Rode o comando:

```powershell
python manage.py import_legacy_data --username SEU_USUARIO --db-path ugc_management.db
```

Isso importa `prospects`, `projects` e `app_settings` para o workspace do usuario informado.

## Deploy no Hetzner

1. Copie `.env.example` para `.env` e ajuste dominios, senhas e hosts.
2. Garanta que o dominio esteja apontando para o IP do servidor.
3. Suba a stack:

```bash
docker compose up -d --build
```

4. O Caddy vai expor o app nas portas `80` e `443`.
5. O container `web` roda:

- `python manage.py migrate`
- `python manage.py collectstatic`
- bootstrap opcional do admin via variaveis `DJANGO_SUPERUSER_*`
- `gunicorn ugc_saas.wsgi:application`

## Estrutura principal

- `ugc_saas/`: configuracao do projeto Django
- `studio/`: app principal do produto
- `compose.yaml`: stack pronta para Hetzner
- `Dockerfile`: build da aplicacao
- `Caddyfile`: reverse proxy com HTTPS
- `ugc_management/`: codigo legado desktop mantido apenas como referencia

## Observacao

O sistema novo foi pensado para web e multi-workspace simples. O codigo legado desktop continua no repo apenas para consulta e migracao de dados, mas o caminho principal agora e o Django.
