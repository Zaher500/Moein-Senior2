import secrets

from django.conf import settings
from django.http import JsonResponse


class GatewaySecretMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        expected_secret = getattr(settings, "GATEWAY_SECRET", None)
        provided_secret = request.headers.get("X-GATEWAY-SECRET")

        if (
            not expected_secret
            or not provided_secret
            or not secrets.compare_digest(
                str(provided_secret),
                str(expected_secret),
            )
        ):
            return JsonResponse(
                {
                    "error": (
                        "Direct access forbidden, use API Gateway"
                    )
                },
                status=403,
            )

        return self.get_response(request)
