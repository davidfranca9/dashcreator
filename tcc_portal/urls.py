from django.urls import path

from . import views

urlpatterns = [
    path("api/mentor/login/", views.mentor_login),
    path("api/aluna/login/", views.aluna_login),
    path("api/estado/", views.estado),

    path("api/conteudo/", views.config_update),
    path("api/abas/toggle/", views.aba_toggle),

    path("api/aulas/", views.aula_create),
    path("api/aulas/<int:pk>/", views.aula_update),
    path("api/aulas/<int:pk>/apagar/", views.aula_delete),
    path("api/aulas/<int:pk>/mover/", views.aula_mover),

    path("api/materiais/", views.material_create),
    path("api/materiais/<int:pk>/", views.material_update),
    path("api/materiais/<int:pk>/apagar/", views.material_delete),

    path("api/tarefas/", views.tarefa_create),
    path("api/tarefas/<int:pk>/", views.tarefa_update),
    path("api/tarefas/<int:pk>/apagar/", views.tarefa_delete),
    path("api/tarefas/<int:pk>/concluir/", views.tarefa_toggle),

    path("api/desafios/", views.desafio_create),
    path("api/desafios/<int:pk>/", views.desafio_update),
    path("api/desafios/<int:pk>/apagar/", views.desafio_delete),
    path("api/desafios/<int:pk>/status/", views.desafio_status_toggle),

    path("api/checklist/", views.checklist_create),
    path("api/checklist/<int:pk>/", views.checklist_update),
    path("api/checklist/<int:pk>/apagar/", views.checklist_delete),
    path("api/checklist/marcar/", views.checklist_toggle),

    path("api/alunas/", views.aluna_salvar),
    path("api/alunas/<int:pk>/regenerar-codigo/", views.aluna_regenerar_codigo),
    path("api/alunas/<int:pk>/impersonar/", views.aluna_impersonar),

    path("api/progresso-aula/", views.progresso_aula_toggle),

    path("api/entregas/", views.entrega_criar),
    path("api/entregas/<int:pk>/apagar/", views.entrega_apagar),

    path("api/evolucao/", views.evolucao_criar),
    path("api/evolucao/<int:pk>/apagar/", views.evolucao_apagar),

    path("api/duvidas/", views.duvida_criar),
    path("api/duvidas/<int:pk>/apagar/", views.duvida_apagar),
    path("api/duvidas/<int:pk>/responder/", views.duvida_responder),

    path("api/comentarios-aula/", views.comentario_aula_criar),
    path("api/comentarios-aula/<int:pk>/apagar/", views.comentario_aula_apagar),
]
