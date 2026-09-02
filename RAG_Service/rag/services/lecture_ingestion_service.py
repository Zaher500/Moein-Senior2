import time
import uuid
from typing import Dict, List

from .embedding_service import EmbeddingService
from .vector_store_service import VectorStoreService


class LectureIngestionService:
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50

    @classmethod
    def ingest_lecture_text(
        cls,
        lecture_text: str,
        lecture_id: str,
        course_id: str,
        student_id: str,
        source_type: str = "lecture",
    ) -> Dict:
        cls._validate_inputs(
            lecture_text=lecture_text,
            lecture_id=lecture_id,
            course_id=course_id,
            student_id=student_id,
            source_type=source_type,
        )

        chunks = cls._chunk_text(lecture_text)

        if not chunks:
            raise ValueError("No chunks were generated from lecture text.")

        embeddings = EmbeddingService.embed_texts(chunks)

        created_at = int(time.time())

        chunk_records = [
            {
                "chunk_id": str(uuid.uuid4()),
                "embedding": embedding,
                "chunk_text": chunk_text,
                "lecture_id": lecture_id,
                "course_id": course_id,
                "student_id": student_id,
                "chunk_index": chunk_index,
                "source_type": source_type,
                "created_at": created_at,
            }
            for chunk_index, (chunk_text, embedding) in enumerate(
                zip(chunks, embeddings)
            )
        ]

        VectorStoreService.insert_chunks(chunk_records)

        return {
            "lecture_id": lecture_id,
            "course_id": course_id,
            "student_id": student_id,
            "source_type": source_type,
            "chunks_inserted": len(chunk_records),
            "chunk_ids": [
                chunk["chunk_id"]
                for chunk in chunk_records
            ],
        }

    @classmethod
    def _validate_inputs(
        cls,
        lecture_text: str,
        lecture_id: str,
        course_id: str,
        student_id: str,
        source_type: str,
    ) -> None:
        if not lecture_text or not lecture_text.strip():
            raise ValueError("Lecture text cannot be empty.")

        if not lecture_id:
            raise ValueError("lecture_id is required.")

        if not course_id:
            raise ValueError("course_id is required.")

        if not student_id:
            raise ValueError("student_id is required.")

        if not source_type:
            raise ValueError("source_type is required.")

    @classmethod
    def _chunk_text(cls, text: str) -> List[str]:
        words = text.split()

        if not words:
            return []

        chunks = []
        start = 0

        while start < len(words):
            end = start + cls.CHUNK_SIZE
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words).strip()

            if chunk_text:
                chunks.append(chunk_text)

            if end >= len(words):
                break

            start = end - cls.CHUNK_OVERLAP

        return chunks