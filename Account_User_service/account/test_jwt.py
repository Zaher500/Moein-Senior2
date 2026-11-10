
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase, override_settings

from .auth import create_jwt_for_user, decode_jwt
from .models import User


@override_settings(
    JWT_SECRET="test-only-jwt-secret",
    JWT_ALGORITHM="HS256",
    JWT_EXP_DELTA_SECONDS=3600,
)
class JWTTests(SimpleTestCase):

    def make_user(self, role):
        return SimpleNamespace(
            user_id=uuid4(),
            username="test_user",
            role=role,
            token_version=1,
        )

    def test_student_jwt(self):
        user = self.make_user(User.Role.STUDENT)
        student = SimpleNamespace(student_id=uuid4())

        token = create_jwt_for_user(user, student=student)
        payload = decode_jwt(token)

        self.assertEqual(payload["token_version"], 1)
        self.assertEqual(payload["sub"], str(user.user_id))
        self.assertEqual(payload["username"], user.username)
        self.assertEqual(payload["role"], User.Role.STUDENT)
        self.assertEqual(
            payload["student_id"],
            str(student.student_id)
        )
        self.assertIn("iat", payload)
        self.assertIn("exp", payload)

    def test_admin_jwt(self):
        user = self.make_user(User.Role.ADMIN)

        token = create_jwt_for_user(user)
        payload = decode_jwt(token)

        self.assertEqual(payload["token_version"], 1)
        self.assertEqual(payload["sub"], str(user.user_id))
        self.assertEqual(payload["role"], User.Role.ADMIN)
        self.assertNotIn("student_id", payload)

    def test_main_admin_jwt(self):
        user = self.make_user(User.Role.MAIN_ADMIN)

        token = create_jwt_for_user(user)
        payload = decode_jwt(token)

        self.assertEqual(payload["token_version"], 1)
        self.assertEqual(payload["sub"], str(user.user_id))
        self.assertEqual(payload["role"], User.Role.MAIN_ADMIN)
        self.assertNotIn("student_id", payload)

    def test_student_requires_profile(self):
        user = self.make_user(User.Role.STUDENT)

        with self.assertRaisesMessage(
            ValueError,
            "Student profile is required",
        ):
            create_jwt_for_user(user)
