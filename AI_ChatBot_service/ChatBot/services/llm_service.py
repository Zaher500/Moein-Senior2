from ChatBot.utils.llm_client import LLMClient


class LLMService:
    def __init__(self):
        self.client = LLMClient()

    def generate_response(self, messages):
        try:
            response = self.client.chat_completion(messages=messages)
            return response.strip()
        except Exception as exc:
            raise RuntimeError(
                "LLM service request failed."
            ) from exc
