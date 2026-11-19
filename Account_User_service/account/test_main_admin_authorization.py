from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from account.authorization import require_main_admin
from account.models import User


class MainAdminAuthorizationTests(SimpleTestCase):

    def setUp(self):
        self.request = object()

    @patch("account.authorization.get_user_from_token")
    def test_missing_authentication_is_rejected(self, mock_get_user):
        mock_get_user.return_value = None

        with self.assertRaises(AuthenticationFailed):
            require_main_admin(self.request)

    @patch("account.authorization.get_user_from_token")
    def test_student_is_rejected(self, mock_get_user):
        mock_get_user.return_value = SimpleNamespace(
            role=User.Role.STUDENT,
            must_change_password=False,
        )

        with self.assertRaises(PermissionDenied):
            require_main_admin(self.request)

    @patch("account.authorization.get_user_from_token")
    def test_regular_admin_is_rejected(self, mock_get_user):
        mock_get_user.return_value = SimpleNamespace(
            role=User.Role.ADMIN,
            must_change_password=False,
        )

        with self.assertRaises(PermissionDenied):
            require_main_admin(self.request)

    @patch("account.authorization.get_user_from_token")
    def test_main_admin_is_allowed(self, mock_get_user):
        main_admin = SimpleNamespace(
            role=User.Role.MAIN_ADMIN,
            must_change_password=False,
        )
        mock_get_user.return_value = main_admin

        result = require_main_admin(self.request)

        self.assertIs(result, main_admin)

    @patch("account.authorization.get_user_from_token")
    def test_main_admin_must_change_password_is_rejected(self, mock_get_user):
        mock_get_user.return_value = SimpleNamespace(
            role=User.Role.MAIN_ADMIN,
            must_change_password=True,
        )

        with self.assertRaises(PermissionDenied):
            require_main_admin(self.request)