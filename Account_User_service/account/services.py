import random
import requests
from django.conf import settings
from .rabbitmq_publisher import publish_otp  #AR

def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp(email, otp, username):
    #  1. نحاول RabbitMQ أولاً
    try:
        publish_otp(email, otp)
        print("OTP sent via RabbitMQ")

        #  إذا نجح، لا نستخدم HTTP
        return {"message": "OTP sent via RabbitMQ"}

    except Exception as e:
        print("RabbitMQ failed, fallback to HTTP:", str(e))

    #  2. fallback إلى HTTP فقط إذا فشل RabbitMQ
    url = settings.NOTIFICATION_SERVICE_URL

    payload = {
        "email": email,
        "otp": otp,
        "username": username
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("HTTP also failed:", str(e))
        return {"error": "Failed to send OTP"}