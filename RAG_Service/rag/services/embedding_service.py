from typing import List

from django.conf import settings


class EmbeddingService:
    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            from sentence_transformers import SentenceTransformer

            cls._model = SentenceTransformer(
                settings.EMBEDDING_MODEL,
                token=settings.HF_TOKEN,
            )

        return cls._model

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
