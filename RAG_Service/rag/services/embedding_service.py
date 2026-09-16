from threading import Lock
from typing import List

from django.conf import settings


class EmbeddingService:
    _model = None
    _model_lock = Lock()

    _warmup_complete = False
    _warmup_lock = Lock()

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            with cls._model_lock:
                if cls._model is None:
                    cls._model = cls._create_model()

        return cls._model

    @classmethod
    def warm_up(cls) -> None:
        if cls._warmup_complete:
            return

        with cls._warmup_lock:
            if cls._warmup_complete:
                return

            cls.embed_text("RAG service warm-up")
            cls._warmup_complete = True

    @classmethod
    def embed_text(cls, text: str) -> List[float]:
        if not text or not text.strip():
            raise ValueError("Text for embedding cannot be empty.")

        model = cls._get_model()

        embedding = model.encode(
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).tolist()

        cls._validate_embedding_dimension(embedding)

        return embedding

    @classmethod
    def embed_texts(cls, texts: List[str]) -> List[List[float]]:
        if not texts:
            raise ValueError("Texts list for embedding cannot be empty.")

        cleaned_texts = []

        for text in texts:
            if not text or not text.strip():
                raise ValueError("Texts list contains an empty text.")

            cleaned_texts.append(text)

        model = cls._get_model()

        embeddings = model.encode(
            cleaned_texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).tolist()

        for embedding in embeddings:
            cls._validate_embedding_dimension(embedding)

        return embeddings

    @staticmethod
    def _validate_embedding_dimension(embedding: List[float]) -> None:
        expected_dimension = settings.EMBEDDING_DIMENSION

        if len(embedding) != expected_dimension:
            raise ValueError(
                "Invalid embedding dimension: "
                f"expected {expected_dimension}, got {len(embedding)}"
            )

    @classmethod
    def _create_model(cls):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            settings.EMBEDDING_MODEL,
            token=settings.HF_TOKEN,
        )
