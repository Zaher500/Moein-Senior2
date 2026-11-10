import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied


@override_settings(
    INTERNAL_SERVICE_SECRET="test-internal-secret"
)
class InternalAdminAuthorizeTests(SimpleTestCase):

    def send_request(self, permission="VIEW_STUDENTS", secret=None):
        headers = {}

        if secret is not None:
            headers["HTTP_X_INTERNAL_SERVICE_SECRET"] = secret

        return self.client.post(
            "/api/internal/admin/authorize/",
            data=json.dumps({"permission": permission}),
            content_type="application/json",
            **headers,
        )

    @patch("account.internal_admin_views.require_admin_permission")
    def test_missing_secret_is_rejected(self, mock_authorize):
        response = self.send_request()

        self.assertEqual(response.status_code, 403)
        mock_authorize.assert_not_called()

    @patch("account.internal_admin_views.require_admin_permission")
    def test_invalid_secret_is_rejected(self, mock_authorize):
        response = self.send_request(
            secret="wrong-secret"
        )

        self.assertEqual(response.status_code, 403)
        mock_authorize.assert_not_called()

    @override_settings(INTERNAL_SERVICE_SECRET="")
    def test_unconfigured_secret_is_rejected(self):
        response = self.send_request(
            secret="test-internal-secret"
        )

        self.assertEqual(response.status_code, 503)

    @patch("account.internal_admin_views.require_admin_permission")
    def test_invalid_permission_is_rejected(self, mock_authorize):
        response = self.send_request(
            permission="INVALID_PERMISSION",
            secret="test-internal-secret",
        )

        self.assertEqual(response.status_code, 400)
        mock_authorize.assert_not_called()

    @patch("account.internal_admin_views.require_admin_permission")
    def test_authorized_admin_is_allowed(self, mock_authorize):
        mock_authorize.return_value = SimpleNamespace(
            user_id="test-admin-id"
        )

        response = self.send_request(
            permission="VIEW_STUDENTS",
            secret="test-internal-secret",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["authorized"], True)
        self.assertEqual(response.data["user_id"], "test-admin-id")
        self.assertEqual(
            response.data["permission"],
            "VIEW_STUDENTS",
        )

        mock_authorize.assert_called_once()
        self.assertEqual(
            mock_authorize.call_args.args[1],
            "VIEW_STUDENTS",
        )

    @patch("account.internal_admin_views.require_admin_permission")
    def test_permission_denied_is_rejected(self, mock_authorize):
        mock_authorize.side_effect = PermissionDenied(
            "Insufficient permissions"
        )

        response = self.send_request(
            permission="DELETE_STUDENTS",
            secret="test-internal-secret",
        )

        self.assertEqual(response.status_code, 403)