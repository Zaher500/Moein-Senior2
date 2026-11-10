
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from account.models import User


@override_settings(GATEWAY_SECRET="test-gateway-secret")
class DeleteAdminTests(APITestCase):

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
    def test_main_admin_can_deactivate_admin(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/deactivate/",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.data["message"],
            "Admin deactivated successfully",
        )

        self.assertEqual(
            response.data["user_id"],
            str(self.admin.user_id),
        )

        # Admin must still exist in database.
        self.admin.refresh_from_db()

        # Admin must be deactivated.
        self.assertFalse(self.admin.is_active)

        # MAIN_ADMIN must remain active.
        self.main_admin.refresh_from_db()
        self.assertTrue(self.main_admin.is_active)




    @patch("account.authorization.get_user_from_token")
    def test_regular_admin_cannot_deactivate_admin(self, mock_get_user):
        mock_get_user.return_value = self.admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/deactivate/",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        # Regular ADMIN must not have permission.
        self.assertEqual(response.status_code, 403)

        # Account must still exist and remain active.
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)



    @patch("account.authorization.get_user_from_token")
    def test_main_admin_cannot_be_deactivated(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.main_admin.user_id}/deactivate/",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        # MAIN_ADMIN is not a valid deactivation target.
        self.assertEqual(response.status_code, 404)

        # MAIN_ADMIN must remain active.
        self.main_admin.refresh_from_db()
        self.assertTrue(self.main_admin.is_active)
        self.assertEqual(
            self.main_admin.role,
            User.Role.MAIN_ADMIN,
        )



    @patch("account.authorization.get_user_from_token")
    def test_deactivate_nonexistent_admin_returns_404(self, mock_get_user):
        from uuid import uuid4

        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{uuid4()}/deactivate/",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 404)

        # Existing admin must remain active.
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)



    @patch("account.authorization.get_user_from_token")
    def test_deactivate_already_inactive_admin(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        url = f"/api/admin/{self.admin.user_id}/deactivate/"

        # First deactivation
        response = self.client.patch(
            url,
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)

        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)

        updated_at = self.admin.updated_at

        # Second deactivation
        response = self.client.patch(
            url,
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "Admin deactivated successfully",
        )

        # Account must remain inactive without another update
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)
        self.assertEqual(self.admin.updated_at, updated_at)


    @patch("account.authorization.get_user_from_token")
    def test_deactivate_already_inactive_admin(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        url = f"/api/admin/{self.admin.user_id}/deactivate/"

        # First deactivation
        response = self.client.patch(
            url,
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)

        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)

        updated_at = self.admin.updated_at

        # Second deactivation
        response = self.client.patch(
            url,
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["message"],
            "Admin deactivated successfully",
        )

        # Account must remain inactive without another update
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)
        self.assertEqual(self.admin.updated_at, updated_at)


    @patch("account.authorization.get_user_from_token")
    def test_legacy_delete_endpoint_is_disabled(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.delete(
            f"/api/admin/{self.admin.user_id}/delete/",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        # Old hard-delete endpoint must no longer exist.
        self.assertEqual(response.status_code, 404)

        # Admin must remain in the database.
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
