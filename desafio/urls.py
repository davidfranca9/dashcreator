from django.urls import path

from . import views

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
]
