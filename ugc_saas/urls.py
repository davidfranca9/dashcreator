from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from studio.views import logout_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("logout/", logout_view, name="logout"),
    path("", include("studio.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
