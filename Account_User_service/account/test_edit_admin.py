
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from account.models import User


@override_settings(GATEWAY_SECRET="test-gateway-secret")
class EditAdminTests(APITestCase):

    def setUp(self):
        self.main_admin = User(
            username="main_admin_test",
            email="main_admin_test@example.com",
            role=User.Role.MAIN_ADMIN,
            must_change_password=False,
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

    @patch("account.authorization.get_user_from_token")
    def test_main_admin_can_edit_admin(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/edit/",
            {
                "username": "updated_admin_test",
                "email": "updated_admin@example.com",
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)

        self.admin.refresh_from_db()

        self.assertEqual(
            self.admin.username,
            "updated_admin_test",
        )
        self.assertEqual(
            self.admin.email,
            "updated_admin@example.com",
        )

        # The admin role must remain unchanged.
        self.assertEqual(
            self.admin.role,
            User.Role.ADMIN,
        )

        # Editing profile information must not change the password.
        self.assertTrue(
            self.admin.check_password("StrongPassword123!")
        )


    @patch("account.authorization.get_user_from_token")
    def test_regular_admin_cannot_edit_admin(self, mock_get_user):
        mock_get_user.return_value = self.admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/edit/",
            {
                "username": "hacked_admin",
                "email": "hacked@example.com",
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 403)

        self.admin.refresh_from_db()

        self.assertEqual(
            self.admin.username,
            "regular_admin_test",
        )
        self.assertEqual(
            self.admin.email,
            "regular_admin_test@example.com",
        )

    @patch("account.authorization.get_user_from_token")
    def test_main_admin_cannot_be_edited(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.main_admin.user_id}/edit/",
            {
                "username": "changed_main_admin",
                "email": "changed_main@example.com",
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 404)

        self.main_admin.refresh_from_db()

        self.assertEqual(
            self.main_admin.username,
            "main_admin_test",
        )
        self.assertEqual(
            self.main_admin.email,
            "main_admin_test@example.com",
        )


    @patch("account.authorization.get_user_from_token")
    def test_duplicate_username_is_rejected(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/edit/",
            {
                "username": "main_admin_test",
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.admin.refresh_from_db()

        self.assertEqual(
            self.admin.username,
            "regular_admin_test",
        )

    @patch("account.authorization.get_user_from_token")
    def test_duplicate_email_is_rejected(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/edit/",
            {
                "email": "MAIN_ADMIN_TEST@example.com",
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.admin.refresh_from_db()

        self.assertEqual(
            self.admin.email,
            "regular_admin_test@example.com",
        )

    @patch("account.authorization.get_user_from_token")
    def test_sensitive_fields_cannot_be_modified(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/edit/",
            {
                "username": "modified_admin",
                "role": "MAIN_ADMIN",
                "password": "SomeOtherPassword123!",
                "permissions": ["DELETE_STUDENTS"],
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.admin.refresh_from_db()

        self.assertEqual(
            self.admin.username,
            "regular_admin_test",
        )
        self.assertEqual(
            self.admin.role,
            User.Role.ADMIN,
        )
        self.assertTrue(
            self.admin.check_password("StrongPassword123!")
        )
        self.assertFalse(
            self.admin.admin_permissions.exists()
        )
