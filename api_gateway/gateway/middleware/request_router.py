# api_gateway/gateway/middleware/request_router.py
import requests
from django.http import HttpResponse, JsonResponse
import json
from django.conf import settings
import urllib.parse

class RequestRouterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

        # Map service names to URLs (use settings.SERVICES)
        self.routes = {
            'account': settings.SERVICES['account'].rstrip('/'),
            'course': settings.SERVICES['course'].rstrip('/'),
            'summarizer': settings.SERVICES['summarizer'].rstrip('/'),
            'chatbot': settings.SERVICES['chatbot'].rstrip('/'),

            # ✅ الحل هنا
            #'notifications': settings.SERVICES['notifications'].rstrip('/'),
        }

        # Map URL paths to services — keep specific/longer paths here
        self.path_mapping = {
            # account-related
            '/api/signup': 'account',
            '/api/login': 'account',
            '/api/delete': 'account',
            '/api/edit': 'account',
            '/api/decode-token': 'account',
            '/api/check-student': 'account',
            '/api/check-user': 'account',
            '/api/me': 'account',
            '/api/register-initiate': 'account',
            '/api/register-initiate/': 'account',
            '/api/verify-otp': 'account',
            '/api/verify-otp/': 'account',

            #"/api/notifications/": "http://127.0.0.1:8005/api/notifications/",    #AYO
            '/api/notifications/': 'notifications',            #AYO
            # course-related (make sure media is included)
            '/api/media': 'course',
            '/api/media/': 'course',

            '/api/courses': 'course',
            '/api/courses/': 'course',
            '/api/lectures': 'course',
            '/api/lectures/': 'course',
            '/api/delete-student-courses/<uuid>/': 'course',
            '/api/summarize': 'summarizer',
            '/api/summarize/': 'summarizer',

            # chatbot-related
            '/api/chat/test': 'chatbot',
            '/api/chat/test/': 'chatbot',
            '/api/chat/sessions': 'chatbot',
            '/api/chat/sessions/': 'chatbot',
            '/api/chat/lectures/ingest': 'chatbot',
            '/api/chat/lectures/ingest/': 'chatbot',
            
        }

        # debug: show route map at startup
        print("[Gateway DEBUG] route map:", self.routes)
        print("[Gateway DEBUG] path mapping keys:", list(self.path_mapping.keys()))

    def __call__(self, request):
        # Determine which service this request is for
        service_name = None

        # Important: match longest prefixes first so '/api/media/...' matches before '/api/'
        for path_prefix in sorted(self.path_mapping.keys(), key=len, reverse=True):
            if request.path.startswith(path_prefix):
                service_name = self.path_mapping[path_prefix]
                break

        if not service_name:
            # Not a proxied path — hand to Django as usual
            return self.get_response(request)

        service_url = self.routes.get(service_name)
        if not service_url:
            return JsonResponse({'error': 'Service not configured'}, status=502)

        # Build the target URL carefully: preserve query string
        target_url = urllib.parse.urljoin(service_url + '/', request.get_full_path().lstrip('/'))

        # Debug which upstream will be used
        print(f"[Gateway DEBUG] forwarding to -> {target_url}")

        # Base headers for all requests
        headers = {
            'ngrok-skip-browser-warning': 'true',
            'X-GATEWAY-SECRET': getattr(settings, 'GATEWAY_SECRET', '')
        }

        # Forward Authorization if exists
        auth = request.META.get('HTTP_AUTHORIZATION') or (request.headers.get('Authorization') if hasattr(request, 'headers') else None)
        if auth:
            headers['Authorization'] = auth

        # Remove client-supplied identity headers to prevent spoofing
        request.META.pop('HTTP_X_STUDENT_ID', None)
        request.META.pop('HTTP_X_USER_ID', None)
        request.META.pop('HTTP_X_USERNAME', None)

        # If previous middleware set request.user_id/student_id, inject them
        user_id = getattr(request, 'user_id', None)
        student_id = getattr(request, 'student_id', None)
        if student_id:
            headers['X-Student-ID'] = str(student_id)
        elif user_id:
            headers['X-User-ID'] = str(user_id)

        username = getattr(request, 'username', None)
        if username:
            headers['X-Username'] = username
            
        print("Forwarded headers:", headers)

        # Detect content type and forward request accordingly
        content_type = request.META.get('CONTENT_TYPE', '')
        print("[Gateway DEBUG] forwarding headers sample:", {k:v for k,v in headers.items() if 'GATEWAY' in k.upper() or 'STUDENT' in k.upper()})
        try:
            if content_type.startswith('application/json') and request.body:
                try:
                    json_data = json.loads(request.body)
                    response = requests.request(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        json=json_data,
                        params=request.GET,
                        timeout=60,
                        verify=True
                    )
                except json.JSONDecodeError:
                    response = requests.request(
                        method=request.method,
                        url=target_url,
                        headers=headers,
                        data=request.body,
                        params=request.GET,
                        timeout=60,
                        verify=True
                    )
                    

            elif content_type.startswith('multipart/form-data'):
                response = requests.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=request.POST,
                    files=request.FILES,
                    params=request.GET,
                    timeout=60,
                    verify=True
                )

            else:
                response = requests.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=request.body,
                    params=request.GET,
                    timeout=60,
                    verify=True
                )

            return HttpResponse(
                content=response.content,
                status=response.status_code,
                content_type=response.headers.get('Content-Type', 'application/json')
            )

        except requests.exceptions.ConnectionError:
            return JsonResponse({'error': 'Cannot connect to service'}, status=503)
        except requests.exceptions.SSLError as e:
            return JsonResponse({'error': f'SSL error: {str(e)}'}, status=502)
        except Exception as e:
            return JsonResponse({'error': f'Gateway error: {str(e)}'}, status=500)
