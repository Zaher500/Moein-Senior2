import secrets

from django.conf import settings
from rest_framework.permissions import BasePermission


class HasInternalServiceKey(BasePermission):
    message = "Invalid or missing internal service credentials."

    def has_permission(self, request, view):
        expected_key = settings.RAG_INTERNAL_API_KEY

        if not expected_key:
            return False

        provided_key = request.headers.get("X-Internal-Service-Key")

        if not provided_key:
            return False

        return secrets.compare_digest(
            str(provided_key),
            str(expected_key),
        )
