from unittest.mock import Mock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from gateway.middleware.request_router import RequestRouterMiddleware


@override_settings(
    SERVICES={
        "account": "http://account.test",
        "course": "http://course.test",
        "summarizer": "http://summarizer.test",
        "chatbot": "http://chatbot.test",
        "stt": "http://stt.test",
        "quiz": "http://quiz.test",
        "notification": "http://notification.test",
        "study_plan": "http://study-plan.test",
    },
    GATEWAY_SECRET="test-gateway-secret",
)
class RequestRouterIdentityTests(SimpleTestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.router = RequestRouterMiddleware(
            lambda request: HttpResponse(status=404)
        )

    def make_request(self, student_id):
        request = self.factory.get(
            "/api/me/",
            HTTP_X_STUDENT_ID="forged-student-id",
            HTTP_X_USER_ID="forged-user-id",
            HTTP_X_USERNAME="forged-username",
            HTTP_X_GATEWAY_SECRET="forged-secret",
        )

        # Identity already validated by JWTAuthMiddleware.
        request.user_id = "real-user-id"
        request.student_id = student_id
        request.username = "real-username"

        return request

    @patch("gateway.middleware.request_router.requests.request")
    def test_student_identity_is_forwarded(self, mock_request):
        mock_request.return_value = Mock(
            status_code=200,
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )

        request = self.make_request(student_id="real-student-id")
        response = self.router(request)

        self.assertEqual(response.status_code, 200)

        headers = mock_request.call_args.kwargs["headers"]

        self.assertEqual(headers["X-Student-ID"], "real-student-id")
        self.assertEqual(headers["X-User-ID"], "real-user-id")
        self.assertEqual(headers["X-Username"], "real-username")
        self.assertEqual(
            headers["X-GATEWAY-SECRET"],
            "test-gateway-secret",
        )

    @patch("gateway.middleware.request_router.requests.request")
    def test_admin_has_no_student_id_even_if_spoofed(self, mock_request):
        mock_request.return_value = Mock(
            status_code=200,
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )

        request = self.make_request(student_id=None)
        response = self.router(request)

        self.assertEqual(response.status_code, 200)

        headers = mock_request.call_args.kwargs["headers"]

        self.assertNotIn("X-Student-ID", headers)
        self.assertEqual(headers["X-User-ID"], "real-user-id")
        self.assertEqual(headers["X-Username"], "real-username")
        self.assertEqual(
            headers["X-GATEWAY-SECRET"],
            "test-gateway-secret",
        )

    @patch("gateway.middleware.request_router.requests.request")
    def test_change_admin_password_is_routed_to_account(self, mock_request):
        mock_request.return_value = Mock(
            status_code=200,
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )

        request = self.factory.post(
            "/api/admin/change-password/",
            data="{}",
            content_type="application/json",
        )

        response = self.router(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            mock_request.call_args.kwargs["url"],
            "http://account.test/api/admin/change-password/",
        )

    @patch("gateway.middleware.request_router.requests.request")
    def test_create_admin_is_routed_to_account(self, mock_request):
        mock_request.return_value = Mock(
            status_code=200,
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )

        request = self.factory.post(
            "/api/admin/create/",
            data="{}",
            content_type="application/json",
        )

        # Identity already validated by JWTAuthMiddleware.
        request.user_id = "main-admin-user-id"
        request.student_id = None
        request.username = "main_admin"

        response = self.router(request)

        self.assertEqual(response.status_code, 200)

        forwarded = mock_request.call_args.kwargs

        self.assertEqual(
            forwarded["url"],
            "http://account.test/api/admin/create/",
        )

        self.assertEqual(
            forwarded["headers"]["X-GATEWAY-SECRET"],
            "test-gateway-secret",
        )

        self.assertEqual(
            forwarded["headers"]["X-User-ID"],
            "main-admin-user-id",
        )

        self.assertNotIn(
            "X-Student-ID",
            forwarded["headers"],
        )


    @patch("gateway.middleware.request_router.requests.request")
    def test_list_admins_is_routed_to_account(self, mock_request):
        mock_request.return_value = Mock(
            status_code=200,
            content=b'{"admins": []}',
            headers={"Content-Type": "application/json"},
        )

        request = self.factory.get("/api/admin/list/")

        # Identity already validated by JWTAuthMiddleware.
        request.user_id = "main-admin-user-id"
        request.student_id = None
        request.username = "main_admin"

        response = self.router(request)

        self.assertEqual(response.status_code, 200)

        forwarded = mock_request.call_args.kwargs

        self.assertEqual(
            forwarded["url"],
            "http://account.test/api/admin/list/",
        )

        self.assertEqual(
            forwarded["headers"]["X-GATEWAY-SECRET"],
            "test-gateway-secret",
        )

        self.assertEqual(
            forwarded["headers"]["X-User-ID"],
            "main-admin-user-id",
        )

        self.assertNotIn(
            "X-Student-ID",
            forwarded["headers"],
        )



    @patch("gateway.middleware.request_router.requests.request")
    def test_update_admin_permissions_is_routed_to_account(self, mock_request):
        mock_request.return_value = Mock(
            status_code=200,
            content=b'{"message": "Admin permissions updated successfully"}',
            headers={"Content-Type": "application/json"},
        )

        admin_id = "26a7ff84-5fca-43d1-90a8-dbedcdd26f9d"

        request = self.factory.patch(
            f"/api/admin/{admin_id}/permissions/",
            data='{"permissions": ["VIEW_COURSES", "EDIT_COURSES"]}',
            content_type="application/json",
        )

        # Identity already validated by JWTAuthMiddleware.
        request.user_id = "main-admin-user-id"
        request.student_id = None
        request.username = "main_admin"

        response = self.router(request)

        self.assertEqual(response.status_code, 200)

        forwarded = mock_request.call_args.kwargs

        self.assertEqual(
            forwarded["method"],
            "PATCH",
        )

        self.assertEqual(
            forwarded["url"],
            f"http://account.test/api/admin/{admin_id}/permissions/",
        )

        self.assertEqual(
            forwarded["headers"]["X-GATEWAY-SECRET"],
            "test-gateway-secret",
        )

        self.assertEqual(
            forwarded["headers"]["X-User-ID"],
            "main-admin-user-id",
        )

        self.assertNotIn(
            "X-Student-ID",
            forwarded["headers"],
        )

        self.assertEqual(
            forwarded["json"]["permissions"],
            ["VIEW_COURSES", "EDIT_COURSES"],
        )


    @patch("gateway.middleware.request_router.requests.request")
    def test_edit_admin_is_routed_to_account(self, mock_request):
        mock_request.return_value = Mock(
            status_code=200,
            content=b'{"message": "Admin updated successfully"}',
            headers={"Content-Type": "application/json"},
        )

        admin_id = "26a7ff84-5fca-43d1-90a8-dbedcdd26f9d"

        request = self.factory.patch(
            f"/api/admin/{admin_id}/edit/",
            data='{"username": "updated_admin", "email": "updated_admin@example.com"}',
            content_type="application/json",
        )

        request.user_id = "main-admin-user-id"
        request.student_id = None
        request.username = "main_admin"

        response = self.router(request)

        self.assertEqual(response.status_code, 200)

        forwarded = mock_request.call_args.kwargs

        self.assertEqual(
            forwarded["method"],
            "PATCH",
        )

        self.assertEqual(
            forwarded["url"],
            f"http://account.test/api/admin/{admin_id}/edit/",
        )

        self.assertEqual(
            forwarded["headers"]["X-GATEWAY-SECRET"],
            "test-gateway-secret",
        )

        self.assertEqual(
            forwarded["headers"]["X-User-ID"],
            "main-admin-user-id",
        )

        self.assertNotIn(
            "X-Student-ID",
            forwarded["headers"],
        )

        self.assertEqual(
            forwarded["json"],
            {
                "username": "updated_admin",
                "email": "updated_admin@example.com",
            },
        )


    @patch("gateway.middleware.request_router.requests.request")
    def test_delete_admin_is_routed_to_account(self, mock_request):
        mock_request.return_value = Mock(
            status_code=200,
            content=b'{"message": "Admin deactivated successfully"}',
            headers={"Content-Type": "application/json"},
        )

        admin_id = "26a7ff84-5fca-43d1-90a8-dbedcdd26f9d"

        request = self.factory.patch(
        f"/api/admin/{admin_id}/deactivate/"
        )

        # Identity already verified by JWTAuthMiddleware.
        request.user_id = "main-admin-user-id"
        request.student_id = None
        request.username = "main_admin"

        response = self.router(request)

        self.assertEqual(response.status_code, 200)

        forwarded = mock_request.call_args.kwargs

        self.assertEqual(
            forwarded["method"],
            "PATCH",
        )

        self.assertEqual(
            forwarded["url"],
            f"http://account.test/api/admin/{admin_id}/deactivate/",
        )

        self.assertEqual(
            forwarded["headers"]["X-GATEWAY-SECRET"],
            "test-gateway-secret",
        )

        self.assertEqual(
            forwarded["headers"]["X-User-ID"],
            "main-admin-user-id",
        )

        self.assertNotIn(
            "X-Student-ID",
            forwarded["headers"],
        )
