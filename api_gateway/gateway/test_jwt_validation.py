from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

import jwt
import requests

from django.conf import settings
from django.http import JsonResponse
from django.test import (
    RequestFactory,
    SimpleTestCase,
    override_settings,
)

from gateway.middleware.jwt_auth import JWTAuthMiddleware


@override_settings(
    JWT_SECRET="test-only-jwt-secret",
    JWT_ALGORITHM="HS256",
    INTERNAL_SERVICE_SECRET="test-internal-secret",
    SERVICES={"account": "http://account.test"},
)
class GatewayTokenValidationTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()

        self.middleware = JWTAuthMiddleware(
            lambda request: JsonResponse({"forwarded": True})
        )

        now = datetime.now(timezone.utc)

        self.token = jwt.encode(
            {
                "sub": str(uuid4()),
                "username": "test_admin",
                "role": "ADMIN",
                "token_version": 1,
                "iat": now,
                "exp": now + timedelta(hours=1),
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

    def make_request(self):
        return self.factory.get(
            "/api/me/",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    @patch("gateway.middleware.jwt_auth.requests.post")
    def test_revoked_token_is_rejected(self, mock_post):
        mock_post.return_value.status_code = 401

        response = self.middleware(self.make_request())

        self.assertEqual(response.status_code, 401)
        mock_post.assert_called_once()

    @patch("gateway.middleware.jwt_auth.requests.post")
    def test_account_service_unavailable_fails_closed(self, mock_post):
        mock_post.side_effect = requests.Timeout()

        response = self.middleware(self.make_request())

        self.assertEqual(response.status_code, 503)
        mock_post.assert_called_once()

    @patch("gateway.middleware.jwt_auth.requests.post")
    def test_valid_token_uses_current_database_role(self, mock_post):
        payload = jwt.decode(
            self.token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Simulate the current student ID from Account Service.
        current_student_id = str(uuid4())

        # Account Service returns the current database state.
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "valid": True,
            "user_id": payload["sub"],
            "role": "STUDENT",
            "student_id": current_student_id,
            "must_change_password": False,
        }

        downstream = Mock(
            return_value=JsonResponse({"forwarded": True})
        )
        self.middleware.get_response = downstream

        response = self.middleware(self.make_request())

        self.assertEqual(response.status_code, 200)

        downstream.assert_called_once()
        forwarded_request = downstream.call_args.args[0]

        self.assertEqual(
            forwarded_request.user_id,
            payload["sub"],
        )

        # JWT says ADMIN, but database says STUDENT.
        self.assertEqual(forwarded_request.role, "STUDENT")
        self.assertFalse(forwarded_request.must_change_password)
        self.assertEqual(
            forwarded_request.student_id,
            current_student_id,
        )

        mock_post.assert_called_once()

    @patch("gateway.middleware.jwt_auth.requests.post")
    def test_mismatched_user_id_is_rejected(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "valid": True,
            "user_id": str(uuid4()),
            "role": "ADMIN",
            "must_change_password": False,
        }

        downstream = Mock(
            return_value=JsonResponse({"forwarded": True})
        )
        self.middleware.get_response = downstream

        response = self.middleware(self.make_request())

        self.assertEqual(response.status_code, 503)
        downstream.assert_not_called()
        mock_post.assert_called_once()

    @patch("gateway.middleware.jwt_auth.requests.post")
    def test_student_id_comes_from_account_service(self, mock_post):
        payload = jwt.decode(
            self.token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Simulate a JWT containing an outdated student ID.
        payload["role"] = "STUDENT"
        payload["student_id"] = "old-student-id"

        self.token = jwt.encode(
            payload,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

        # Current student ID returned by Account Service.
        current_student_id = str(uuid4())

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "valid": True,
            "user_id": payload["sub"],
            "role": "STUDENT",
            "student_id": current_student_id,
            "must_change_password": False,
        }

        downstream = Mock(
            return_value=JsonResponse({"forwarded": True})
        )
        self.middleware.get_response = downstream

        response = self.middleware(self.make_request())

        self.assertEqual(response.status_code, 200)
        downstream.assert_called_once()

        forwarded_request = downstream.call_args.args[0]

        self.assertEqual(
            forwarded_request.student_id,
            current_student_id,
        )

    @patch("gateway.middleware.jwt_auth.requests.post")
    def test_student_without_student_id_is_rejected(self, mock_post):
        payload = jwt.decode(
            self.token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "valid": True,
            "user_id": payload["sub"],
            "role": "STUDENT",
            "student_id": None,
            "must_change_password": False,
        }

        downstream = Mock(
            return_value=JsonResponse({"forwarded": True})
        )
        self.middleware.get_response = downstream

        response = self.middleware(self.make_request())

        self.assertEqual(response.status_code, 503)
        downstream.assert_not_called()
        mock_post.assert_called_once()

    @patch("gateway.middleware.jwt_auth.requests.post")
    def test_admin_with_student_id_is_rejected(self, mock_post):
        payload = jwt.decode(
            self.token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "valid": True,
            "user_id": payload["sub"],
            "role": "ADMIN",
            "student_id": str(uuid4()),
            "must_change_password": False,
        }

        downstream = Mock(
            return_value=JsonResponse({"forwarded": True})
        )
        self.middleware.get_response = downstream

        response = self.middleware(self.make_request())

        self.assertEqual(response.status_code, 503)
        downstream.assert_not_called()
        mock_post.assert_called_once()

    def test_login_without_token_is_public(self):
        request = self.factory.post("/api/login/")

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)


    def test_login_subpath_without_token_is_rejected(self):
        request = self.factory.get(
            "/api/login/anything/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 401)

    def test_valid_check_user_path_is_public(self):
        user_id = str(uuid4())

        request = self.factory.get(
            f"/api/check-user/{user_id}/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_valid_check_student_path_is_public(self):
        student_id = str(uuid4())

        request = self.factory.get(
            f"/api/check-student/{student_id}/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_invalid_check_user_path_is_rejected(self):
        request = self.factory.get(
            "/api/check-user/not-a-uuid/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 401)

    def test_check_user_extra_path_is_rejected(self):
        user_id = str(uuid4())

        request = self.factory.get(
            f"/api/check-user/{user_id}/extra/"
        )

        response = self.middleware(request)

        self.assertEqual(response.status_code, 401)