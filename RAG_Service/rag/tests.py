from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from rag.services.lecture_ingestion_service import LectureIngestionService
from rag.services.rag_service import RAGService
from rag.services.vector_store_service import VectorStoreService


class HealthCheckAPITests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_check_returns_ok(self):
        response = self.client.get(reverse("rag-health"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "service": "rag",
                "status": "ok",
            },
        )


class RAGServiceTests(SimpleTestCase):
    @patch("rag.services.rag_service.VectorStoreService.search_chunks")
    @patch("rag.services.rag_service.EmbeddingService.embed_text")
    def test_retrieve_context_returns_sorted_chunks_context_and_sources(
        self,
        mock_embed_text,
        mock_search_chunks,
    ):
        mock_embed_text.return_value = [0.1, 0.2]

        mock_search_chunks.return_value = [
            {
                "chunk_id": "chunk-2",
                "chunk_text": "Second chunk",
                "lecture_id": "lecture-1",
                "course_id": "course-1",
                "chunk_index": 2,
                "source_type": "lecture",
                "student_id": "student-1",
                "score": 0.8,
            },
            {
                "chunk_id": "chunk-1",
                "chunk_text": "First chunk",
                "lecture_id": "lecture-1",
                "course_id": "course-1",
                "chunk_index": 1,
                "source_type": "lecture",
                "student_id": "student-1",
                "score": 0.9,
            },
        ]

        result = RAGService.retrieve_context(
            student_id="student-1",
            query="What is RAG?",
            course_id="course-1",
            lecture_id="lecture-1",
            top_k=5,
        )

        mock_embed_text.assert_called_once_with("What is RAG?")

        mock_search_chunks.assert_called_once_with(
            query_embedding=[0.1, 0.2],
            limit=5,
            student_id="student-1",
            course_id="course-1",
            lecture_id="lecture-1",
        )

        self.assertEqual(
            [chunk["chunk_id"] for chunk in result["chunks"]],
            ["chunk-1", "chunk-2"],
        )

        self.assertEqual(
            result["context_text"],
            "First chunk\n\nSecond chunk",
        )

        self.assertEqual(
            result["sources"],
            [
                {
                    "chunk_id": "chunk-1",
                    "lecture_id": "lecture-1",
                    "course_id": "course-1",
                    "chunk_index": 1,
                    "score": 0.9,
                },
                {
                    "chunk_id": "chunk-2",
                    "lecture_id": "lecture-1",
                    "course_id": "course-1",
                    "chunk_index": 2,
                    "score": 0.8,
                },
            ],
        )

    @patch("rag.services.rag_service.VectorStoreService.search_chunks")
    @patch("rag.services.rag_service.EmbeddingService.embed_text")
    def test_empty_query_returns_empty_result_without_retrieval(
        self,
        mock_embed_text,
        mock_search_chunks,
    ):
        result = RAGService.retrieve_context(
            student_id="student-1",
            query="   ",
        )

        self.assertEqual(
            result,
            {
                "chunks": [],
                "context_text": "",
                "sources": [],
            },
        )

        mock_embed_text.assert_not_called()
        mock_search_chunks.assert_not_called()

    def test_missing_student_id_raises_value_error(self):
        with self.assertRaisesMessage(
            ValueError,
            "student_id is required.",
        ):
            RAGService.retrieve_context(
                student_id="",
                query="What is RAG?",
            )

    def test_invalid_top_k_raises_value_error(self):
        with self.assertRaisesMessage(
            ValueError,
            "top_k must be greater than zero.",
        ):
            RAGService.retrieve_context(
                student_id="student-1",
                query="What is RAG?",
                top_k=0,
            )


class LectureIngestionServiceTests(SimpleTestCase):
    @patch(
        "rag.services.lecture_ingestion_service."
        "VectorStoreService.insert_chunks"
    )
    @patch(
        "rag.services.lecture_ingestion_service."
        "EmbeddingService.embed_texts"
    )
    def test_ingest_lecture_text_embeds_and_inserts_chunks(
        self,
        mock_embed_texts,
        mock_insert_chunks,
    ):
        original_chunk_size = LectureIngestionService.CHUNK_SIZE
        original_chunk_overlap = LectureIngestionService.CHUNK_OVERLAP

        LectureIngestionService.CHUNK_SIZE = 3
        LectureIngestionService.CHUNK_OVERLAP = 1

        try:
            mock_embed_texts.return_value = [
                [0.1, 0.2],
                [0.3, 0.4],
            ]

            result = LectureIngestionService.ingest_lecture_text(
                lecture_text="one two three four five",
                lecture_id="lecture-1",
                course_id="course-1",
                student_id="student-1",
            )

            mock_embed_texts.assert_called_once_with(
                [
                    "one two three",
                    "three four five",
                ]
            )

            inserted_chunks = mock_insert_chunks.call_args.args[0]

            self.assertEqual(len(inserted_chunks), 2)
            self.assertEqual(
                inserted_chunks[0]["chunk_text"],
                "one two three",
            )
            self.assertEqual(
                inserted_chunks[1]["chunk_text"],
                "three four five",
            )
            self.assertEqual(
                inserted_chunks[0]["chunk_index"],
                0,
            )
            self.assertEqual(
                inserted_chunks[1]["chunk_index"],
                1,
            )

            self.assertEqual(result["chunks_inserted"], 2)
            self.assertEqual(result["lecture_id"], "lecture-1")
            self.assertEqual(result["course_id"], "course-1")
            self.assertEqual(result["student_id"], "student-1")
            self.assertEqual(result["source_type"], "lecture")
            self.assertEqual(len(result["chunk_ids"]), 2)

        finally:
            LectureIngestionService.CHUNK_SIZE = original_chunk_size
            LectureIngestionService.CHUNK_OVERLAP = original_chunk_overlap

    def test_empty_lecture_text_raises_value_error(self):
        with self.assertRaisesMessage(
            ValueError,
            "Lecture text cannot be empty.",
        ):
            LectureIngestionService.ingest_lecture_text(
                lecture_text="",
                lecture_id="lecture-1",
                course_id="course-1",
                student_id="student-1",
            )


class VectorStoreServiceTests(SimpleTestCase):
    def setUp(self):
        VectorStoreService._collection = None
        VectorStoreService._initialized = False

    def tearDown(self):
        VectorStoreService._collection = None
        VectorStoreService._initialized = False

    @patch.object(VectorStoreService, "_ensure_index")
    @patch.object(VectorStoreService, "_ensure_collection")
    @patch.object(VectorStoreService, "_connect")
    def test_get_collection_initializes_once_and_reuses_collection(
        self,
        mock_connect,
        mock_ensure_collection,
        mock_ensure_index,
    ):
        mock_collection = MagicMock()
        mock_ensure_collection.return_value = mock_collection

        first_collection = VectorStoreService.get_collection()
        second_collection = VectorStoreService.get_collection()

        self.assertIs(first_collection, mock_collection)
        self.assertIs(second_collection, mock_collection)

        mock_connect.assert_called_once()
        mock_ensure_collection.assert_called_once()
        mock_ensure_index.assert_called_once_with(mock_collection)
        mock_collection.load.assert_called_once()


class InternalRAGAPITests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.valid_key = "test-internal-key"
        self.headers = {
            "HTTP_X_INTERNAL_SERVICE_KEY": self.valid_key,
        }

    @override_settings(RAG_INTERNAL_API_KEY="test-internal-key")
    def test_retrieve_rejects_missing_internal_key(self):
        response = self.client.post(
            reverse("rag-retrieve"),
            {
                "student_id": "student-1",
                "query": "What is RAG?",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    @override_settings(RAG_INTERNAL_API_KEY="test-internal-key")
    def test_retrieve_rejects_invalid_internal_key(self):
        response = self.client.post(
            reverse("rag-retrieve"),
            {
                "student_id": "student-1",
                "query": "What is RAG?",
            },
            format="json",
            HTTP_X_INTERNAL_SERVICE_KEY="wrong-key",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    @override_settings(RAG_INTERNAL_API_KEY="test-internal-key")
    @patch("rag.views.RAGService.retrieve_context")
    def test_retrieve_accepts_valid_internal_key(
        self,
        mock_retrieve_context,
    ):
        mock_retrieve_context.return_value = {
            "chunks": [],
            "context_text": "",
            "sources": [],
        }

        response = self.client.post(
            reverse("rag-retrieve"),
            {
                "student_id": "student-1",
                "query": "What is RAG?",
                "course_id": "course-1",
                "lecture_id": "lecture-1",
                "top_k": 5,
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        mock_retrieve_context.assert_called_once_with(
            student_id="student-1",
            query="What is RAG?",
            course_id="course-1",
            lecture_id="lecture-1",
            top_k=5,
        )

    @override_settings(RAG_INTERNAL_API_KEY="test-internal-key")
    @patch("rag.views.LectureIngestionService.ingest_lecture_text")
    def test_ingest_accepts_valid_internal_key(
        self,
        mock_ingest_lecture_text,
    ):
        mock_ingest_lecture_text.return_value = {
            "lecture_id": "lecture-1",
            "course_id": "course-1",
            "student_id": "student-1",
            "source_type": "lecture",
            "chunks_inserted": 1,
            "chunk_ids": ["chunk-1"],
        }

        response = self.client.post(
            reverse("rag-ingest"),
            {
                "lecture_text": "Lecture content",
                "lecture_id": "lecture-1",
                "course_id": "course-1",
                "student_id": "student-1",
                "source_type": "lecture",
            },
            format="json",
            **self.headers,
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        mock_ingest_lecture_text.assert_called_once_with(
            lecture_text="Lecture content",
            lecture_id="lecture-1",
            course_id="course-1",
            student_id="student-1",
            source_type="lecture",
        )

    def test_health_remains_public(self):
        response = self.client.get(reverse("rag-health"))

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )
