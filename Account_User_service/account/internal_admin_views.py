import secrets

from django.conf import settings
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .authorization import require_admin_permission
from .models import AdminPermission
from rest_framework.exceptions import AuthenticationFailed

@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def authorize_admin_internal(request):
    # Authenticate the calling service.
    expected_secret = getattr(settings, "INTERNAL_SERVICE_SECRET", "")
    provided_secret = request.headers.get(
        "X-INTERNAL-SERVICE-SECRET", ""
    )

    if not expected_secret:
        return Response(
            {"detail": "Internal authorization not configured"},
            status=503,
        )

    if not provided_secret or not secrets.compare_digest(
        provided_secret, expected_secret
    ):
        return Response(
            {"detail": "Forbidden"},
            status=403,
        )

    # Validate requested permission.
    if not isinstance(request.data, dict):
        return Response(
            {"detail": "Invalid request body"},
            status=400,
        )

    permission_code = request.data.get("permission")

    if permission_code not in AdminPermission.Code.values:
        return Response(
            {"detail": "Invalid admin permission"},
            status=400,
        )

    # Validate JWT and current database permissions.
    try:
        user = require_admin_permission(
            request,
            permission_code,
        )
    except AuthenticationFailed as exc:
        return Response(
        {"detail": str(exc.detail)},
        status=401,
        headers={"WWW-Authenticate": "Bearer"},
    )

    return Response({
        "authorized": True,
        "user_id": str(user.user_id),
        "permission": permission_code,
    })