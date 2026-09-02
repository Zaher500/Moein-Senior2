from ChatBot.selectors.chat_session_selector import get_student_session_or_404
from ChatBot.selectors.chat_message_selector import get_llm_ready_history
from ChatBot.services.chat_message_service import ChatMessageService
from ChatBot.services.rag_client import retrieve_context
from ChatBot.services.prompt_builder import PromptBuilder
from ChatBot.services.llm_service import LLMService


class ChatOrchestrator:
    @staticmethod
    def send_message(student_id, session_id, message_text):
        session = get_student_session_or_404(session_id, student_id)

        user_message = ChatMessageService.create_user_message(
            session=session, content=message_text
        )

        rag_result = retrieve_context(
            student_id=student_id,
            query=message_text,
        )
        print("RAG chunks count:", len(rag_result["chunks"]))
        print("RAG context preview:", rag_result["context_text"][:500])

        history = get_llm_ready_history(session=session, limit=10)

        history_without_current_message = history[:-1] if history else []

        retrieved_context = [
            chunk["chunk_text"]
            for chunk in rag_result["chunks"]
            if chunk.get("chunk_text")
        ]

        prompt_builder = PromptBuilder()
        messages = prompt_builder.build_messages(
            user_message=message_text,
            chat_history=history_without_current_message,
            retrieved_context=retrieved_context,
        )
        print("Final messages:", messages)

        llm_service = LLMService()
        try:
            assistant_text = llm_service.generate_response(messages=messages)
        except Exception as e:
            print("LLM ERROR:", str(e))
            assistant_text = f"LLM failed: {str(e)}"

        assistant_message = ChatMessageService.create_assistant_message(
            session=session, content=assistant_text
        )

        return {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "rag_result": rag_result,
        }
