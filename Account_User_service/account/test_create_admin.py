from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APITestCase

from account.models import User, AdminPermission


@override_settings(GATEWAY_SECRET="test-gateway-secret")
class CreateAdminTests(APITestCase):

    def setUp(self):
        self.main_admin = User(
            username="main_admin_test",
            email="main_admin_test@example.com",
            role=User.Role.MAIN_ADMIN,
            must_change_password=False,
        )
        self.main_admin.set_password("StrongMainAdminPassword123!")
        self.main_admin.save()

    @patch("account.authorization.get_user_from_token")
    def test_main_admin_can_create_admin(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        permission, _ = AdminPermission.objects.get_or_create(
            code=AdminPermission.Code.VIEW_STUDENTS
        )

        response = self.client.post(
            "/api/admin/create/",
            {
                "username": "new_admin",
                "email": "new_admin@example.com",
                "permissions": [permission.code],
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 201)

        admin = User.objects.get(username="new_admin")

        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.must_change_password)

        self.assertEqual(
            list(admin.admin_permissions.values_list("code", flat=True)),
            [AdminPermission.Code.VIEW_STUDENTS],
        )

        self.assertIn("temporary_password", response.data)

        temporary_password = response.data["temporary_password"]

        self.assertTrue(admin.check_password(temporary_password))
        self.assertNotEqual(admin.password, temporary_password)

    @patch("account.authorization.get_user_from_token")
    def test_regular_admin_cannot_create_admin(self, mock_get_user):
        regular_admin = User(
            username="regular_admin",
            email="regular@example.com",
            role=User.Role.ADMIN,
            must_change_password=False,
        )

        mock_get_user.return_value = regular_admin

        response = self.client.post(
            "/api/admin/create/",
            {
                "username": "unauthorized_admin",
                "email": "unauthorized@example.com",
                "permissions": [],
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            User.objects.filter(
                username="unauthorized_admin"
            ).exists()
        )

    @patch("account.authorization.get_user_from_token")
    def test_student_cannot_create_admin(self, mock_get_user):
        student = User(
            username="student_test",
            email="student@example.com",
            role=User.Role.STUDENT,
        )

        mock_get_user.return_value = student

        response = self.client.post(
            "/api/admin/create/",
            {
                "username": "unauthorized_admin",
                "email": "unauthorized@example.com",
                "permissions": [],
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 403)

        self.assertFalse(
            User.objects.filter(
                username="unauthorized_admin"
            ).exists()
        )

    @patch("account.authorization.get_user_from_token")
    def test_invalid_permission_is_rejected(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.post(
            "/api/admin/create/",
            {
                "username": "invalid_permission_admin",
                "email": "invalid@example.com",
                "permissions": ["INVALID_PERMISSION"],
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            User.objects.filter(
                username="invalid_permission_admin"
            ).exists()
        )

    @patch("account.authorization.get_user_from_token")
    def test_duplicate_permissions_are_rejected(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.post(
            "/api/admin/create/",
            {
                "username": "duplicate_permission_admin",
                "email": "duplicate@example.com",
                "permissions": [
                    AdminPermission.Code.VIEW_STUDENTS,
                    AdminPermission.Code.VIEW_STUDENTS,
                ],
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            User.objects.filter(
                username="duplicate_permission_admin"
            ).exists()
        )

    @patch("account.authorization.get_user_from_token")
    def test_duplicate_username_is_rejected(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.post(
            "/api/admin/create/",
            {
                "username": "main_admin_test",
                "email": "another_admin@example.com",
                "permissions": [],
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            User.objects.filter(
                email="another_admin@example.com"
            ).exists()
        )

    @patch("account.authorization.get_user_from_token")
    def test_duplicate_email_is_rejected(self, mock_get_user):
        mock_get_user.return_value = self.main_admin

        response = self.client.post(
            "/api/admin/create/",
            {
                "username": "another_admin",
                "email": "main_admin_test@example.com",
                "permissions": [],
            },
            format="json",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(response.status_code, 400)

        self.assertFalse(
            User.objects.filter(
                username="another_admin"
            ).exists()
        )