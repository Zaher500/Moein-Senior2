import secrets

from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .authorization import require_main_admin
from .models import User, AdminPermission
from django.shortcuts import get_object_or_404  #We want to allow the MAIN_ADMIN to modify the permissions of any regular ADMIN, while preventing any changes to the permissions of the MAIN_ADMIN themselves.

class CreateAdminSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    permissions = serializers.ListField(
        child=serializers.ChoiceField(
            choices=AdminPermission.Code.choices
        ),
        allow_empty=True,
    )

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "Username already exists"
            )
        return value

    def validate_email(self, value):
        value = value.lower()

        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "Email already exists"
            )
        return value

    def validate_permissions(self, values):
        if len(values) != len(set(values)):
            raise serializers.ValidationError(
                "Duplicate permissions are not allowed"
            )
        return values


@api_view(["POST"])
@permission_classes([AllowAny])
def create_admin(request):
    # Only MAIN_ADMIN can create another admin.
    require_main_admin(request)

    serializer = CreateAdminSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    data = serializer.validated_data
    permission_codes = data["permissions"]

    permissions = list(
        AdminPermission.objects.filter(
            code__in=permission_codes
        )
    )

    # Ensure every requested permission exists in the DB.
    if len(permissions) != len(permission_codes):
        return Response(
            {"error": "One or more permissions are unavailable"},
            status=400,
        )

    # Generate a cryptographically secure temporary password.
    temporary_password = secrets.token_urlsafe(24)

    try:
        with transaction.atomic():
            admin = User(
                username=data["username"],
                email=data["email"],
                role=User.Role.ADMIN,
                must_change_password=True,
            )

            admin.set_password(temporary_password)
            admin.save()

            admin.admin_permissions.set(permissions)

    except IntegrityError:
        return Response(
            {"error": "Username or email already exists"},
            status=400,
        )

    return Response(
        {
            "message": "Admin created successfully",
            "user_id": str(admin.user_id),
            "username": admin.username,
            "email": admin.email,
            "role": admin.role,
            "permissions": permission_codes,
            "must_change_password": True,
            "temporary_password": temporary_password,
        },
        status=201,
        headers={"Cache-Control": "no-store"},
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def list_admins(request):
    # Only MAIN_ADMIN can view and manage admins.
    require_main_admin(request)

    admins = (
        User.objects
        .filter(role=User.Role.ADMIN)
        .prefetch_related("admin_permissions")
        .order_by("created_at", "user_id")
    )

    admin_data = []

    for admin in admins:
        admin_data.append({
            "user_id": str(admin.user_id),
            "username": admin.username,
            "email": admin.email,
            "phone": admin.phone,
            "role": admin.role,
            "is_active": admin.is_active,
            "must_change_password": admin.must_change_password,
            "permissions": sorted(
                permission.code
                for permission in admin.admin_permissions.all()
            ),
            "created_at": admin.created_at,
        })

    return Response(
        {"admins": admin_data},
        status=200,
        headers={"Cache-Control": "no-store"},
    )


class UpdateAdminPermissionsSerializer(serializers.Serializer):
    permissions = serializers.ListField(
        child=serializers.ChoiceField(
            choices=AdminPermission.Code.choices
        ),
        allow_empty=True,
    )

    def validate_permissions(self, values):
        if len(values) != len(set(values)):
            raise serializers.ValidationError(
                "Duplicate permissions are not allowed"
            )
        return values


@api_view(["PATCH"])
@permission_classes([AllowAny])
def update_admin_permissions(request, admin_id):
    # Only MAIN_ADMIN can manage admin permissions.
    require_main_admin(request)

    serializer = UpdateAdminPermissionsSerializer(
        data=request.data
    )
    serializer.is_valid(raise_exception=True)

    permission_codes = serializer.validated_data["permissions"]

    # Prevent modifying MAIN_ADMIN or STUDENT accounts.
    admin = get_object_or_404(
        User,
        user_id=admin_id,
        role=User.Role.ADMIN,
    )

    permissions = list(
        AdminPermission.objects.filter(
            code__in=permission_codes
        )
    )

    if len(permissions) != len(permission_codes):
        return Response(
            {"error": "One or more permissions are unavailable"},
            status=400,
        )

    with transaction.atomic():
        # Replace all existing permissions.
        admin.admin_permissions.set(permissions)

    return Response(
        {
            "message": "Admin permissions updated successfully",
            "user_id": str(admin.user_id),
            "username": admin.username,
            "role": admin.role,
            "permissions": sorted(permission_codes),
        },
        status=200,
        headers={"Cache-Control": "no-store"},
    )



class EditAdminSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=150,
        required=False,
    )
    email = serializers.EmailField(
        required=False,
    )

    def validate(self, attrs):
        admin = self.context["admin"]

        # Only username and email can be modified.
        allowed_fields = {"username", "email"}
        unexpected_fields = set(self.initial_data) - allowed_fields

        if unexpected_fields:
            raise serializers.ValidationError(
                "Unsupported fields"
            )

        if not attrs:
            raise serializers.ValidationError(
                "At least one field is required"
            )

        if "username" in attrs:
            if User.objects.exclude(
                user_id=admin.user_id
            ).filter(
                username__iexact=attrs["username"]
            ).exists():
                raise serializers.ValidationError({
                    "username": "Username already exists"
                })

        if "email" in attrs:
            attrs["email"] = attrs["email"].lower()

            if User.objects.exclude(
                user_id=admin.user_id
            ).filter(
                email__iexact=attrs["email"]
            ).exists():
                raise serializers.ValidationError({
                    "email": "Email already exists"
                })

        return attrs


@api_view(["PATCH"])
@permission_classes([AllowAny])
def edit_admin(request, admin_id):
    # Only MAIN_ADMIN can edit admin accounts.
    require_main_admin(request)

    # Never allow editing MAIN_ADMIN or STUDENT accounts.
    admin = get_object_or_404(
        User,
        user_id=admin_id,
        role=User.Role.ADMIN,
    )

    serializer = EditAdminSerializer(
        data=request.data,
        context={"admin": admin},
    )
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data

    # Username is included in JWT, so revoke existing tokens
    # if the username changes.
    username_changed = (
        "username" in data
        and data["username"] != admin.username
    )

    update_fields = list(data.keys())

    for field, value in data.items():
        setattr(admin, field, value)

    if username_changed:
        admin.token_version += 1
        update_fields.append("token_version")

    update_fields.append("updated_at")

    try:
        with transaction.atomic():
            admin.save(update_fields=update_fields)
    except IntegrityError:
        return Response(
            {"error": "Username or email already exists"},
            status=400,
        )

    return Response(
        {
            "message": "Admin updated successfully",
            "user_id": str(admin.user_id),
            "username": admin.username,
            "email": admin.email,
            "role": admin.role,
        },
        status=200,
        headers={"Cache-Control": "no-store"},
    )


@api_view(["PATCH"])
@permission_classes([AllowAny])
def deactivate_admin(request, admin_id):
    # Only MAIN_ADMIN can deactivate admins.
    require_main_admin(request)

    # Only regular ADMIN accounts can be deactivated.
    admin = get_object_or_404(
        User,
        user_id=admin_id,
        role=User.Role.ADMIN,
    )

    # Do not update an already deactivated account.
    if admin.is_active:
        admin.is_active = False
        admin.save(update_fields=["is_active", "updated_at"])

    return Response(
        {
            "message": "Admin deactivated successfully",
            "user_id": str(admin.user_id),
        },
        status=200,
        headers={"Cache-Control": "no-store"},
    )
