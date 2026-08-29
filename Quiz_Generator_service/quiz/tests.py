import uuid

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Quiz, QuizAttempt


class LearningProgressAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("learning_progress")

        self.student_id = uuid.uuid4()
        self.lecture_id = uuid.uuid4()
        self.course_id = uuid.uuid4()

        self.quiz_1 = Quiz.objects.create(
            lecture_id=self.lecture_id,
            course_id=self.course_id,
            student_id=self.student_id,
            title="Quiz 1",
            source="EXISTING",
            status="READY",
            num_questions=5,
            difficulty=3,
        )

        self.quiz_2 = Quiz.objects.create(
            lecture_id=self.lecture_id,
            course_id=self.course_id,
            student_id=self.student_id,
            title="Quiz 2",
            source="EXISTING",
            status="READY",
            num_questions=5,
            difficulty=4,
        )

        QuizAttempt.objects.create(
            quiz=self.quiz_1,
            student_id=self.student_id,
            score=5,
            total=5,
        )

        QuizAttempt.objects.create(
            quiz=self.quiz_2,
            student_id=self.student_id,
            score=3,
            total=5,
        )

    def test_missing_student_id_header(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "X-Student-ID header is missing",
        )

    def test_invalid_student_id_header(self):
        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID="abc",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "X-Student-ID must be a valid UUID",
        )

    def test_student_with_no_attempts_returns_empty_progress(self):
        empty_student_id = uuid.uuid4()

        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID=str(empty_student_id),
        )

        self.assertEqual(response.status_code, 200)

        overview = response.data["data"]["overview"]

        self.assertEqual(overview["total_attempts"], 0)
        self.assertEqual(overview["unique_quizzes_completed"], 0)
        self.assertEqual(overview["average_score"], 0.0)
        self.assertEqual(response.data["data"]["score_trend"], [])

    def test_student_progress_is_calculated_correctly(self):
        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)

        data = response.data["data"]
        overview = data["overview"]

        self.assertEqual(overview["total_attempts"], 2)
        self.assertEqual(overview["unique_quizzes_completed"], 2)

        # Quiz scores: 5/5 = 100%, 3/5 = 60%
        self.assertEqual(overview["average_score"], 80.0)
        self.assertEqual(overview["best_score"], 100.0)
        self.assertEqual(overview["latest_score"], 60.0)

        self.assertEqual(overview["total_questions"], 10)
        self.assertEqual(overview["correct_answers"], 8)
        self.assertEqual(overview["accuracy"], 80.0)

        self.assertEqual(len(data["score_trend"]), 2)
        self.assertEqual(len(data["difficulty_progression"]), 2)

        self.assertEqual(
            data["difficulty_progression"][0]["difficulty"],
            3,
        )
        self.assertEqual(
            data["difficulty_progression"][1]["difficulty"],
            4,
        )

        self.assertEqual(len(data["lecture_performance"]), 1)

        lecture_progress = data["lecture_performance"][0]

        self.assertEqual(lecture_progress["attempts"], 2)
        self.assertEqual(
            lecture_progress["average_score"],
            80.0,
        )
