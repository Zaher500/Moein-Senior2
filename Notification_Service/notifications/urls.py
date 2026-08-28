from django.urls import path
from .views import SendOTPEmailAPIView
from .views import UserNotificationsAPIView, MarkNotificationReadAPIView #AYO

urlpatterns = [
    path("send-otp/", SendOTPEmailAPIView.as_view()),

    path("user-notifications/", UserNotificationsAPIView.as_view()),  #AYO
    path("mark-as-read/", MarkNotificationReadAPIView.as_view()),   #AYO
]

#AYO  مشان اختبار بوستمان بس
from .views import TestPublishNotificationAPIView

urlpatterns += [
    path("test-send-notification/", TestPublishNotificationAPIView.as_view()),
]