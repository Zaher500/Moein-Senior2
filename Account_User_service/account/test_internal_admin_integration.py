import json

from django.test import TestCase, override_settings

from .auth import create_jwt_for_user
from .models import User, Student, AdminPermission


@override_settings(
    INTERNAL_SERVICE_SECRET="test-internal-secret",
    GATEWAY_SECRET="test-gateway-secret",
)
class InternalAdminIntegrationTests(TestCase):

    def setUp(self):
        self.permission, _ = AdminPermission.objects.get_or_create(
        code=AdminPermission.Code.VIEW_STUDENTS
        )

        self.student = self.create_user(
            "student_test",
            User.Role.STUDENT,
        )
        self.student_profile = Student.objects.create(
            user_id=self.student
        )

        self.admin = self.create_user(
            "admin_test",
            User.Role.ADMIN,
        )
        self.admin.admin_permissions.add(self.permission)

        self.admin_without_permission = self.create_user(
            "admin_no_permission",
            User.Role.ADMIN,
        )

        self.temporary_admin = self.create_user(
            "temporary_admin",
            User.Role.ADMIN,
            must_change_password=True,
        )
        self.temporary_admin.admin_permissions.add(self.permission)

        self.main_admin = self.create_user(
            "main_admin_test",
            User.Role.MAIN_ADMIN,
        )

    def create_user(
        self,
        username,
        role,
        must_change_password=False,
    ):
        user = User(
            username=username,
            email=f"{username}@example.com",
            role=role,
            must_change_password=must_change_password,
        )
        user.set_password("SecureTestP@ss123")
        user.save()
        return user

    def send_request(self, token, permission="VIEW_STUDENTS"):
        headers = {
            "HTTP_X_INTERNAL_SERVICE_SECRET": "test-internal-secret",
        }

        if token is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        return self.client.post(
            "/api/internal/admin/authorize/",
            data=json.dumps({"permission": permission}),
            content_type="application/json",
            **headers,
        )

    def token_for(self, user):
        if user.role == User.Role.STUDENT:
            return create_jwt_for_user(
                user,
                self.student_profile,
            )

        return create_jwt_for_user(user)

    def test_student_is_rejected(self):
        response = self.send_request(
            self.token_for(self.student)
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_with_permission_is_allowed(self):
        response = self.send_request(
            self.token_for(self.admin)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authorized"])
        self.assertEqual(
            response.json()["user_id"],
            str(self.admin.user_id),
        )

    def test_admin_without_permission_is_rejected(self):
        response = self.send_request(
            self.token_for(self.admin_without_permission)
        )

        self.assertEqual(response.status_code, 403)

    def test_temporary_password_admin_is_rejected(self):
        response = self.send_request(
            self.token_for(self.temporary_admin)
        )

        self.assertEqual(response.status_code, 403)

    def test_main_admin_is_allowed(self):
        response = self.send_request(
            self.token_for(self.main_admin)
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authorized"])

    def test_invalid_jwt_is_rejected(self):
        response = self.send_request("invalid.jwt.token")

        self.assertEqual(response.status_code, 401)

    def test_missing_jwt_is_rejected(self):
        response = self.send_request(None)

        self.assertEqual(response.status_code, 401)

    def test_revoked_permission_takes_effect_immediately(self):
        token = self.token_for(self.admin)

        first_response = self.send_request(token)
        self.assertEqual(first_response.status_code, 200)

        self.admin.admin_permissions.remove(self.permission)

        second_response = self.send_request(token)
        self.assertEqual(second_response.status_code, 403)

    def test_password_change_requirement_takes_effect_immediately(self):
        token = self.token_for(self.admin)

        first_response = self.send_request(token)
        self.assertEqual(first_response.status_code, 200)

        self.admin.must_change_password = True
        self.admin.save(update_fields=["must_change_password"])

        second_response = self.send_request(token)
        self.assertEqual(second_response.status_code, 403)

    def test_password_change_revokes_existing_token(self):
        token = self.token_for(self.admin)

        # Existing token works before password change.
        before = self.send_request(token)
        self.assertEqual(before.status_code, 200)

        # Change password through the real endpoint.
        password_response = self.client.post(
            "/api/admin/change-password/",
            data=json.dumps({
                "current_password": "SecureTestP@ss123",
                "new_password": "DifferentSecureP@ss456",
                "confirm_password": "DifferentSecureP@ss456",
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_X_GATEWAY_SECRET="test-gateway-secret",
        )

        self.assertEqual(password_response.status_code, 200)

        # Old token must be rejected after password change.
        after = self.send_request(token)
        self.assertEqual(after.status_code, 401)