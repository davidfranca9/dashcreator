from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from studio.views import logout_view, serve_media_file

urlpatterns = [
    path("admin/", admin.site.urls),
    path("media/<path:path>", serve_media_file, name="serve_media_file"),
    path("logout/", logout_view, name="logout"),
    path("tcc/", include("tcc_portal.urls")),
    path("desafio/", include("desafio.urls")),
    path("", include("studio.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
