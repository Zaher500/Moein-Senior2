from rest_framework import serializers
from .models import ChatSession, ChatMessage


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = [
            'session_id',
            'student_id',
            'title',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['session_id', 'created_at', 'updated_at']


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            'message_id',
            'session',
            'role',
            'content',
            'created_at',
        ]
        read_only_fields = ['message_id', 'created_at']


class CreateChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = ['title']


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField()
