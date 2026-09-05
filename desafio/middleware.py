from django.conf import settings
from django.http import HttpResponse


class DesafioCorsMiddleware:
    """CORS restrito a rota /desafio/ e as origens do site estatico."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.META.get("HTTP_ORIGIN", "")
        is_desafio_path = request.path.startswith("/desafio/")
        allowed = is_desafio_path and origin in settings.DESAFIO_ALLOWED_ORIGINS

        if is_desafio_path and request.method == "OPTIONS":
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)

        if allowed:
            response["Access-Control-Allow-Origin"] = origin
            response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response["Access-Control-Max-Age"] = "86400"
            response["Vary"] = "Origin"
        return response
