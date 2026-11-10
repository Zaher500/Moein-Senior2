from rest_framework import exceptions
import jwt
from .auth import decode_jwt
from .models import User

def get_user_from_token(request):
    """
    Manual JWT token validation
    Returns user object if token is valid, None if no token, raises exception if invalid
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    
    if not auth_header:
        return None  # No token provided
    
    # Check if header has Bearer format
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise exceptions.AuthenticationFailed('Invalid token header')
    
    token = parts[1]
    
    try:
        # Decode the token
        payload = decode_jwt(token)
        user_id = payload.get('sub')
        
        # Get user from database
        user = User.objects.get(user_id=user_id)

        # Reject deactivated accounts
        if not user.is_active:
            raise exceptions.AuthenticationFailed("Account is deactivated")

        # Validate token version against the current database value.
        token_version = payload.get("token_version")

        if token_version is None:
            # Temporarily support legacy student tokens.
            # Admin tokens must always include a token version.
            if user.role != User.Role.STUDENT:
                raise exceptions.AuthenticationFailed(
                    "Token version missing"
                )

        elif (
            type(token_version) is not int
            or token_version != user.token_version
        ):
            raise exceptions.AuthenticationFailed(
                "Token revoked"
            )

        return user
        
    except jwt.PyJWTError:
        raise exceptions.AuthenticationFailed('Invalid token')
    except User.DoesNotExist:
        raise exceptions.AuthenticationFailed('User not found')