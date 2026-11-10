
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from .jwt_utils import get_user_from_token
from .models import User


def require_admin_permission(request, permission_code):
    """
    Authenticate a user and require an admin permission.
    Returns the User if authorized.
    """

    user = get_user_from_token(request)

    if user is None:
        raise AuthenticationFailed("Authentication required")

    # Students cannot access administrative operations.
    if user.role not in (User.Role.ADMIN, User.Role.MAIN_ADMIN):
        raise PermissionDenied("Admin access required")

    # Temporary-password admins must change their password first.
    if user.must_change_password:
        raise PermissionDenied("Password change required")

    # Main Admin has all administrative permissions.
    if user.role == User.Role.MAIN_ADMIN:
        return user

    # Regular Admin must have the required permission.
    if not user.admin_permissions.filter(code=permission_code).exists():
        raise PermissionDenied("Insufficient permissions")

    return user

def require_main_admin(request):
    """
    Authenticate the request and allow MAIN_ADMIN only.
    """

    user = get_user_from_token(request)

    if user is None:
        raise AuthenticationFailed("Authentication required")

    if user.role != User.Role.MAIN_ADMIN:
        raise PermissionDenied("Main Admin access required")

    if user.must_change_password:
        raise PermissionDenied("Password change required")

    return user