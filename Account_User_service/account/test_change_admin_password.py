
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import User
from .views import change_admin_password


class ChangeAdminPasswordTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.old_password = "TemporaryP@ssw0rd42"
        self.new_password = "NewSecureP@ssw0rd85"

        self.user = User(
            username="admin_test",
            email="admin_test@example.com",
            role=User.Role.ADMIN,
            must_change_password=True,
        )
        self.user.set_password(self.old_password)
        self.user.save()

    def submit(self, **overrides):
        data = {
            "current_password": self.old_password,
            "new_password": self.new_password,
            "confirm_password": self.new_password,
        }
        data.update(overrides)

        request = self.factory.post(
            "/api/admin/change-password/",
            data,
            format="json",
        )

        with patch(
            "account.views.get_user_from_token",
            return_value=self.user,
        ):
            return change_admin_password(request)

    def test_successful_password_change(self):
        response = self.submit()

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            self.user.check_password(self.new_password)
        )
        self.assertFalse(
            self.user.check_password(self.old_password)
        )
        self.assertFalse(self.user.must_change_password)

    def test_incorrect_current_password(self):
        response = self.submit(
            current_password="WrongPassword123!"
        )

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            self.user.check_password(self.old_password)
        )
        self.assertTrue(self.user.must_change_password)

    def test_passwords_do_not_match(self):
        response = self.submit(
            confirm_password="DifferentPassword123!"
        )

        self.assertEqual(response.status_code, 400)

    def test_cannot_reuse_same_password(self):
        response = self.submit(
            new_password=self.old_password,
            confirm_password=self.old_password,
        )

        self.assertEqual(response.status_code, 400)

    def test_weak_password_rejected(self):
        response = self.submit(
            new_password="12345678",
            confirm_password="12345678",
        )

        self.assertEqual(response.status_code, 400)

    def test_student_cannot_use_admin_endpoint(self):
        self.user.role = User.Role.STUDENT
        self.user.save(update_fields=["role"])

        response = self.submit()

        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)
