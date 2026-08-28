import requests
from django.http import HttpResponse, JsonResponse
import json
from django.conf import settings
import urllib.parse

class RequestRouterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

        self.routes = {
            'account': settings.SERVICES['account'].rstrip('/'),
            'course': settings.SERVICES['course'].rstrip('/'),
            'summarizer': settings.SERVICES['summarizer'].rstrip('/'),
            'chatbot': settings.SERVICES['chatbot'].rstrip('/'),
            'stt': settings.SERVICES['stt'].rstrip('/'),
            'quiz': settings.SERVICES['quiz'].rstrip('/'),
            'notification': settings.SERVICES['notification'].rstrip('/'),
        }

        self.path_mapping = {
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

            '/api/register-initiate': 'account',
            '/api/register-initiate/': 'account',
            '/api/verify-otp': 'account',
            '/api/verify-otp/': 'account',

            '/api/media': 'course',
            '/api/media/': 'course',
            '/api/courses': 'course',
            '/api/courses/': 'course',
            '/api/lectures': 'course',
            '/api/lectures/': 'course',
            '/api/generate/existing/': 'course',
            '/api/generate/existing': 'course',

            # '/api/summarize': 'summarizer',
            # '/api/summarize/': 'summarizer',

            '/api/chat/test': 'chatbot',
            '/api/chat/test/': 'chatbot',
            '/api/chat/sessions': 'chatbot',
            '/api/chat/sessions/': 'chatbot',
            '/api/chat/lectures/ingest': 'chatbot',
            '/api/chat/lectures/ingest/': 'chatbot',

            '/stt/upload': 'stt',
            '/stt/upload/': 'stt',
            '/stt/stt-status': 'stt',
            '/stt/stt-status/': 'stt',

            '/api/quiz': 'quiz',
            '/api/quiz/': 'quiz',

            '/api/notifications/': 'notification',
            '/api/notifications': 'notification',
            '/notifications/': 'notification',
            '/notifications': 'notification',
        }

    def __call__(self, request):
        print("\n========== GATEWAY REQUEST START ==========")
        print(f"[Gateway] Incoming method: {request.method}")
        print(f"[Gateway] Incoming path: {request.path}")
        print(f"[Gateway] Full path: {request.get_full_path()}")

        service_name = None
        matched_prefix = None

        for path_prefix in sorted(self.path_mapping.keys(), key=len, reverse=True):
            if request.path.startswith(path_prefix):
                service_name = self.path_mapping[path_prefix]
                matched_prefix = path_prefix
                break

        print(f"[Gateway] Matched prefix: {matched_prefix}")
        print(f"[Gateway] Service name: {service_name}")

        if not service_name:
            print("[Gateway] No matching service. Passing to Django directly.")
            print("========== GATEWAY REQUEST END ==========\n")
            return self.get_response(request)

        service_url = self.routes.get(service_name)
        print(f"[Gateway] Service base URL: {service_url}")

        if not service_url:
            print("[Gateway] ERROR: Service not configured")
            print("========== GATEWAY REQUEST END ==========\n")
            return JsonResponse({'error': 'Service not configured'}, status=502)

        path = request.get_full_path()

        if path.startswith('/api/quiz/'):
            path = path.replace('/api/quiz/', '/quiz/', 1)
        elif path == '/api/quiz':
            path = '/quiz'

        target_url = urllib.parse.urljoin(
            service_url + '/',
            path.lstrip('/')
        )

        print(f"[Gateway] Forward target URL: {target_url}")

        headers = {
            'ngrok-skip-browser-warning': 'true',
            'X-GATEWAY-SECRET': getattr(settings, 'GATEWAY_SECRET', '')
        }

        auth = request.META.get('HTTP_AUTHORIZATION') or (
            request.headers.get('Authorization') if hasattr(request, 'headers') else None
        )
        if auth:
            headers['Authorization'] = auth

        request.META.pop('HTTP_X_STUDENT_ID', None)
        request.META.pop('HTTP_X_USER_ID', None)
        request.META.pop('HTTP_X_USERNAME', None)

        user_id = getattr(request, 'user_id', None)
        student_id = getattr(request, 'student_id', None)
        username = getattr(request, 'username', None)

        if student_id:
            headers['X-Student-ID'] = str(student_id)
        if user_id:
            headers['X-User-ID'] = str(user_id)
        if username:
            headers['X-Username'] = str(username)

        print(f"[Gateway] user_id: {user_id}")
        print(f"[Gateway] student_id: {student_id}")
        print(f"[Gateway] username: {username}")
        print(f"[Gateway] Forwarded headers: {headers}")

        content_type = request.META.get('CONTENT_TYPE', '')
        print(f"[Gateway] Content-Type: {content_type}")
        print(f"[Gateway] Query params: {dict(request.GET)}")

        if request.body:
            try:
                preview = request.body.decode("utf-8")[:500]
            except Exception:
                preview = str(request.body[:500])
            print(f"[Gateway] Body preview: {preview}")
        else:
            print("[Gateway] No request body")

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
                files = {}

                for key, uploaded_file in request.FILES.items():
                    files[key] = (
                        uploaded_file.name,
                        uploaded_file.file,
                        uploaded_file.content_type
                    )

                response = requests.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=request.POST.dict(),
                    files=files,
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

            # return HttpResponse(
            #     content=response.content,
            #     status=response.status_code,
            #     content_type=response.headers.get('Content-Type', 'application/json')
            # )
            


            gateway_response = HttpResponse(
                content=response.content,
                status=response.status_code,
                content_type=response.headers.get(
                    'Content-Type',
                    'application/json'
                )
            )

            content_disposition = response.headers.get(
                'Content-Disposition'
            )

            if content_disposition:
                gateway_response['Content-Disposition'] = content_disposition

            return gateway_response

        except requests.exceptions.ConnectionError:
            return JsonResponse({'error': 'Cannot connect to service'}, status=503)

        except requests.exceptions.SSLError as e:
            print(f"[Gateway] SSLError: {e}")
            print("========== GATEWAY REQUEST END ==========\n")
            return JsonResponse({'error': f'SSL error: {str(e)}'}, status=502)

        except Exception as e:
            print(f"[Gateway] Unexpected error: {e}")
            print("========== GATEWAY REQUEST END ==========\n")
            return JsonResponse({'error': f'Gateway error: {str(e)}'}, status=500)