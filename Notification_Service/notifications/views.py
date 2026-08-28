from django.shortcuts import render

# Create your views here.
from django.core.mail import send_mail
from django.conf import settings

#from AI_ChatBot_service.ChatBot.utils.user_headers import get_user_from_headers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import SendOTPSerializer
from .utils import send_email_otp  #AR

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
from rest_framework.views import APIView
from rest_framework.response import Response

from .in_memory_store import notifications_store


class UserNotificationsAPIView(APIView):
    def get(self, request):
        from .auth_utils import get_user_from_headers
        from .in_memory_store import notifications_store

        print("===== DEBUG NOTIFICATIONS =====")

        user = get_user_from_headers(request)

        if not user:
            print(" No user from headers")
            return Response({"error": "Unauthorized"}, status=401)

        user_id = user["user_id"]

        print(" User from JWT (header):", user_id)
        print(" All keys in notifications_store:", list(notifications_store.keys()))

        user_notifications = notifications_store.get(user_id, [])

        print(" Notifications found:", user_notifications)
        print("================================")

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
import pika
import json


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
    


#CloudAMQP
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .in_memory_store import notifications_store
from .auth_utils import get_user_from_headers


@api_view(['GET'])
def get_user_notifications(request):
    print("===== DEBUG NOTIFICATIONS =====")
    user = get_user_from_headers(request)

    if not user:
        print(" No user from headers")
        return Response({"error": "Unauthorized"}, status=401)
    
    user_id = user["user_id"]
    print(" User from JWT (header):", user_id)

    print(" All keys in notifications_store:", list(notifications_store.keys()))

    user_notifications = notifications_store.get(user_id, [])
    print(" Notifications found:", user_notifications)

    print("================================")
    return Response(user_notifications)



@api_view(['POST'])
def mark_as_read(request):
    user = get_user_from_headers(request)

    if not user:
        return Response({"error": "Unauthorized"}, status=401)

    user_id = user["user_id"]
    notification_id = request.data.get("notification_id")

    user_notifications = notifications_store.get(user_id, [])

    for notif in user_notifications:
        if notif["id"] == notification_id:
            notif["is_read"] = True

    return Response({"message": "Marked as read"})