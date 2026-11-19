
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from account.models import User, AdminPermission


@override_settings(GATEWAY_SECRET="test-gateway-secret")
class ListAdminsTests(APITestCase):

    def setUp(self):
        self.main_admin = User(
            username="main_admin_test",
            email="main_admin_test@example.com",
            role=User.Role.MAIN_ADMIN,
        )
        self.main_admin.set_password("StrongPassword123!")
        self.main_admin.save()

        self.admin = User(
            username="regular_admin_test",
            email="regular_admin_test@example.com",
            role=User.Role.ADMIN,
            must_change_password=False,
        )
        self.admin.set_password("StrongPassword123!")
        self.admin.save()

        permission = AdminPermission.objects.get(
            code=AdminPermission.Code.VIEW_STUDENTS
        )
        self.admin.admin_permissions.add(permission)

    @patch("account.authorization.get_user_from_token")
    def test_main_admin_can_list_admins(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.get(
            "/api/admin/list/",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)

        admins = response.data["admins"]

        self.assertEqual(len(admins), 1)
        self.assertEqual(
            admins[0]["username"],
            "regular_admin_test",
        )
        self.assertEqual(
            admins[0]["role"],
            "ADMIN",
        )
        self.assertEqual(
            admins[0]["permissions"],
            ["VIEW_STUDENTS"],
        )

        self.assertNotIn("password", admins[0])


    @patch("account.authorization.get_user_from_token")
    def test_list_admins_includes_active_and_inactive_accounts(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        # Create an inactive admin
        inactive_admin = User(
            username="inactive_admin_test",
            email="inactive_admin_test@example.com",
            role=User.Role.ADMIN,
            is_active=False,
        )
        inactive_admin.set_password("StrongPassword123!")
        inactive_admin.save()

        response = self.client.get(
            "/api/admin/list/",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)

        admins = {
            admin["username"]: admin
            for admin in response.data["admins"]
        }

        # Both accounts must appear
        self.assertEqual(len(admins), 2)
        self.assertIn("regular_admin_test", admins)
        self.assertIn("inactive_admin_test", admins)

        # Each account must have its correct status
        self.assertTrue(admins["regular_admin_test"]["is_active"])
        self.assertFalse(admins["inactive_admin_test"]["is_active"])

        # Existing permissions must remain unchanged
        self.assertEqual(
            admins["regular_admin_test"]["permissions"],
            ["VIEW_STUDENTS"],
        )
