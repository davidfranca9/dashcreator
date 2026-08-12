from django.conf import settings
from django.http import HttpResponse


class TccPortalCorsMiddleware:
    """CORS bem restrito, só pra rota /tcc/ e só pra origem(ns) do portal estático."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.META.get("HTTP_ORIGIN", "")
        is_tcc_path = request.path.startswith("/tcc/")
        allowed = is_tcc_path and origin in settings.TCC_PORTAL_ALLOWED_ORIGINS

        if is_tcc_path and request.method == "OPTIONS":
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
