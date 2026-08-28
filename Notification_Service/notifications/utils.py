from django.core.mail import send_mail
from django.conf import settings


def send_email_otp(email, otp, username="User"):
    subject = "Your OTP Code"
    message = f"""
Hello {username},

Your OTP code is: {otp}

This code will expire soon.
"""

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )