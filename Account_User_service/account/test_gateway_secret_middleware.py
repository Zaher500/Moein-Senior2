from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from .middleware import GatewaySecretMiddleware


@override_settings(GATEWAY_SECRET="test-gateway-secret")
class GatewaySecretMiddlewareTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = GatewaySecretMiddleware(
            lambda request: HttpResponse("allowed")
        )

    def test_internal_admin_authorize_bypasses_gateway_secret(self):
        request = self.factory.post(
            "/api/internal/admin/authorize/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_regular_endpoint_requires_gateway_secret(self):
        request = self.factory.get("/api/me/")

        response = self.middleware(request)

        self.assertEqual(response.status_code, 403)

    def test_similar_internal_path_cannot_bypass(self):
        request = self.factory.post(
            "/api/internal/admin/authorize/other/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 403)

    def test_valid_gateway_secret_allows_regular_request(self):
        request = self.factory.get(
            "/api/me/",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_internal_token_validation_bypasses_gateway_secret(self):
        request = self.factory.post(
            "/api/internal/token/validate/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)


    def test_similar_token_validation_path_cannot_bypass(self):
        request = self.factory.post(
            "/api/internal/token/validate/other/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 403)