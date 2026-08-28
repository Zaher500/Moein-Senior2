# gateway/jwt_utils.py
import jwt
from django.http import JsonResponse
from django.conf import settings
from jwt import ExpiredSignatureError, InvalidTokenError

class JWTAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Public endpoints that don't require auth
        public_paths = [
            '/api/signup/',
            '/api/login/',
            '/health/',
            '/api/decode-token/',
            '/api/check-student/',  # used by course service
            '/api/check-user/',     # used by account service
            '/api/register-initiate/',
            '/api/verify-otp/',

            # ✅ الحل النهائي
            #'/api/notifications/',
        ]

        for path in public_paths:
            if request.path.startswith(path):
                return self.get_response(request)

        # Get auth header (works with both request.META and request.headers)
        auth_header = request.META.get('HTTP_AUTHORIZATION') or (request.headers.get('Authorization') if hasattr(request, 'headers') else '')
        if not auth_header:
            return JsonResponse({'error': 'No authorization header'}, status=401)

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return JsonResponse({'error': 'Invalid token format'}, status=401)

        token = parts[1]

        try:
            # Use settings for secret/algorithm (set these in your gateway settings)
            jwt_secret = getattr(settings, 'JWT_SECRET', None)
            jwt_alg = getattr(settings, 'JWT_ALGORITHM', 'HS256')
            if not jwt_secret:
                # Fail fast if secret missing (helps catch config errors)
                return JsonResponse({'error': 'Server JWT not configured'}, status=500)

            payload = jwt.decode(token, jwt_secret, algorithms=[jwt_alg])
            print("JWT payload:", payload)
            print("student_id from token:", payload.get("student_id"))
            print("user_id from token:", payload.get("sub") or payload.get("user_id"))

            # Common claim names: sub, user_id, student_id, username
            request.user_id = payload.get('sub') or payload.get('user_id') or payload.get('userId') or None
            request.username = payload.get('username') or payload.get('name') or None

            # IMPORTANT: if token contains student_id, attach it so router can forward it
            request.student_id = (
            payload.get('student_id')
            or payload.get('studentId')
            or payload.get('sub')
            or payload.get('user_id')
            or payload.get('userId')
            or None
        )

            return self.get_response(request)

        except ExpiredSignatureError:
            return JsonResponse({'error': 'Token expired'}, status=401)
        except InvalidTokenError:
            return JsonResponse({'error': 'Invalid token'}, status=401)
        except Exception as e:
            # Unexpected decode error
            return JsonResponse({'error': f'JWT decode error: {str(e)}'}, status=401)
