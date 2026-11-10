
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from account.models import User
from account.views import login
from rest_framework.exceptions import AuthenticationFailed
from account.jwt_utils import get_user_from_token

class InactiveUserLoginTests(TestCase):

    def test_inactive_admin_cannot_login(self):
        # Create an inactive admin account
        user = User.objects.create(
            username="inactive_test_admin",
            email="inactive_test@example.com",
            role=User.Role.ADMIN,
            is_active=False,
        )

        user.set_password("TestPassword123!")
        user.save(update_fields=["password"])

        # Attempt login with correct credentials
        factory = APIRequestFactory()
        request = factory.post(
            "/api/login/",
            {
                "username": "inactive_test_admin",
                "password": "TestPassword123!",
            },
            format="json",
        )

        response = login(request)

        # Inactive accounts must not receive a JWT
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("token", response.data)



    def test_inactive_admin_cannot_use_existing_token(self):
        # Create an active admin
        user = User.objects.create(
            username="jwt_test_admin",
            email="jwt_test_admin@example.com",
            role=User.Role.ADMIN,
            is_active=True,
        )
        user.set_password("TestPassword123!")
        user.save(update_fields=["password"])

        factory = APIRequestFactory()

        # Login while account is active
        login_request = factory.post(
            "/api/login/",
            {
                "username": "jwt_test_admin",
                "password": "TestPassword123!",
            },
            format="json",
        )

        login_response = login(login_request)
        self.assertEqual(login_response.status_code, 200)

        token = login_response.data["token"]

        # Deactivate account AFTER issuing JWT
        user.is_active = False
        user.save(update_fields=["is_active"])

        # Attempt to use the previously issued JWT
        request = factory.get(
            "/api/me/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        with self.assertRaises(AuthenticationFailed):
            get_user_from_token(request)
