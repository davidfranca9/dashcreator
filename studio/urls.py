from django.urls import path

from .views import (
    AppLoginView,
    dashboard,
    finance,
    home,
    jobs,
    project_create,
    project_delete,
    project_edit,
    prospection,
    prospect_convert,
    prospect_create,
    prospect_delete,
    prospect_edit,
    reports,
    settings,
    signup,
)


urlpatterns = [
    path("", home, name="home"),
    path("login/", AppLoginView.as_view(), name="login"),
    path("signup/", signup, name="signup"),
    path("dashboard/", dashboard, name="dashboard"),
    path("prospeccao/", prospection, name="prospection"),
    path("prospeccao/novo/", prospect_create, name="prospect_create"),
    path("prospeccao/<int:pk>/editar/", prospect_edit, name="prospect_edit"),
    path("prospeccao/<int:pk>/excluir/", prospect_delete, name="prospect_delete"),
    path("prospeccao/<int:pk>/converter/", prospect_convert, name="prospect_convert"),
    path("trabalhos/", jobs, name="jobs"),
    path("trabalhos/novo/", project_create, name="project_create"),
    path("trabalhos/<int:pk>/editar/", project_edit, name="project_edit"),
    path("trabalhos/<int:pk>/excluir/", project_delete, name="project_delete"),
    path("financeiro/", finance, name="finance"),
    path("relatorios/", reports, name="reports"),
    path("configuracoes/", settings, name="settings"),
]
