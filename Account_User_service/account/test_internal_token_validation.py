from django.test import TestCase, override_settings

from .auth import create_jwt_for_user
from .models import User, Student

@override_settings(
    INTERNAL_SERVICE_SECRET="test-internal-secret",
    GATEWAY_SECRET="test-gateway-secret",
    JWT_SECRET="test-only-jwt-secret",
    JWT_ALGORITHM="HS256",
    JWT_EXP_DELTA_SECONDS=3600,
)
class InternalTokenValidationTests(TestCase):

    def setUp(self):
        self.user = User(
            username="token_validation_admin",
            email="token_validation_admin@example.com",
            role=User.Role.ADMIN,
        )
        self.user.set_password("SecureTestP@ss123")
        self.user.save()

        self.token = create_jwt_for_user(self.user)

        self.url = "/api/internal/token/validate/"

    def send_request(self, token=None, secret="test-internal-secret"):
        headers = {}

        if secret is not None:
            headers["HTTP_X_INTERNAL_SERVICE_SECRET"] = secret

        if token is not None:
            headers["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        return self.client.post(
            self.url,
            data="{}",
            content_type="application/json",
            **headers,
        )

    def test_valid_token_is_accepted(self):
        response = self.send_request(self.token)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(
            response.json()["user_id"],
            str(self.user.user_id),
        )
        self.assertEqual(
            response.json()["role"],
            User.Role.ADMIN,
        )

    def test_missing_token_is_rejected(self):
        response = self.send_request()

        self.assertEqual(response.status_code, 401)

    def test_invalid_token_is_rejected(self):
        response = self.send_request("invalid.jwt.token")

        self.assertEqual(response.status_code, 401)

    def test_revoked_token_is_rejected(self):
        # Token is initially valid.
        response = self.send_request(self.token)
        self.assertEqual(response.status_code, 200)

        # Revoke existing tokens.
        self.user.token_version += 1
        self.user.save(update_fields=["token_version"])

        # The old token must now be rejected.
        response = self.send_request(self.token)

        self.assertEqual(response.status_code, 401)


    def test_inactive_admin_token_is_rejected(self):
        # Verify the token works before deactivation
        response = self.send_request(self.token)
        self.assertEqual(response.status_code, 200)

        # Deactivate the admin account
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        # Try using the same token after deactivation
        response = self.send_request(self.token)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"],
            "Account is deactivated",
        )

    def test_missing_internal_secret_is_rejected(self):
        response = self.send_request(
            self.token,
            secret=None,
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_internal_secret_is_rejected(self):
        response = self.send_request(
            self.token,
            secret="wrong-secret",
        )

        self.assertEqual(response.status_code, 403)

    @override_settings(INTERNAL_SERVICE_SECRET="")
    def test_unconfigured_secret_is_rejected(self):
        response = self.send_request(self.token)

        self.assertEqual(response.status_code, 503)

    def test_current_database_role_is_returned(self):
        # Change the user's role after issuing the token.
        self.user.role = User.Role.MAIN_ADMIN
        self.user.save(update_fields=["role"])

        response = self.send_request(self.token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["role"],
            User.Role.MAIN_ADMIN,
        )

    def test_student_id_is_returned_from_database(self):
        student_user = User(
            username="student_validation",
            email="student_validation@example.com",
            role=User.Role.STUDENT,
        )
        student_user.set_password("SecureTestP@ss123")
        student_user.save()

        student_profile = Student.objects.create(
            user_id=student_user
        )

        token = create_jwt_for_user(
            student_user,
            student_profile,
        )

        response = self.send_request(token)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["student_id"],
            str(student_profile.student_id),
        )
        self.assertEqual(
            response.json()["role"],
            User.Role.STUDENT,
        )


    def test_admin_has_no_student_id(self):
        response = self.send_request(self.token)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["student_id"])


    def test_student_without_profile_is_rejected(self):
        student_user = User(
            username="student_no_profile",
            email="student_no_profile@example.com",
            role=User.Role.STUDENT,
        )
        student_user.set_password("SecureTestP@ss123")
        student_user.save()

        student_profile = Student.objects.create(
            user_id=student_user
        )

        token = create_jwt_for_user(
            student_user,
            student_profile,
        )

        # Simulate deletion of the student profile
        # after the JWT was issued.
        student_profile.delete()

        response = self.send_request(token)

        self.assertEqual(response.status_code, 401)