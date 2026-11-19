import jwt # pyright: ignore[reportMissingImports]
from datetime import datetime, timedelta, timezone
from django.conf import settings # pyright: ignore[reportMissingImports]
from .models import User # pyright: ignore[reportMissingImports]


def create_jwt_for_user(user, student=None):
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user.user_id),
        "username": user.username,
        "role": user.role,
        "token_version": user.token_version,        # admin
        "iat": now,
        "exp": now + timedelta(
            seconds=settings.JWT_EXP_DELTA_SECONDS
        ),
    }

    if user.role == User.Role.STUDENT:
        if student is None:
            raise ValueError(
                "Student profile is required for student users"
            )

        payload["student_id"] = str(student.student_id)

    token = jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )

    return token


def decode_jwt(token):
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
