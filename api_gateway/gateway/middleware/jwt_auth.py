import requests    # admin
import re        #admin
import jwt
from django.http import JsonResponse
from django.conf import settings
from jwt import ExpiredSignatureError, InvalidTokenError

class JWTAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Public endpoints with exact path matching.
        public_paths = {
            "/api/signup/",
            "/api/login/",
            "/health/",
            "/api/decode-token/",
            "/api/register-initiate/",
            "/api/verify-otp/",
            "/api/verify-otp",
            "/api/resend-otp/",
            "/api/resend-otp",
        }

        if request.path in public_paths:
            return self.get_response(request)

        # Public dynamic endpoints requiring a valid UUID format.
        uuid_pattern = (
            r"[0-9a-fA-F]{8}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{12}"
        )

        dynamic_public_pattern = (
            rf"/api/check-(?:student|user)/{uuid_pattern}/"
        )

        if re.fullmatch(dynamic_public_pattern, request.path):
            return self.get_response(request)

        auth_header = request.META.get('HTTP_AUTHORIZATION') or (request.headers.get('Authorization') if hasattr(request, 'headers') else '')
        if not auth_header:
            return JsonResponse({'error': 'No authorization header'}, status=401)

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return JsonResponse({'error': 'Invalid token format'}, status=401)

        token = parts[1]

        try:
            jwt_secret = getattr(settings, 'JWT_SECRET', None)
            jwt_alg = getattr(settings, 'JWT_ALGORITHM', 'HS256')
            if not jwt_secret:
                return JsonResponse({'error': 'Server JWT not configured'}, status=500)


            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms=[jwt_alg],
            )

            user_id = (
                payload.get("sub")
                or payload.get("user_id")
                or payload.get("userId")
            )

            if not isinstance(user_id, str) or not user_id:
                return JsonResponse(
                    {"error": "Invalid token identity"},
                    status=401,
                )

            # Internal validation configuration.
            internal_secret = getattr(
                settings, "INTERNAL_SERVICE_SECRET", ""
            )

            account_url = settings.SERVICES.get(
                "account", ""
            ).rstrip("/")

            if not internal_secret or not account_url:
                return JsonResponse(
                    {"error": "Token validation not configured"},
                    status=503,
                )

            # Validate token against current Account Service state.
            try:
                validation_response = requests.post(
                    f"{account_url}/api/internal/token/validate/",
                    headers={
                        "Authorization": auth_header,
                        "X-INTERNAL-SERVICE-SECRET": internal_secret,
                    },
                    timeout=5,
                )
            except requests.RequestException:
                return JsonResponse(
                    {"error": "Token validation service unavailable"},
                    status=503,
                )

            if validation_response.status_code == 401:
                return JsonResponse(
                    {"error": "Token invalid or revoked"},
                    status=401,
                )

            if validation_response.status_code != 200:
                return JsonResponse(
                    {"error": "Token validation unavailable"},
                    status=503,
                )

            try:
                validation_data = validation_response.json()
            except ValueError:
                return JsonResponse(
                    {"error": "Invalid token validation response"},
                    status=503,
                )

            if (
                not isinstance(validation_data, dict)
                or validation_data.get("valid") is not True
                or validation_data.get("user_id") != user_id
                or validation_data.get("role")
                not in ("STUDENT", "ADMIN", "MAIN_ADMIN")
                or not isinstance(
                    validation_data.get("must_change_password"), bool
                )
            ):
                return JsonResponse(
                    {"error": "Token validation failed"},
                    status=503,
                )

            # Use the verified identity and current database role.
            request.user_id = user_id
            request.username = (
                payload.get("username")
                or payload.get("name")
            )
            request.role = validation_data["role"]
            request.must_change_password = validation_data[
                "must_change_password"
            ]

            # Use the current student identity from Account Service.
            student_id = validation_data.get("student_id")

            if request.role == "STUDENT":
                if not isinstance(student_id, str) or not student_id:
                    return JsonResponse(
                        {"error": "Invalid student identity"},
                        status=503,
                    )
            else:
                # Admins must not have a student identity.
                if student_id is not None:
                    return JsonResponse(
                        {"error": "Unexpected student identity"},
                        status=503,
                    )

            request.student_id = student_id

            return self.get_response(request)

        except ExpiredSignatureError:
            return JsonResponse({'error': 'Token expired'}, status=401)
        except InvalidTokenError:
            return JsonResponse({'error': 'Invalid token'}, status=401)
        except Exception as e:
            # Unexpected decode error
            return JsonResponse({'error': f'JWT decode error: {str(e)}'}, status=401)
