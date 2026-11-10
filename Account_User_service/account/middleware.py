from django.conf import settings
from django.http import JsonResponse


class GatewaySecretMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Internal admin authorization uses a separate service secret.
        # The endpoint itself validates X-INTERNAL-SERVICE-SECRET.
        if request.path in (
            "/api/internal/admin/authorize/",
            "/api/internal/token/validate/",          #admin
        ):
            return self.get_response(request)

        secret = request.headers.get("X-GATEWAY-SECRET")

        if secret != settings.GATEWAY_SECRET:
            return JsonResponse(
                {"error": "Direct access forbidden, use API Gateway"},
                status=403,
            )

        return self.get_response(request)
