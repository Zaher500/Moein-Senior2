from django.urls import path
from .views import (
    test_chatbot,
    create_chat_session,
    list_chat_sessions,
    get_chat_session,
    send_message,
)

urlpatterns = [
    path('chat/test/', test_chatbot),
    path('chat/sessions/create/', create_chat_session),
    path('chat/sessions/', list_chat_sessions),
    path('chat/sessions/<uuid:session_id>/', get_chat_session),
    path('chat/sessions/<uuid:session_id>/messages/send/', send_message),
]
