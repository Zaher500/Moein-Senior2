import tempfile
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from Course.services.rag_client import (
    RAGClientError,
    send_for_rag_ingestion,
)
from Course.views import upload_lecture


class RAGClientTests(SimpleTestCase):
    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_INGESTION_TIMEOUT=60,
    )
    @patch("Course.services.rag_client.requests.post")
    def test_send_for_rag_ingestion_sends_expected_request(self, mock_post):
        response = MagicMock()
        mock_post.return_value = response

        send_for_rag_ingestion(
            lecture_id="lecture-1",
            course_id="course-1",
            student_id="student-1",
            text="Lecture content",
            source_type="lecture",
        )

        mock_post.assert_called_once_with(
            "http://rag-service:8005/api/rag/ingest/",
            json={
                "lecture_text": "Lecture content",
                "lecture_id": "lecture-1",
                "course_id": "course-1",
                "student_id": "student-1",
                "source_type": "lecture",
            },
            headers={
                "X-Internal-Service-Key": "test-key",
            },
            timeout=60,
        )

        response.raise_for_status.assert_called_once_with()

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY=None,
        RAG_INGESTION_TIMEOUT=60,
    )
    def test_send_for_rag_ingestion_rejects_missing_internal_key(self):
        with self.assertRaises(RAGClientError):
            send_for_rag_ingestion(
                lecture_id="lecture-1",
                course_id="course-1",
                student_id="student-1",
                text="Lecture content",
            )

    @override_settings(
        RAG_SERVICE_URL="http://rag-service:8005",
        RAG_INTERNAL_API_KEY="test-key",
        RAG_INGESTION_TIMEOUT=60,
    )
    @patch("Course.services.rag_client.requests.post")
    def test_send_for_rag_ingestion_wraps_request_failure(self, mock_post):
        import requests

        mock_post.side_effect = requests.RequestException(
            "connection failed"
        )

        with self.assertRaises(RAGClientError):
            send_for_rag_ingestion(
                lecture_id="lecture-1",
                course_id="course-1",
                student_id="student-1",
                text="Lecture content",
            )

class UploadLectureRAGRegressionTests(SimpleTestCase):
    @patch("Course.views.LectureSerializer")
    @patch("Course.views.send_for_summarization")
    @patch("Course.views.send_for_rag_ingestion")
    @patch("Course.views.extract_text_from_file")
    @patch("Course.views.Lecture.objects.create")
    @patch("Course.views.Course.objects.get")
    @patch("Course.views.get_student_id_from_token")
    def test_upload_lecture_dispatches_extracted_text_to_rag(
        self,
        mock_get_student_id,
        mock_get_course,
        mock_create_lecture,
        mock_extract_text,
        mock_send_for_rag_ingestion,
        mock_send_for_summarization,
        mock_lecture_serializer,
    ):
        factory = APIRequestFactory()

        student_id = "student-1"
        course_id = "course-1"

        course = MagicMock()
        course.course_id = course_id

        lecture = MagicMock()
        lecture.lecture_id = "lecture-1"

        mock_get_student_id.return_value = student_id
        mock_get_course.return_value = course
        mock_create_lecture.return_value = lecture
        mock_extract_text.return_value = "Extracted lecture text"

        mock_lecture_serializer.return_value.data = {
            "lecture_id": "lecture-1",
            "lecture_name": "Lecture 1",
        }

        uploaded_file = SimpleUploadedFile(
            "lecture.pdf",
            b"fake pdf content",
            content_type="application/pdf",
        )

        request = factory.post(
            "/api/courses/course-1/lectures/upload/",
            {
                "lecture_name": "Lecture 1",
                "file": uploaded_file,
            },
            format="multipart",
        )

        class ImmediateThread:
            def __init__(self, target, daemon=True):
                self.target = target

            def start(self):
                self.target()

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                with patch(
                    "Course.views.threading.Thread",
                    ImmediateThread,
                ):
                    response = upload_lecture(
                        request,
                        course_id=course_id,
                    )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        mock_send_for_rag_ingestion.assert_called_once_with(
            lecture_id="lecture-1",
            course_id="course-1",
            student_id="student-1",
            text="Extracted lecture text",
            source_type="lecture",
        )

        mock_extract_text.assert_called_once()

        mock_send_for_summarization.assert_called_once()
