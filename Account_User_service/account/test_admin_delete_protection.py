
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .models import User
from .views import delete_account


class AdminDeleteProtectionTests(SimpleTestCase):

    def test_admins_cannot_delete_their_own_accounts(self):
        for role in (User.Role.ADMIN, User.Role.MAIN_ADMIN):
            with self.subTest(role=role):

                user = Mock()
                user.role = role

                request = APIRequestFactory().delete(
                    "/api/delete/",
                    {"password": "test-password"},
                    format="json",
                )

                with (
                    patch(
                        "account.views.get_user_from_token",
                        return_value=user,
                    ),
                    patch("account.views.requests.delete") as course_delete,
                ):
                    response = delete_account(request)

                self.assertEqual(response.status_code, 403)
                self.assertEqual(
                    response.data["error"],
                    "This endpoint is only available for students",
                )

                user.delete.assert_not_called()
                course_delete.assert_not_called()
