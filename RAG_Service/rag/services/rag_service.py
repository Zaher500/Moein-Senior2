from .embedding_service import EmbeddingService
from .vector_store_service import VectorStoreService


class RAGService:
    @staticmethod
    def retrieve_context(
        student_id: str,
        query: str,
        course_id: str | None = None,
        lecture_id: str | None = None,
        top_k: int = 5,
    ) -> dict:
        if not student_id:
            raise ValueError("student_id is required.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        if not query or not query.strip():
            return {
                "chunks": [],
                "context_text": "",
                "sources": [],
            }

        query_embedding = EmbeddingService.embed_text(query)

        chunks = VectorStoreService.search_chunks(
            query_embedding=query_embedding,
            limit=top_k,
            student_id=student_id,
            course_id=course_id,
            lecture_id=lecture_id,
        )

        sorted_chunks = sorted(
            chunks,
            key=lambda chunk: chunk["chunk_index"],
        )

        context_text = "\n\n".join(
            chunk["chunk_text"]
            for chunk in sorted_chunks
            if chunk.get("chunk_text")
        )

        sources = [
            {
                "chunk_id": chunk["chunk_id"],
                "lecture_id": chunk["lecture_id"],
                "course_id": chunk["course_id"],
                "chunk_index": chunk["chunk_index"],
                "score": chunk["score"],
            }
            for chunk in sorted_chunks
        ]

        return {
            "chunks": sorted_chunks,
            "context_text": context_text,
            "sources": sources,
        }
