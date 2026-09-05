from django.urls import path

from . import admin_views, views

urlpatterns = [
    path("api/cadastro/", views.cadastro, name="desafio_cadastro"),
    path("api/login/", views.login, name="desafio_login"),
    path("api/reenviar-codigo/", views.reenviar_codigo, name="desafio_reenviar_codigo"),
    path("api/estado/", views.estado, name="desafio_estado"),
    path("api/checkin/", views.checkin, name="desafio_checkin"),
    path("api/missoes/<int:dia>/concluir/", views.concluir_missao, name="desafio_concluir_missao"),
    path("api/posts/", views.publicar, name="desafio_publicar"),
    path("api/posts/<int:post_id>/comentar/", views.comentar, name="desafio_comentar"),
    path("api/ranking/", views.ranking, name="desafio_ranking"),
    # Painel da organizadora (login de staff, token separado do da participante)
    path("api/admin/login/", admin_views.login_admin, name="desafio_admin_login"),
    path("api/admin/painel/", admin_views.painel, name="desafio_admin_painel"),
    path("api/admin/pontos/", admin_views.ajustar_pontos, name="desafio_admin_pontos"),
    path(
        "api/admin/participantes/<int:participante_id>/alternar/",
        admin_views.alternar_participante,
        name="desafio_admin_alternar_participante",
    ),
    path("api/admin/missoes/<int:dia>/data/", admin_views.mudar_data_missao, name="desafio_admin_missao_data"),
    path("api/admin/posts/<int:post_id>/remover/", admin_views.remover_post, name="desafio_admin_remover_post"),
    path(
        "api/admin/comentarios/<int:comentario_id>/remover/",
        admin_views.remover_comentario,
        name="desafio_admin_remover_comentario",
    ),
]
