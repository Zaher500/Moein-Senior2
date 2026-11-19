
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from .authorization import require_admin_permission
from .models import User


class AdminAuthorizationTests(SimpleTestCase):

    def make_user(self, role, must_change_password=False, has_permission=False):
        permissions = MagicMock()
        permissions.filter.return_value.exists.return_value = has_permission

        return SimpleNamespace(
            role=role,
            must_change_password=must_change_password,
            admin_permissions=permissions,
        )

    def authorize(self, user):
        with patch(
            "account.authorization.get_user_from_token",
            return_value=user,
        ):
            return require_admin_permission(None, "EDIT_STUDENTS")

    def test_unauthenticated_user(self):
        with self.assertRaises(AuthenticationFailed):
            self.authorize(None)

    def test_student_cannot_access_admin(self):
        user = self.make_user(User.Role.STUDENT)

        with self.assertRaises(PermissionDenied):
            self.authorize(user)

    def test_admin_without_permission(self):
        user = self.make_user(User.Role.ADMIN, has_permission=False)

        with self.assertRaises(PermissionDenied):
            self.authorize(user)

    def test_admin_with_permission(self):
        user = self.make_user(User.Role.ADMIN, has_permission=True)

        result = self.authorize(user)

        self.assertIs(result, user)
        user.admin_permissions.filter.assert_called_once_with(
            code="EDIT_STUDENTS"
        )

    def test_main_admin_has_full_access(self):
        user = self.make_user(User.Role.MAIN_ADMIN)

        result = self.authorize(user)

        self.assertIs(result, user)
        user.admin_permissions.filter.assert_not_called()

    def test_temporary_password_blocks_admins(self):
        for role in (User.Role.ADMIN, User.Role.MAIN_ADMIN):
            with self.subTest(role=role):
                user = self.make_user(
                    role,
                    must_change_password=True,
                    has_permission=True,
                )

                with self.assertRaises(PermissionDenied):
                    self.authorize(user)
