from django.contrib import admin
from django.urls import include, path

from studio.views import logout_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("logout/", logout_view, name="logout"),
    path("", include("studio.urls")),
]
