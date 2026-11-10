from unittest.mock import patch    #admin
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from django.conf import settings
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from gateway.middleware.jwt_auth import JWTAuthMiddleware


@override_settings(
    JWT_SECRET="test-only-gateway-secret",
    JWT_ALGORITHM="HS256",
    INTERNAL_SERVICE_SECRET="test-internal-secret",
    SERVICES={"account": "http://account.test"},
)
class JWTAuthRoleTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()

        def get_response(request):
            return JsonResponse({
                "user_id": getattr(request, "user_id", None),
                "student_id": getattr(request, "student_id", None),
                "role": getattr(request, "role", None),
            })

        self.middleware = JWTAuthMiddleware(get_response)

    def send_token(self, role, student_id=None):
        user_id = str(uuid4())
        now = datetime.now(timezone.utc)

        payload = {
            "sub": user_id,
            "username": "test_user",
            "iat": now,
            "exp": now + timedelta(hours=1),
        }

        if role is not None:
            payload["role"] = role

        if student_id is not None:
            payload["student_id"] = student_id

        token = jwt.encode(
            payload,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

        request = self.factory.get(
            "/api/me/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        # Simulate the Account Service returning current database state.
        current_role = role if role is not None else "STUDENT"

        with patch("gateway.middleware.jwt_auth.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "valid": True,
                "user_id": user_id,
                "role": current_role,
                "student_id": student_id if current_role == "STUDENT" else None,
                "must_change_password": False,
            }

            response = self.middleware(request)

            mock_post.assert_called_once()
        return user_id, response, json.loads(response.content)

    def test_student_has_student_id(self):
        student_id = str(uuid4())

        user_id, response, data = self.send_token(
            role="STUDENT",
            student_id=student_id,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["user_id"], user_id)
        self.assertEqual(data["student_id"], student_id)
        self.assertEqual(data["role"], "STUDENT")

    def test_admin_has_no_student_id(self):
        user_id, response, data = self.send_token(
            role="ADMIN",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["user_id"], user_id)
        self.assertIsNone(data["student_id"])
        self.assertEqual(data["role"], "ADMIN")

    def test_main_admin_has_no_student_id(self):
        user_id, response, data = self.send_token(
            role="MAIN_ADMIN",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["user_id"], user_id)
        self.assertIsNone(data["student_id"])
        self.assertEqual(data["role"], "MAIN_ADMIN")

    def test_legacy_student_token(self):
        student_id = str(uuid4())

        user_id, response, data = self.send_token(
            role=None,
            student_id=student_id,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["user_id"], user_id)
        self.assertEqual(data["student_id"], student_id)
        self.assertEqual(data["role"], "STUDENT")
