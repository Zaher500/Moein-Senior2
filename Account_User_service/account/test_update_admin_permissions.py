
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from account.models import User, AdminPermission


@override_settings(GATEWAY_SECRET="test-gateway-secret")
class UpdateAdminPermissionsTests(APITestCase):

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

        old_permission = AdminPermission.objects.get(
            code=AdminPermission.Code.VIEW_STUDENTS
        )
        self.admin.admin_permissions.add(old_permission)

    @patch("account.authorization.get_user_from_token")
    def test_main_admin_can_update_permissions(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        new_permissions = [
            AdminPermission.Code.VIEW_COURSES,
            AdminPermission.Code.EDIT_COURSES,
        ]

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/permissions/",
            {"permissions": new_permissions},
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 200)

        self.admin.refresh_from_db()

        saved_permissions = set(
            self.admin.admin_permissions.values_list(
                "code", flat=True
            )
        )

        self.assertEqual(
            saved_permissions,
            set(new_permissions),
        )

        self.assertEqual(
            set(response.data["permissions"]),
            set(new_permissions),
        )


    @patch("account.authorization.get_user_from_token")
    def test_regular_admin_cannot_update_permissions(self, mock_get_user):
        mock_get_user.return_value = self.admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/permissions/",
            {
                "permissions": [
                    AdminPermission.Code.DELETE_STUDENTS
                ]
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 403)

        # Permissions must remain unchanged.
        self.assertEqual(
            set(self.admin.admin_permissions.values_list(
                "code", flat=True
            )),
            {AdminPermission.Code.VIEW_STUDENTS},
        )

    @patch("account.authorization.get_user_from_token")
    def test_main_admin_permissions_cannot_be_modified(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.main_admin.user_id}/permissions/",
            {
                "permissions": [
                    AdminPermission.Code.VIEW_COURSES
                ]
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        # This endpoint only targets regular ADMIN accounts.
        self.assertEqual(response.status_code, 404)

        self.assertFalse(
            self.main_admin.admin_permissions.exists()
        )


    @patch("account.authorization.get_user_from_token")
    def test_invalid_permission_is_rejected(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/permissions/",
            {
                "permissions": ["INVALID_PERMISSION"]
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            set(self.admin.admin_permissions.values_list(
                "code", flat=True
            )),
            {AdminPermission.Code.VIEW_STUDENTS},
        )

    @patch("account.authorization.get_user_from_token")
    def test_duplicate_permissions_are_rejected(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.patch(
            f"/api/admin/{self.admin.user_id}/permissions/",
            {
                "permissions": [
                    AdminPermission.Code.VIEW_COURSES,
                    AdminPermission.Code.VIEW_COURSES,
                ]
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.assertEqual(
            set(self.admin.admin_permissions.values_list(
                "code", flat=True
            )),
            {AdminPermission.Code.VIEW_STUDENTS},
        )
