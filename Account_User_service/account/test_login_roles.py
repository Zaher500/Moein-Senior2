
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory

from .auth import decode_jwt
from .models import User, Student
from .views import login as login_view


@override_settings(
    JWT_SECRET="test-only-jwt-secret",
    JWT_ALGORITHM="HS256",
    JWT_EXP_DELTA_SECONDS=3600,
)
class LoginRoleTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.password = "TestPassword123!"

    def create_user(self, username, role, must_change=False):
        user = User(
            username=username,
            email=f"{username}@example.com",
            role=role,
            must_change_password=must_change,
        )
        user.set_password(self.password)
        user.save()
        return user

    def login_user(self, username, password=None):
        request = self.factory.post(
            "/api/login/",
            {
                "username": username,
                "password": password or self.password,
            },
            format="json",
        )
        return login_view(request)

    def test_student_login(self):
        user = self.create_user("student1", User.Role.STUDENT)
        student = Student.objects.create(user_id=user)

        response = self.login_user("student1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "STUDENT")
        self.assertEqual(
            response.data["student"]["student_id"],
            str(student.student_id),
        )

        payload = decode_jwt(response.data["token"])
        self.assertEqual(payload["role"], "STUDENT")
        self.assertEqual(
            payload["student_id"],
            str(student.student_id),
        )

    def test_admin_login(self):
        self.create_user("admin1", User.Role.ADMIN)

        response = self.login_user("admin1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "ADMIN")
        self.assertIsNone(response.data["student"])

        payload = decode_jwt(response.data["token"])
        self.assertEqual(payload["role"], "ADMIN")
        self.assertNotIn("student_id", payload)

    def test_main_admin_login(self):
        self.create_user("mainadmin", User.Role.MAIN_ADMIN)

        response = self.login_user("mainadmin")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["user"]["role"],
            "MAIN_ADMIN",
        )
        self.assertIsNone(response.data["student"])

        payload = decode_jwt(response.data["token"])
        self.assertEqual(payload["role"], "MAIN_ADMIN")
        self.assertNotIn("student_id", payload)

    def test_admin_temporary_password(self):
        self.create_user(
            "tempadmin",
            User.Role.ADMIN,
            must_change=True,
        )

        response = self.login_user("tempadmin")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.data["user"]["must_change_password"]
        )

    def test_invalid_password(self):
        self.create_user("student1", User.Role.STUDENT)

        response = self.login_user(
            "student1",
            password="WrongPassword123!",
        )

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("token", response.data)


#The student logs in and receives a `student_id` and a valid JWT.
#A regular admin logs in without a student profile.
#The Main Admin logs in without a Student Profile.
#An admin who uses a temporary password will have `must_change_password=True`.
#An incorrect password results in a 401.