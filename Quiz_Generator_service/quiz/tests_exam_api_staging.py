import uuid
from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from quiz.models import Quiz
from quiz.views import generate_exam_view


class ExamAPIStagingTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.student_id = str(uuid.uuid4())
        self.course_id = str(uuid.uuid4())
        self.lecture_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ]

        self.lectures = [
            {
                "lecture_id": lecture_id,
                "course_id": self.course_id,
                "student_id": self.student_id,
                "file_exists": True,
            }
            for lecture_id in self.lecture_ids
        ]

    @patch(
        "quiz.services.exam_course_loader.stage_course_lecture_file"
    )
    @patch("quiz.views.publish_quiz_job")
    @patch("quiz.views.fetch_course_lectures")
    def test_staging_completes_before_publish(
        self,
        mock_fetch,
        mock_publish,
        mock_stage,
    ):
        mock_fetch.return_value = self.lectures

        operations = Mock()
        operations.attach_mock(mock_stage, "stage")
        operations.attach_mock(mock_publish, "publish")

        request = self.factory.post(
            "/api/quiz/generate/exam/",
            {
                "course_id": self.course_id,
                "selection_mode": "selected",
                "lecture_ids": self.lecture_ids,
                "num_questions": 6,
                "question_mode": "mixed",
            },
            format="json",
            HTTP_X_STUDENT_ID=self.student_id,
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        response = generate_exam_view(request)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(mock_stage.call_count, 2)
        mock_publish.assert_called_once()

        operation_names = [
            call[0] for call in operations.mock_calls
        ]

        self.assertEqual(
            operation_names,
            ["stage", "stage", "publish"],
        )

        quiz = Quiz.objects.get(
            quiz_id=response.data["data"]["quiz_id"]
        )

        self.assertEqual(quiz.status, "PENDING")
        self.assertEqual(quiz.source, "EXAM")

    @patch("quiz.services.exam_staging.cleanup_exam_staging")
    @patch("quiz.services.exam_course_loader.stage_course_lecture_file")
    @patch("quiz.views.publish_quiz_job")
    @patch("quiz.views.fetch_course_lectures")
    def test_second_lecture_failure_cleans_up(
        self,
        mock_fetch,
        mock_publish,
        mock_stage,
        mock_cleanup,
    ):
        mock_fetch.return_value = self.lectures

        mock_stage.side_effect = [
            None,
            RuntimeError("Download failed"),
        ]

        request = self.factory.post(
            "/api/quiz/generate/exam/",
            {
                "course_id": self.course_id,
                "selection_mode": "selected",
                "lecture_ids": self.lecture_ids,
                "num_questions": 6,
            },
            format="json",
            HTTP_X_STUDENT_ID=self.student_id,
        )

        response = generate_exam_view(request)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(mock_stage.call_count, 2)
        mock_publish.assert_not_called()

        quiz = Quiz.objects.get()

        self.assertEqual(quiz.status, "FAILED")
        self.assertEqual(
            quiz.error,
            "Failed to prepare exam lecture files",
        )

        mock_cleanup.assert_called_once_with(quiz.quiz_id)

    @patch("quiz.services.exam_staging.cleanup_exam_staging")
    @patch("quiz.services.exam_course_loader.stage_course_lecture_file")
    @patch("quiz.views.publish_quiz_job")
    @patch("quiz.views.fetch_course_lectures")
    def test_publish_failure_cleans_staging(
        self,
        mock_fetch,
        mock_publish,
        mock_stage,
        mock_cleanup,
    ):
        mock_fetch.return_value = self.lectures
        mock_publish.side_effect = RuntimeError(
            "RabbitMQ unavailable"
        )

        request = self.factory.post(
            "/api/quiz/generate/exam/",
            {
                "course_id": self.course_id,
                "selection_mode": "selected",
                "lecture_ids": self.lecture_ids,
                "num_questions": 6,
            },
            format="json",
            HTTP_X_STUDENT_ID=self.student_id,
        )

        response = generate_exam_view(request)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(mock_stage.call_count, 2)
        mock_publish.assert_called_once()

        quiz = Quiz.objects.get()

        self.assertEqual(quiz.source, "EXAM")
        self.assertEqual(quiz.status, "FAILED")

        mock_cleanup.assert_called_once_with(quiz.quiz_id)

        self.assertEqual(
            quiz.error,
            "Failed to publish exam generation job",
        )
