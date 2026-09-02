from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from ChatBot.services.chat_orchestrator import ChatOrchestrator

from ChatBot.services.rag_client import (
    RAGClientError,
    retrieve_context,
)

class RAGClientTests(SimpleTestCase):
    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_RETRIEVAL_TIMEOUT=15,
    )
    @patch("ChatBot.services.rag_client.requests.post")
    def test_retrieve_context_sends_expected_request(self, mock_post):
        response = MagicMock()
        response.json.return_value = {
            "chunks": [],
            "context_text": "",
            "sources": [],
        }
        mock_post.return_value = response

        result = retrieve_context(
            student_id="student-1",
            query="What is RAG?",
            course_id="course-1",
            lecture_id="lecture-1",
            top_k=5,
        )

        self.assertEqual(
            result,
            {
                "chunks": [],
                "context_text": "",
                "sources": [],
            },
        )

        mock_post.assert_called_once_with(
            "http://rag-service:8005/api/rag/retrieve/",
            json={
                "student_id": "student-1",
                "query": "What is RAG?",
                "top_k": 5,
                "course_id": "course-1",
                "lecture_id": "lecture-1",
            },
            headers={
                "X-Internal-Service-Key": "test-key",
            },
            timeout=15,
        )

        response.raise_for_status.assert_called_once_with()

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY=None,
        RAG_RETRIEVAL_TIMEOUT=15,
    )
    def test_retrieve_context_rejects_missing_internal_key(self):
        with self.assertRaises(RAGClientError):
            retrieve_context(
                student_id="student-1",
                query="What is RAG?",
            )

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_RETRIEVAL_TIMEOUT=15,
    )
    @patch("ChatBot.services.rag_client.requests.post")
    def test_retrieve_context_wraps_request_failure(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException(
            "connection failed"
        )

        with self.assertRaises(RAGClientError):
            retrieve_context(
                student_id="student-1",
                query="What is RAG?",
            )

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_RETRIEVAL_TIMEOUT=15,
    )
    @patch("ChatBot.services.rag_client.requests.post")
    def test_retrieve_context_rejects_invalid_json(self, mock_post):
        response = MagicMock()
        response.json.side_effect = ValueError("invalid json")
        mock_post.return_value = response

        with self.assertRaises(RAGClientError):
            retrieve_context(
                student_id="student-1",
                query="What is RAG?",
            )


class ChatOrchestratorRegressionTests(SimpleTestCase):
    @patch("ChatBot.services.chat_orchestrator.LLMService")
    @patch("ChatBot.services.chat_orchestrator.PromptBuilder")
    @patch("ChatBot.services.chat_orchestrator.get_llm_ready_history")
    @patch("ChatBot.services.chat_orchestrator.retrieve_context")
    @patch(
        "ChatBot.services.chat_orchestrator."
        "ChatMessageService.create_assistant_message"
    )
    @patch(
        "ChatBot.services.chat_orchestrator."
        "ChatMessageService.create_user_message"
    )
    @patch(
        "ChatBot.services.chat_orchestrator."
        "get_student_session_or_404"
    )
    def test_send_message_uses_rag_context_in_prompt(
        self,
        mock_get_session,
        mock_create_user_message,
        mock_create_assistant_message,
        mock_retrieve_context,
        mock_get_history,
        mock_prompt_builder_class,
        mock_llm_service_class,
    ):
        session = MagicMock()
        user_message = MagicMock()
        assistant_message = MagicMock()

        mock_get_session.return_value = session
        mock_create_user_message.return_value = user_message
        mock_create_assistant_message.return_value = assistant_message
        mock_get_history.return_value = []

        mock_retrieve_context.return_value = {
            "chunks": [
                {
                    "chunk_id": "chunk-1",
                    "chunk_text": "First retrieved chunk",
                },
                {
                    "chunk_id": "chunk-2",
                    "chunk_text": "Second retrieved chunk",
                },
            ],
            "context_text": (
                "First retrieved chunk\n\n"
                "Second retrieved chunk"
            ),
            "sources": [],
        }

        prompt_builder = mock_prompt_builder_class.return_value
        prompt_builder.build_messages.return_value = [
            {
                "role": "user",
                "content": "What is RAG?",
            }
        ]

        llm_service = mock_llm_service_class.return_value
        llm_service.generate_response.return_value = "Assistant response"

        result = ChatOrchestrator.send_message(
            student_id="student-1",
            session_id="session-1",
            message_text="What is RAG?",
        )

        mock_get_session.assert_called_once_with(
            "session-1",
            "student-1",
        )

        mock_create_user_message.assert_called_once_with(
            session=session,
            content="What is RAG?",
        )

        mock_retrieve_context.assert_called_once_with(
            student_id="student-1",
            query="What is RAG?",
        )

        prompt_builder.build_messages.assert_called_once_with(
            user_message="What is RAG?",
            chat_history=[],
            retrieved_context=[
                "First retrieved chunk",
                "Second retrieved chunk",
            ],
        )

        llm_service.generate_response.assert_called_once_with(
            messages=[
                {
                    "role": "user",
                    "content": "What is RAG?",
                }
            ]
        )

        mock_create_assistant_message.assert_called_once_with(
            session=session,
            content="Assistant response",
        )

        self.assertIs(result["user_message"], user_message)
        self.assertIs(result["assistant_message"], assistant_message)
        self.assertEqual(
            result["rag_result"],
            mock_retrieve_context.return_value,
        )

    @patch("ChatBot.services.chat_orchestrator.LLMService")
    @patch("ChatBot.services.chat_orchestrator.PromptBuilder")
    @patch("ChatBot.services.chat_orchestrator.get_llm_ready_history")
    @patch("ChatBot.services.chat_orchestrator.retrieve_context")
    @patch(
        "ChatBot.services.chat_orchestrator."
        "ChatMessageService.create_assistant_message"
    )
    @patch(
        "ChatBot.services.chat_orchestrator."
        "ChatMessageService.create_user_message"
    )
    @patch(
        "ChatBot.services.chat_orchestrator."
        "get_student_session_or_404"
    )
    def test_send_message_preserves_history_and_excludes_current_message(
        self,
        mock_get_session,
        mock_create_user_message,
        mock_create_assistant_message,
        mock_retrieve_context,
        mock_get_history,
        mock_prompt_builder_class,
        mock_llm_service_class,
    ):
        session = MagicMock()
        mock_get_session.return_value = session

        mock_retrieve_context.return_value = {
            "chunks": [],
            "context_text": "",
            "sources": [],
        }

        history = [
            {
                "role": "user",
                "content": "Previous question",
            },
            {
                "role": "assistant",
                "content": "Previous answer",
            },
            {
                "role": "user",
                "content": "Current question",
            },
        ]
        mock_get_history.return_value = history

        prompt_builder = mock_prompt_builder_class.return_value
        prompt_builder.build_messages.return_value = []

        llm_service = mock_llm_service_class.return_value
        llm_service.generate_response.return_value = "Response"

        ChatOrchestrator.send_message(
            student_id="student-1",
            session_id="session-1",
            message_text="Current question",
        )

        mock_get_history.assert_called_once_with(
            session=session,
            limit=10,
        )

        prompt_builder.build_messages.assert_called_once_with(
            user_message="Current question",
            chat_history=[
                {
                    "role": "user",
                    "content": "Previous question",
                },
                {
                    "role": "assistant",
                    "content": "Previous answer",
                },
            ],
            retrieved_context=[],
        )
