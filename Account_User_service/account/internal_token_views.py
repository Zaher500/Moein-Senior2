import secrets
from .models import User, Student   # admin
from django.conf import settings
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .jwt_utils import get_user_from_token


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def validate_token_internal(request):
    expected_secret = getattr(
        settings, "INTERNAL_SERVICE_SECRET", ""
    )
    provided_secret = request.headers.get(
        "X-INTERNAL-SERVICE-SECRET", ""
    )

    if not expected_secret:
        return Response(
            {"detail": "Internal validation not configured"},
            status=503,
        )

    if not provided_secret or not secrets.compare_digest(
        provided_secret, expected_secret
    ):
        return Response(
            {"detail": "Forbidden"},
            status=403,
        )

    try:
        user = get_user_from_token(request)
    except AuthenticationFailed as exc:
        return Response(
            {"detail": str(exc.detail)},
            status=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user is None:
        return Response(
            {"detail": "Authentication required"},
            status=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    student_id = None

    if user.role == User.Role.STUDENT:
        student_id = (
            Student.objects.filter(user_id=user)
            .values_list("student_id", flat=True)
            .first()
        )

        if student_id is None:
            return Response(
                {"detail": "Student profile not found"},
                status=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

    return Response({
        "valid": True,
        "user_id": str(user.user_id),
        "role": user.role,
        "student_id": str(student_id) if student_id is not None else None,
        "must_change_password": user.must_change_password,
    })