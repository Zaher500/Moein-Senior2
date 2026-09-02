from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import (
    ChatSessionSerializer,
    ChatMessageSerializer,
    CreateChatSessionSerializer,
    SendMessageSerializer,
)
from ChatBot.utils.user_headers import get_user_from_headers

from .selectors.chat_session_selector import (
    get_student_sessions,
    get_student_session_or_404,
)
from .selectors.chat_message_selector import get_session_messages
from .services.chat_session_service import ChatSessionService
from .services.chat_orchestrator import ChatOrchestrator


def extract_student_id(request):
    user = get_user_from_headers(request)
    student_id = user.get("student_id")
    return user, student_id


@api_view(["GET"])
def test_chatbot(request):
    user = get_user_from_headers(request)
    return Response({
        "message": "ChatBot service is working",
        "user": user
    })


@api_view(["POST"])
def create_chat_session(request):
    user, student_id = extract_student_id(request)

    if not student_id:
        return Response(
            {"error": "Student ID not found in headers"},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = CreateChatSessionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    session = ChatSessionService.create_session(
        student_id=student_id,
        title=serializer.validated_data.get("title")
    )

    return Response(
        ChatSessionSerializer(session).data,
        status=status.HTTP_201_CREATED
    )


@api_view(["GET"])
def list_chat_sessions(request):
    user, student_id = extract_student_id(request)

    if not student_id:
        return Response(
            {"error": "Student ID not found in headers"},
            status=status.HTTP_400_BAD_REQUEST
        )

    sessions = get_student_sessions(student_id)
    serializer = ChatSessionSerializer(sessions, many=True)

    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
def get_chat_session(request, session_id):
    user, student_id = extract_student_id(request)

    if not student_id:
        return Response(
            {"error": "Student ID not found in headers"},
            status=status.HTTP_400_BAD_REQUEST
        )

    session = get_student_session_or_404(session_id, student_id)
    messages = get_session_messages(session)

    return Response({
        "session": ChatSessionSerializer(session).data,
        "messages": ChatMessageSerializer(messages, many=True).data
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
def send_message(request, session_id):
    user, student_id = extract_student_id(request)

    if not student_id:
        return Response(
            {"error": "Student ID not found in headers"},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = SendMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    result = ChatOrchestrator.send_message(
        student_id=student_id,
        session_id=session_id,
        message_text=serializer.validated_data["content"]
    )

    return Response({
        "user_message": ChatMessageSerializer(result["user_message"]).data,
        "assistant_message": ChatMessageSerializer(result["assistant_message"]).data,
    }, status=status.HTTP_201_CREATED)
