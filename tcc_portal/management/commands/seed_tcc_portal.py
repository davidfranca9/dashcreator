from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from tcc_portal.models import (
    Aluna,
    Aula,
    ChecklistItem,
    Config,
    Desafio,
    Material,
    Tarefa,
)

CHECKLIST_ITENS = [
    ("onboarding", "Ferramentas essenciais configuradas"),
    ("onboarding", "Perfil da agência/marca preenchido"),
    ("metodo", "Sistema de organização semanal definido"),
    ("metodo", "Rotina de conteúdo estruturada"),
    ("narrativa", "Narrativa central definida e validada"),
    ("narrativa", "Posicionamento e diferencial escritos"),
    ("calendario", "Pilares de conteúdo definidos"),
    ("calendario", "Calendário editorial do mês montado"),
    ("roteiros", "Primeiro lote de roteiros escrito"),
    ("roteiros", "Roteiros revisados e prontos para gravar"),
    ("perfil", "Perfil estruturado (bio, destaques, feed)"),
    ("perfil", "Link na bio e CTAs organizados"),
    ("prospeccao", "Lista de prospecção ativa montada"),
    ("prospeccao", "Primeiras abordagens enviadas"),
    ("laboratorio", "Métricas da fase analisadas"),
    ("laboratorio", "Ajustes de estratégia registrados"),
]

DEFAULT_AULAS = [
    dict(fase_id="onboarding", titulo="Boas-vindas à jornada TCC", descricao="Conheça o método, a dinâmica da mentoria e como aproveitar cada espaço do portal.", url="#", duracao=18, status="publicada", destaque=True),
    dict(fase_id="onboarding", titulo="Seu ambiente de trabalho", descricao="Configure as ferramentas que vão sustentar sua rotina de conteúdo e atendimento.", url="#", duracao=26, status="publicada", destaque=False),
    dict(fase_id="metodo", titulo="Rotina leve e sustentável", descricao="Monte uma semana possível para produzir, publicar e prospectar com consistência.", url="#", duracao=34, status="publicada", destaque=True),
    dict(fase_id="narrativa", titulo="Encontrando sua narrativa central", descricao="Transforme repertório e experiência em uma mensagem clara, própria e reconhecível.", url="#", duracao=42, status="publicada", destaque=True),
    dict(fase_id="calendario", titulo="Calendário editorial estratégico", descricao="Conecte objetivos, pilares e formatos em um calendário que você realmente consegue executar.", url="#", duracao=37, status="rascunho", destaque=False),
]

DEFAULT_MATERIAIS = [
    dict(fase_id="onboarding", titulo="Boas-vindas ao TCC", tipo="video", descricao="Como funciona a mentoria, o que esperar de cada fase e como usar o portal.", url="#"),
    dict(fase_id="onboarding", titulo="Configurando suas ferramentas de trabalho", tipo="pdf", descricao="Contas e apps essenciais para começar a produzir com o método do TCC.", url="#"),
    dict(fase_id="metodo", titulo="Como organizar sua rotina de criadora", tipo="video", descricao="Sistema semanal para dar conta de gravar, editar, postar e prospectar.", url="#"),
    dict(fase_id="metodo", titulo="Modelo de agenda semanal", tipo="modelo", descricao="Planilha para distribuir gravação, edição e postagem ao longo da semana.", url="#"),
    dict(fase_id="narrativa", titulo="Como encontrar sua narrativa central", tipo="video", descricao="O fio condutor que vai aparecer em tudo o que você postar.", url="#"),
    dict(fase_id="narrativa", titulo="Perguntas para descobrir seu diferencial", tipo="pdf", descricao="Roteiro de perguntas para destravar sua narrativa.", url="#"),
    dict(fase_id="calendario", titulo="Montando seu calendário editorial", tipo="video", descricao="Como planejar pilares de conteúdo e distribuir ao longo do mês.", url="#"),
    dict(fase_id="calendario", titulo="Modelo de calendário editorial", tipo="modelo", descricao="Planilha pronta para preencher com pilares e datas de postagem.", url="#"),
    dict(fase_id="roteiros", titulo="Estrutura de roteiro que prende atenção", tipo="pdf", descricao="Gancho, desenvolvimento e CTA para roteiros orgânicos.", url="#"),
    dict(fase_id="roteiros", titulo="Banco de ganchos para roteiros", tipo="link", descricao="Aberturas testadas para adaptar aos seus próprios vídeos.", url="#"),
    dict(fase_id="perfil", titulo="Como estruturar um perfil que converte", tipo="video", descricao="Bio, destaques e feed pensados para quem chega até você.", url="#"),
    dict(fase_id="perfil", titulo="Checklist de perfil", tipo="pdf", descricao="Itens para revisar antes de considerar o perfil pronto.", url="#"),
    dict(fase_id="prospeccao", titulo="Como prospectar sem parecer forçada", tipo="video", descricao="Abordagem natural para conversar com clientes em potencial.", url="#"),
    dict(fase_id="prospeccao", titulo="Modelos de mensagem de prospecção", tipo="modelo", descricao="Textos de abertura para adaptar ao seu tom de voz.", url="#"),
    dict(fase_id="laboratorio", titulo="Como ler suas métricas", tipo="video", descricao="O que observar nos números antes de mudar de estratégia.", url="#"),
    dict(fase_id="laboratorio", titulo="Planilha de acompanhamento de resultados", tipo="modelo", descricao="Registro mês a mês do que funcionou e do que não funcionou.", url="#"),
]

DEFAULT_TAREFAS = [
    dict(fase_id="onboarding", titulo="Concluir onboarding e configurar ferramentas", prazo="2026-08-07", prioridade="alta", descricao="Criar as contas necessárias e revisar como o portal funciona."),
    dict(fase_id="metodo", titulo="Montar sua rotina semanal de criadora", prazo="2026-08-14", prioridade="media", descricao="Definir dias e horários fixos para gravar, editar e postar."),
    dict(fase_id="narrativa", titulo="Escrever sua narrativa central", prazo="2026-08-21", prioridade="alta", descricao="Um parágrafo que resume o fio condutor do seu conteúdo."),
    dict(fase_id="calendario", titulo="Entregar o calendário editorial do mês", prazo="2026-08-28", prioridade="alta", descricao="Pilares de conteúdo e datas de postagem definidos."),
    dict(fase_id="roteiros", titulo="Escrever o primeiro lote de roteiros", prazo="2026-09-04", prioridade="media", descricao="Ao menos 5 roteiros prontos para gravar."),
    dict(fase_id="perfil", titulo="Estruturar o perfil completo", prazo="2026-09-11", prioridade="media", descricao="Bio, destaques e primeiros conteúdos fixados."),
    dict(fase_id="prospeccao", titulo="Enviar as primeiras 10 prospecções", prazo="2026-09-18", prioridade="media", descricao="Usar os modelos de mensagem como ponto de partida."),
    dict(fase_id="laboratorio", titulo="Registrar a primeira leitura de resultados", prazo="2026-09-25", prioridade="baixa", descricao="O que funcionou e o que ajustar para o próximo ciclo."),
]

DEFAULT_DESAFIOS = [
    dict(titulo="Desafio do Gancho Perfeito", descricao="Escreva 3 ganchos diferentes para o mesmo roteiro e poste na área de dúvidas para a turma opinar sobre qual prende mais."),
    dict(titulo="Desafio dos 7 Dias de Postagem", descricao="Poste um conteúdo por dia durante uma semana e registre no Painel de Evolução o que você percebeu."),
    dict(titulo="Desafio do Perfil Espelho", descricao="Peça para uma colega olhar seu perfil por 30 segundos e listar o que ela entendeu sobre você."),
    dict(titulo="Desafio da Prospecção Cruzada", descricao="Troque sua lista de prospecção com uma colega e sugiram abordagens uma para a outra."),
]

DEFAULT_AVISO = (
    "Bem-vindas ao TCC! Este é o portal de vocês para acompanhar a jornada: aulas, materiais organizados "
    "por fase, tarefas, desafios, o mural de entregas, o painel de evolução e um espaço para tirar dúvidas, "
    "de vocês para vocês, e comigo também. Qualquer ajuste que precisarem, me chamem."
)

ALUNAS_INICIAIS = [
    dict(nome="V. S. Lima", email="vslima00@gmail.com", turma="Turma 01", data_entrada="2026-08-03", status="ativa", codigo="TCCVSL7", notas="Nome provisório — completar no Admin."),
    dict(nome="Anna Prieto", email="annaprietougc@gmail.com", turma="Turma 01", data_entrada="2026-08-03", status="ativa", codigo="TCCANP4"),
    dict(nome="Ariana", email="contatoariana@hotmail.com", turma="Turma 01", data_entrada="2026-08-03", status="ativa", codigo="TCCARI8"),
]


class Command(BaseCommand):
    help = "Popula o Portal do TCC com o conteúdo padrão (só cria o que ainda não existe, seguro rodar de novo)."

    @transaction.atomic
    def handle(self, *args, **options):
        cfg = Config.obter()
        if not cfg.aviso_mentora:
            cfg.aviso_mentora = DEFAULT_AVISO
            cfg.fase_atual_id = "onboarding"
            cfg.save()
            self.stdout.write("Config inicial criada.")

        if not Aula.objects.exists():
            for idx, dados in enumerate(DEFAULT_AULAS):
                Aula.objects.create(ordem=idx, **dados)
            self.stdout.write(f"{len(DEFAULT_AULAS)} aulas criadas.")

        if not Material.objects.exists():
            for dados in DEFAULT_MATERIAIS:
                Material.objects.create(**dados)
            self.stdout.write(f"{len(DEFAULT_MATERIAIS)} materiais criados.")

        if not Tarefa.objects.exists():
            for dados in DEFAULT_TAREFAS:
                dados = {**dados, "prazo": date.fromisoformat(dados["prazo"])}
                Tarefa.objects.create(**dados)
            self.stdout.write(f"{len(DEFAULT_TAREFAS)} tarefas criadas.")

        if not Desafio.objects.exists():
            for dados in DEFAULT_DESAFIOS:
                Desafio.objects.create(**dados)
            self.stdout.write(f"{len(DEFAULT_DESAFIOS)} desafios criados.")

        if not ChecklistItem.objects.exists():
            for fase_id, texto in CHECKLIST_ITENS:
                ChecklistItem.objects.create(fase_id=fase_id, texto=texto)
            self.stdout.write(f"{len(CHECKLIST_ITENS)} itens de checklist criados.")

        criadas = 0
        for dados in ALUNAS_INICIAIS:
            dados = {**dados, "data_entrada": date.fromisoformat(dados["data_entrada"])}
            _, criada = Aluna.objects.get_or_create(email=dados["email"], defaults=dados)
            criadas += int(criada)
        if criadas:
            self.stdout.write(f"{criadas} alunas iniciais criadas.")

        self.stdout.write(self.style.SUCCESS("Seed do Portal do TCC concluído."))
