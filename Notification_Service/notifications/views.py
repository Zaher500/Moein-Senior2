import json
import pika

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth_utils import get_user_from_headers
from .in_memory_store import notifications_store
from .serializers import SendOTPSerializer
from .utils import send_email_otp

class SendOTPEmailAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        email = data["email"]
        otp = data["otp"]
        username = data.get("username", "User")

        subject = "Your OTP Code"
        message = f"""
Hello {username},

Your OTP code is: {otp}

This code will expire soon.
"""

        try:
            send_email_otp(email, otp, username)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"message": "OTP email sent successfully"},
            status=status.HTTP_200_OK,
        )
    


#AYO
class UserNotificationsAPIView(APIView):
    def get(self, request):
        user = get_user_from_headers(request)

        if not user:
            return Response({"error": "Unauthorized"}, status=401)

        user_id = user["user_id"]

        user_notifications = notifications_store.get(user_id, [])

        return Response(user_notifications)


class MarkNotificationReadAPIView(APIView):
    def post(self, request):
        #user_id = request.data.get("user_id")
        user_id = get_user_from_headers(request)["user_id"]
        notification_id = request.data.get("notification_id")

        user_notifications = notifications_store.get(user_id, [])

        for n in user_notifications:
            if n["id"] == notification_id:
                n["is_read"] = True
                break

        return Response({"message": "Notification marked as read"})
    


#AYO  مشان اختبار بوستمان بس

class TestPublishNotificationAPIView(APIView):
    def post(self, request):
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='localhost')
        )
        channel = connection.channel()

        channel.queue_declare(queue='notifications_queue')

        data = request.data

        channel.basic_publish(
            exchange='',
            routing_key='notifications_queue',
            body=json.dumps(data)
        )

        connection.close()

        return Response({"message": "Notification sent to queue"})