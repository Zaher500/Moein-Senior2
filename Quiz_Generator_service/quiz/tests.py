import json
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Answer, Quiz, Question, QuizAttempt
from .services.error_analysis_service import get_student_error_analysis
from .services.quiz_generator import generate_quiz


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

        first_submitted_at = timezone.now() - timedelta(minutes=10)
        second_submitted_at = timezone.now()

        QuizAttempt.objects.create(
            quiz=self.quiz_1,
            student_id=self.student_id,
            status="SUBMITTED",
            score=5,
            total=5,
            submitted_at=first_submitted_at,
        )

        QuizAttempt.objects.create(
            quiz=self.quiz_2,
            student_id=self.student_id,
            status="SUBMITTED",
            score=3,
            total=5,
            submitted_at=second_submitted_at,
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

    def test_in_progress_attempt_is_excluded_from_progress(self):
        QuizAttempt.objects.create(
            quiz=self.quiz_1,
            student_id=self.student_id,
            status="IN_PROGRESS",
            score=0,
            total=5,
        )

        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)

        overview = response.data["data"]["overview"]

        self.assertEqual(overview["total_attempts"], 2)
        self.assertEqual(
            overview["unique_quizzes_completed"],
            2,
        )
        self.assertEqual(
            overview["average_score"],
            80.0,
        )


class QuizAttemptStartAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.student_id = uuid.uuid4()

        self.quiz = Quiz.objects.create(
            student_id=self.student_id,
            title="Resume Quiz",
            source="EXISTING",
            status="READY",
            num_questions=2,
            difficulty=3,
        )

        Question.objects.create(
            quiz=self.quiz,
            question_type="TRUE_FALSE",
            question_text="Question 1",
            correct_answer="True",
            explanation="Explanation 1",
            order=1,
        )

        Question.objects.create(
            quiz=self.quiz,
            question_type="TRUE_FALSE",
            question_text="Question 2",
            correct_answer="False",
            explanation="Explanation 2",
            order=2,
        )

        self.url = reverse(
            "quiz_attempt_start",
            kwargs={
                "quiz_id": self.quiz.quiz_id,
            },
        )

    def test_missing_student_id_header(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "X-Student-ID header is missing",
        )

    def test_invalid_student_id_header(self):
        response = self.client.post(
            self.url,
            HTTP_X_STUDENT_ID="invalid-uuid",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "X-Student-ID must be a valid UUID",
        )

    def test_start_creates_in_progress_attempt(self):
        response = self.client.post(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])

        data = response.data["data"]

        self.assertEqual(
            data["status"],
            "IN_PROGRESS",
        )
        self.assertEqual(
            data["answered_questions"],
            0,
        )
        self.assertEqual(
            data["total_questions"],
            2,
        )
        self.assertEqual(
            data["progress_percentage"],
            0.0,
        )
        self.assertEqual(
            data["answers"],
            [],
        )

        attempt = QuizAttempt.objects.get(attempt_id=data["attempt_id"])

        self.assertEqual(
            attempt.student_id,
            self.student_id,
        )
        self.assertEqual(
            attempt.status,
            "IN_PROGRESS",
        )
        self.assertIsNone(attempt.submitted_at)

    def test_second_start_resumes_existing_attempt(self):
        first_response = self.client.post(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        second_response = self.client.post(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(
            first_response.status_code,
            201,
        )
        self.assertEqual(
            second_response.status_code,
            200,
        )

        self.assertEqual(
            first_response.data["data"]["attempt_id"],
            second_response.data["data"]["attempt_id"],
        )

        self.assertEqual(
            QuizAttempt.objects.filter(
                quiz=self.quiz,
                student_id=self.student_id,
                status="IN_PROGRESS",
            ).count(),
            1,
        )

        self.assertEqual(
            second_response.data["message"],
            "Quiz attempt resumed successfully",
        )

    def test_quiz_must_be_ready(self):
        self.quiz.status = "PROCESSING"
        self.quiz.save(update_fields=["status"])

        response = self.client.post(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(
            response.status_code,
            400,
        )
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "Quiz is not ready to be attempted",
        )

    def test_resume_returns_saved_answers_and_progress(self):
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student_id=self.student_id,
            status="IN_PROGRESS",
            score=0,
            total=2,
        )

        question = self.quiz.questions.order_by("order").first()

        Answer.objects.create(
            attempt=attempt,
            question=question,
            selected_answer="True",
            is_correct=None,
        )

        response = self.client.post(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)

        data = response.data["data"]

        self.assertEqual(
            data["attempt_id"],
            str(attempt.attempt_id),
        )
        self.assertEqual(data["answered_questions"], 1)
        self.assertEqual(data["total_questions"], 2)
        self.assertEqual(data["progress_percentage"], 50.0)
        self.assertEqual(len(data["answers"]), 1)

        self.assertEqual(
            data["answers"][0]["question_id"],
            str(question.question_id),
        )
        self.assertEqual(
            data["answers"][0]["selected_answer"],
            "True",
        )

        self.assertNotIn(
            "is_correct",
            data["answers"][0],
        )
        self.assertNotIn(
            "correct_answer",
            data["answers"][0],
        )

class QuizAttemptAnswerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.student_id = uuid.uuid4()

        self.quiz = Quiz.objects.create(
            student_id=self.student_id,
            title="Autosave Quiz",
            source="EXISTING",
            status="READY",
            num_questions=2,
            difficulty=3,
        )

        self.question_1 = Question.objects.create(
            quiz=self.quiz,
            question_type="TRUE_FALSE",
            question_text="Question 1",
            correct_answer="True",
            explanation="Explanation 1",
            order=1,
        )

        self.question_2 = Question.objects.create(
            quiz=self.quiz,
            question_type="TRUE_FALSE",
            question_text="Question 2",
            correct_answer="False",
            explanation="Explanation 2",
            order=2,
        )

        self.attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student_id=self.student_id,
            status="IN_PROGRESS",
            score=0,
            total=2,
        )

        self.url = reverse(
            "quiz_attempt_answer",
            kwargs={
                "attempt_id": self.attempt.attempt_id,
            },
        )

    def test_save_answer_creates_answer_and_updates_progress(self):
        response = self.client.put(
            self.url,
            {
                "question_id": str(self.question_1.question_id),
                "selected_answer": "True",
            },
            format="json",
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])

        data = response.data["data"]

        self.assertEqual(data["answered_questions"], 1)
        self.assertEqual(data["total_questions"], 2)
        self.assertEqual(data["progress_percentage"], 50.0)

        answer = Answer.objects.get(
            attempt=self.attempt,
            question=self.question_1,
        )

        self.assertEqual(
            answer.selected_answer,
            "True",
        )
        self.assertIsNone(answer.is_correct)

    def test_saving_same_question_updates_existing_answer(self):
        self.client.put(
            self.url,
            {
                "question_id": str(self.question_1.question_id),
                "selected_answer": "True",
            },
            format="json",
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        response = self.client.put(
            self.url,
            {
                "question_id": str(self.question_1.question_id),
                "selected_answer": "False",
            },
            format="json",
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            Answer.objects.filter(
                attempt=self.attempt,
                question=self.question_1,
            ).count(),
            1,
        )

        answer = Answer.objects.get(
            attempt=self.attempt,
            question=self.question_1,
        )

        self.assertEqual(
            answer.selected_answer,
            "False",
        )

        self.assertEqual(
            response.data["data"]["answered_questions"],
            1,
        )
        self.assertEqual(
            response.data["data"]["progress_percentage"],
            50.0,
        )

    def test_answer_from_another_quiz_is_rejected(self):
        other_quiz = Quiz.objects.create(
            student_id=self.student_id,
            title="Other Quiz",
            source="EXISTING",
            status="READY",
            num_questions=1,
            difficulty=3,
        )

        other_question = Question.objects.create(
            quiz=other_quiz,
            question_type="TRUE_FALSE",
            question_text="Other Question",
            correct_answer="True",
            explanation="Other Explanation",
            order=1,
        )

        response = self.client.put(
            self.url,
            {
                "question_id": str(other_question.question_id),
                "selected_answer": "True",
            },
            format="json",
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "Question does not belong to this quiz attempt",
        )

    def test_submitted_attempt_cannot_be_updated(self):
        self.attempt.status = "SUBMITTED"
        self.attempt.save(
            update_fields=["status"]
        )

        response = self.client.put(
            self.url,
            {
                "question_id": str(self.question_1.question_id),
                "selected_answer": "True",
            },
            format="json",
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "Only in-progress attempts can be updated",
        )

    def test_student_cannot_update_another_students_attempt(self):
        other_student_id = uuid.uuid4()

        response = self.client.put(
            self.url,
            {
                "question_id": str(self.question_1.question_id),
                "selected_answer": "True",
            },
            format="json",
            HTTP_X_STUDENT_ID=str(other_student_id),
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "Quiz attempt not found",
        )

class QuizSubmitResumeAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student_id = uuid.uuid4()

        self.quiz = Quiz.objects.create(
            student_id=self.student_id,
            title="Submit Resume Quiz",
            source="EXISTING",
            status="READY",
            num_questions=2,
            difficulty=3,
        )

        self.question_1 = Question.objects.create(
            quiz=self.quiz,
            question_type="TRUE_FALSE",
            question_text="Question 1",
            correct_answer="True",
            explanation="Explanation 1",
            order=1,
        )

        self.question_2 = Question.objects.create(
            quiz=self.quiz,
            question_type="TRUE_FALSE",
            question_text="Question 2",
            correct_answer="False",
            explanation="Explanation 2",
            order=2,
        )

        self.url = reverse(
            "quiz_submit",
            kwargs={
                "quiz_id": self.quiz.quiz_id,
            },
        )

    def test_submit_uses_existing_in_progress_attempt(self):
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student_id=self.student_id,
            status="IN_PROGRESS",
            score=0,
            total=2,
        )

        Answer.objects.create(
            attempt=attempt,
            question=self.question_1,
            selected_answer="True",
            is_correct=None,
        )

        Answer.objects.create(
            attempt=attempt,
            question=self.question_2,
            selected_answer="True",
            is_correct=None,
        )

        response = self.client.post(
            self.url,
            {},
            format="json",
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])

        self.assertEqual(
            response.data["data"]["attempt_id"],
            str(attempt.attempt_id),
        )

        self.assertEqual(
            QuizAttempt.objects.filter(
                quiz=self.quiz,
                student_id=self.student_id,
            ).count(),
            1,
        )

        attempt.refresh_from_db()

        self.assertEqual(
            attempt.status,
            "SUBMITTED",
        )
        self.assertIsNotNone(
            attempt.submitted_at
        )
        self.assertEqual(
            attempt.score,
            1,
        )

        answer_1 = Answer.objects.get(
            attempt=attempt,
            question=self.question_1,
        )

        answer_2 = Answer.objects.get(
            attempt=attempt,
            question=self.question_2,
        )

        self.assertTrue(answer_1.is_correct)
        self.assertFalse(answer_2.is_correct)

        self.assertEqual(
            response.data["data"]["percentage"],
            50.0,
        )

    def test_legacy_submit_without_start_still_works(self):
        response = self.client.post(
            self.url,
            {
                "answers": [
                    {
                        "question_id": str(
                            self.question_1.question_id
                        ),
                        "selected_answer": "True",
                    },
                    {
                        "question_id": str(
                            self.question_2.question_id
                        ),
                        "selected_answer": "False",
                    },
                ]
            },
            format="json",
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])

        attempt = QuizAttempt.objects.get(
            attempt_id=response.data["data"]["attempt_id"]
        )

        self.assertEqual(
            attempt.status,
            "SUBMITTED",
        )
        self.assertIsNotNone(
            attempt.submitted_at
        )
        self.assertEqual(
            attempt.score,
            2,
        )

        self.assertEqual(
            attempt.answers.count(),
            2,
        )

        self.assertEqual(
            response.data["data"]["percentage"],
            100.0,
        )

    def test_in_progress_attempt_enters_progress_only_after_submit(self):
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student_id=self.student_id,
            status="IN_PROGRESS",
            score=0,
            total=2,
        )

        Answer.objects.create(
            attempt=attempt,
            question=self.question_1,
            selected_answer="True",
            is_correct=None,
        )

        progress_url = reverse(
            "learning_progress"
        )

        before_response = self.client.get(
            progress_url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(
            before_response.data["data"]["overview"]["total_attempts"],
            0,
        )

        submit_response = self.client.post(
            self.url,
            {},
            format="json",
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(
            submit_response.status_code,
            201,
        )

        after_response = self.client.get(
            progress_url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(
            after_response.data["data"]["overview"]["total_attempts"],
            1,
        )

class InProgressAttemptsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student_id = uuid.uuid4()

        self.quiz = Quiz.objects.create(
            student_id=self.student_id,
            title="Incomplete Quiz",
            source="EXISTING",
            status="READY",
            num_questions=2,
            difficulty=3,
        )

        self.question_1 = Question.objects.create(
            quiz=self.quiz,
            question_type="TRUE_FALSE",
            question_text="Question 1",
            correct_answer="True",
            explanation="Explanation 1",
            order=1,
        )

        self.question_2 = Question.objects.create(
            quiz=self.quiz,
            question_type="TRUE_FALSE",
            question_text="Question 2",
            correct_answer="False",
            explanation="Explanation 2",
            order=2,
        )

        self.url = reverse(
            "quiz_in_progress_attempts"
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
            HTTP_X_STUDENT_ID="invalid-uuid",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "X-Student-ID must be a valid UUID",
        )

    def test_no_in_progress_attempts_returns_empty_list(self):
        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(
            response.data["data"],
            [],
        )

    def test_returns_in_progress_attempt_with_progress(self):
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            student_id=self.student_id,
            status="IN_PROGRESS",
            score=0,
            total=2,
        )

        Answer.objects.create(
            attempt=attempt,
            question=self.question_1,
            selected_answer="True",
            is_correct=None,
        )

        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)

        data = response.data["data"]

        self.assertEqual(len(data), 1)

        item = data[0]

        self.assertEqual(
            item["attempt_id"],
            str(attempt.attempt_id),
        )
        self.assertEqual(
            item["quiz_id"],
            str(self.quiz.quiz_id),
        )
        self.assertEqual(
            item["title"],
            "Incomplete Quiz",
        )
        self.assertEqual(
            item["status"],
            "IN_PROGRESS",
        )
        self.assertEqual(
            item["answered_questions"],
            1,
        )
        self.assertEqual(
            item["total_questions"],
            2,
        )
        self.assertEqual(
            item["progress_percentage"],
            50.0,
        )

    def test_excludes_submitted_and_other_students_attempts(self):
        QuizAttempt.objects.create(
            quiz=self.quiz,
            student_id=self.student_id,
            status="SUBMITTED",
            score=2,
            total=2,
            submitted_at=timezone.now(),
        )

        other_student_id = uuid.uuid4()

        QuizAttempt.objects.create(
            quiz=self.quiz,
            student_id=other_student_id,
            status="IN_PROGRESS",
            score=0,
            total=2,
        )

        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["data"],
            [],
        )


class QuizAnswerVisibilityAPITests(TestCase):
    """Keep quiz answer keys private until final submission."""

    def setUp(self):
        self.client = APIClient()
        self.student_id = uuid.uuid4()
        self.lecture_id = uuid.uuid4()

        self.quiz = Quiz.objects.create(
            student_id=self.student_id,
            lecture_id=self.lecture_id,
            title="Answer Visibility Quiz",
            source="EXISTING",
            status="READY",
            num_questions=1,
            difficulty=3,
        )
        self.question = Question.objects.create(
            quiz=self.quiz,
            question_type="MCQ",
            question_text="Which option is correct?",
            options="A|B|C|D",
            correct_answer="B",
            explanation="B is correct according to the lecture.",
            order=1,
        )
        self.quiz_url = reverse(
            "quiz_detail", kwargs={"quiz_id": self.quiz.quiz_id}
        )
        self.lecture_url = reverse(
            "quiz_by_lecture", kwargs={"lecture_id": self.lecture_id}
        )
        self.start_url = reverse(
            "quiz_attempt_start", kwargs={"quiz_id": self.quiz.quiz_id}
        )
        self.submit_url = reverse(
            "quiz_submit", kwargs={"quiz_id": self.quiz.quiz_id}
        )
        self.headers = {"HTTP_X_STUDENT_ID": str(self.student_id)}

    def assert_student_question_safe(self, question_data):
        self.assertEqual(
            set(question_data.keys()),
            {"question_id", "question_type", "question_text", "options", "order"},
        )
        self.assertEqual(question_data["question_text"], "Which option is correct?")
        self.assertEqual(question_data["options"], ["A", "B", "C", "D"])
        self.assertNotIn("correct_answer", question_data)
        self.assertNotIn("explanation", question_data)

    def test_quiz_detail_does_not_expose_answers(self):
        response = self.client.get(self.quiz_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["difficulty"], 3)
        self.assertEqual(len(response.data["data"]["questions"]), 1)
        self.assert_student_question_safe(response.data["data"]["questions"][0])

    def test_quiz_by_lecture_does_not_expose_answers(self):
        response = self.client.get(self.lecture_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["data"]), 1)
        self.assert_student_question_safe(response.data["data"][0]["questions"][0])

    def test_autosave_and_resume_only_return_selected_answer(self):
        start = self.client.post(self.start_url, **self.headers)
        self.assertEqual(start.status_code, 201)
        attempt_id = start.data["data"]["attempt_id"]

        answer_url = reverse(
            "quiz_attempt_answer", kwargs={"attempt_id": attempt_id}
        )
        saved = self.client.put(
            answer_url,
            {
                "question_id": str(self.question.question_id),
                "selected_answer": "A",
            },
            format="json",
            **self.headers,
        )
        self.assertEqual(saved.status_code, 200)
        expected_answers = [
            {"question_id": str(self.question.question_id), "selected_answer": "A"}
        ]
        self.assertEqual(saved.data["data"]["answers"], expected_answers)

        resumed = self.client.post(self.start_url, **self.headers)
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.data["data"]["attempt_id"], attempt_id)
        self.assertEqual(resumed.data["data"]["answers"], expected_answers)
        self.assertEqual(resumed.data["data"]["progress_percentage"], 100.0)

    def test_submit_returns_correction_and_quiz_get_stays_safe(self):
        before_progress = self.client.get(
            reverse("learning_progress"), **self.headers
        )
        self.assertEqual(before_progress.status_code, 200)
        self.assertEqual(
            before_progress.data["data"]["overview"]["total_attempts"], 0
        )

        response = self.client.post(
            self.submit_url,
            {
                "answers": [
                    {
                        "question_id": str(self.question.question_id),
                        "selected_answer": "A",
                    }
                ]
            },
            format="json",
            **self.headers,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["percentage"], 0.0)

        result = response.data["data"]["results"][0]
        self.assertEqual(result["selected_answer"], "A")
        self.assertEqual(result["correct_answer"], "B")
        self.assertFalse(result["is_correct"])
        self.assertEqual(
            result["explanation"], "B is correct according to the lecture."
        )

        after_progress = self.client.get(
            reverse("learning_progress"), **self.headers
        )
        self.assertEqual(after_progress.status_code, 200)
        self.assertEqual(
            after_progress.data["data"]["overview"]["total_attempts"], 1
        )

        # General quiz retrieval remains safe even after one attempt is submitted.
        quiz_response = self.client.get(self.quiz_url)
        self.assertEqual(quiz_response.status_code, 200)
        self.assert_student_question_safe(
            quiz_response.data["data"]["questions"][0]
        )


class QuizTopicGenerationTests(TestCase):

    @patch("quiz.services.quiz_generator.call_hf_llm")
    def test_valid_topic_is_normalized(self, mock_llm):
        mock_llm.return_value = json.dumps([
            {
                "question_type": "TRUE_FALSE",
                "question_text": "Unit testing tests individual units.",
                "options": "",
                "correct_answer": "True",
                "explanation": "Unit testing focuses on individual units.",
                "topic": "  Unit   Testing  ",
            }
        ])

        raw_response, questions = generate_quiz(
            text="Unit testing tests individual units.",
            num_questions=1,
            question_mode="true_false",
            difficulty=3,
        )

        self.assertEqual(len(questions), 1)
        self.assertEqual(
            questions[0]["topic"],
            "Unit Testing"
        )
        self.assertEqual(
            questions[0]["correct_answer"],
            "True"
        )

        mock_llm.assert_called_once()

        prompt = mock_llm.call_args[0][0]
        self.assertIn("TOPIC CLASSIFICATION", prompt)

    @patch("quiz.services.quiz_generator.call_hf_llm")
    def test_invalid_or_missing_topic_becomes_none(self, mock_llm):
        invalid_topics = [
            {},
            {"topic": None},
            {"topic": 123},
            {"topic": "   "},
            {"topic": "General"},
            {"topic": "Unknown"},
            {"topic": "x" * 256},
        ]

        for topic_data in invalid_topics:
            with self.subTest(topic_data=topic_data):
                question = {
                    "question_type": "TRUE_FALSE",
                    "question_text": "Unit testing tests individual units.",
                    "options": "",
                    "correct_answer": "True",
                    "explanation": "Unit testing focuses on individual units.",
                    **topic_data,
                }

                mock_llm.return_value = json.dumps([question])

                _, questions = generate_quiz(
                    text="Unit testing tests individual units.",
                    num_questions=1,
                    question_mode="true_false",
                    difficulty=3,
                )

                self.assertEqual(len(questions), 1)
                self.assertIsNone(questions[0]["topic"])
                self.assertEqual(
                    questions[0]["correct_answer"],
                    "True",
                )


class QuizWorkerTopicPersistenceTests(TestCase):

    @patch(
        "quiz.management.commands.run_quiz_worker.store_llm_response"
    )
    @patch(
        "quiz.management.commands.run_quiz_worker.generate_quiz"
    )
    @patch(
        "quiz.management.commands.run_quiz_worker.pika.BlockingConnection"
    )
    def test_worker_saves_question_topic(
        self,
        mock_connection,
        mock_generate,
        mock_store,
    ):
        from quiz.management.commands.run_quiz_worker import Command

        student_id = uuid.uuid4()

        quiz = Quiz.objects.create(
            student_id=student_id,
            title="Worker Topic Test",
            source="EXISTING",
            status="PENDING",
            num_questions=1,
            difficulty=3,
        )

        mock_generate.return_value = (
            "mocked LLM response",
            [
                {
                    "question_type": "TRUE_FALSE",
                    "question_text": "Unit testing tests individual units.",
                    "options": "",
                    "correct_answer": "True",
                    "explanation": "Unit testing focuses on individual units.",
                    "topic": "Unit Testing",
                }
            ],
        )

        channel = mock_connection.return_value.channel.return_value

        Command().handle()

        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]

        payload = {
            "quiz_id": str(quiz.quiz_id),
            "student_id": str(student_id),
            "text": "Unit testing tests individual units.",
            "num_questions": 1,
            "question_mode": "true_false",
            "difficulty": 3,
        }

        method = SimpleNamespace(delivery_tag=123)

        callback(
            channel,
            method,
            None,
            json.dumps(payload).encode("utf-8"),
        )

        quiz.refresh_from_db()

        self.assertEqual(quiz.status, "READY")
        self.assertEqual(quiz.questions.count(), 1)

        question = Question.objects.get(quiz=quiz)

        self.assertEqual(question.topic, "Unit Testing")
        self.assertEqual(question.correct_answer, "True")

        mock_generate.assert_called_once()
        mock_store.assert_called_once()

        channel.basic_ack.assert_called_once_with(
            delivery_tag=123
        )


    @patch(
        "quiz.management.commands.run_quiz_worker.store_llm_response"
    )
    @patch(
        "quiz.management.commands.run_quiz_worker.generate_quiz"
    )
    @patch(
        "quiz.management.commands.run_quiz_worker.pika.BlockingConnection"
    )
    def test_duplicate_message_preserves_submitted_answers(
        self,
        mock_connection,
        mock_generate,
        mock_store,
    ):
        from quiz.management.commands.run_quiz_worker import Command

        student_id = uuid.uuid4()

        quiz = Quiz.objects.create(
            student_id=student_id,
            title="Completed Quiz",
            source="EXISTING",
            status="READY",
            num_questions=1,
            difficulty=3,
        )

        question = Question.objects.create(
            quiz=quiz,
            question_type="TRUE_FALSE",
            question_text="Original question",
            correct_answer="True",
            explanation="Original explanation",
            topic="Unit Testing",
            order=1,
        )

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_id=student_id,
            status="SUBMITTED",
            score=1,
            total=1,
            submitted_at=timezone.now(),
        )

        answer = Answer.objects.create(
            attempt=attempt,
            question=question,
            selected_answer="True",
            is_correct=True,
        )

        mock_generate.return_value = (
            "replacement response",
            [
                {
                    "question_type": "TRUE_FALSE",
                    "question_text": "Replacement question",
                    "options": "",
                    "correct_answer": "False",
                    "explanation": "Replacement explanation",
                    "topic": "Other Topic",
                }
            ],
        )

        channel = mock_connection.return_value.channel.return_value

        Command().handle()

        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]

        payload = {
            "quiz_id": str(quiz.quiz_id),
            "student_id": str(student_id),
            "text": "Duplicate generation request",
            "num_questions": 1,
            "question_mode": "true_false",
            "difficulty": 3,
        }

        method = SimpleNamespace(delivery_tag=456)

        callback(
            channel,
            method,
            None,
            json.dumps(payload).encode("utf-8"),
        )

        quiz.refresh_from_db()

        self.assertEqual(quiz.status, "READY")
        self.assertTrue(
            Question.objects.filter(pk=question.pk).exists()
        )
        self.assertTrue(
            Answer.objects.filter(pk=answer.pk).exists()
        )
        self.assertEqual(
            Answer.objects.get(pk=answer.pk).question_id,
            question.question_id,
        )

        mock_generate.assert_not_called()
        mock_store.assert_not_called()

        channel.basic_ack.assert_called_once_with(
            delivery_tag=456
        )


    @patch("quiz.management.commands.run_quiz_worker.store_llm_response")
    @patch("quiz.management.commands.run_quiz_worker.generate_quiz")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_pending_quiz_with_attempt_preserves_saved_answers(
        self, mock_connection, mock_generate, mock_store
    ):
        from quiz.management.commands.run_quiz_worker import Command

        student_id = uuid.uuid4()

        quiz = Quiz.objects.create(
            student_id=student_id,
            title="Protected Quiz",
            source="EXISTING",
            status="READY",
            num_questions=1,
            difficulty=3,
        )

        question = Question.objects.create(
            quiz=quiz,
            question_type="TRUE_FALSE",
            question_text="Original question",
            correct_answer="True",
            explanation="Original explanation",
            topic="Unit Testing",
            order=1,
        )

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_id=student_id,
            status="IN_PROGRESS",
            total=1,
        )

        answer = Answer.objects.create(
            attempt=attempt,
            question=question,
            selected_answer="True",
            is_correct=None,
        )

        # Simulate an unexpected status reset.
        Quiz.objects.filter(pk=quiz.pk).update(status="PENDING")

        # A valid LLM response ensures an unprotected worker would proceed
        # to delete the original question and its saved answer.
        mock_generate.return_value = (
            "replacement response",
            [
                {
                    "question_type": "TRUE_FALSE",
                    "question_text": "Replacement question",
                    "options": "",
                    "correct_answer": "False",
                    "explanation": "Replacement explanation",
                    "topic": "Other Topic",
                }
            ],
        )

        channel = mock_connection.return_value.channel.return_value

        Command().handle()

        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]

        payload = {
            "quiz_id": str(quiz.quiz_id),
            "student_id": str(student_id),
            "text": "Regeneration request",
            "num_questions": 1,
            "question_mode": "true_false",
            "difficulty": 3,
        }

        callback(
            channel,
            SimpleNamespace(delivery_tag=789),
            None,
            json.dumps(payload).encode("utf-8"),
        )

        quiz.refresh_from_db()

        self.assertEqual(quiz.status, "PENDING")
        self.assertTrue(
            Question.objects.filter(pk=question.pk).exists()
        )
        self.assertTrue(
            Answer.objects.filter(pk=answer.pk).exists()
        )

        mock_generate.assert_not_called()
        mock_store.assert_not_called()
        channel.basic_ack.assert_called_once_with(delivery_tag=789)


    @patch("quiz.management.commands.run_quiz_worker.store_llm_response")
    @patch("quiz.management.commands.run_quiz_worker.generate_quiz")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_attempt_started_during_generation_prevents_deletion(
        self, mock_connection, mock_generate, mock_store
    ):
        from quiz.management.commands.run_quiz_worker import Command

        student_id = uuid.uuid4()
        quiz = Quiz.objects.create(
            student_id=student_id,
            title="In-flight Attempt Protection",
            source="EXISTING",
            status="PENDING",
            num_questions=1,
            difficulty=3,
        )
        original_question = Question.objects.create(
            quiz=quiz,
            question_type="TRUE_FALSE",
            question_text="Original question",
            correct_answer="True",
            explanation="Original explanation",
            topic="Unit Testing",
            order=1,
        )

        saved = {}

        def generation_with_new_attempt(**kwargs):
            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                student_id=student_id,
                status="IN_PROGRESS",
                total=1,
            )
            saved["answer"] = Answer.objects.create(
                attempt=attempt,
                question=original_question,
                selected_answer="True",
                is_correct=None,
            )
            return (
                "replacement response",
                [
                    {
                        "question_type": "TRUE_FALSE",
                        "question_text": "Replacement question",
                        "options": "",
                        "correct_answer": "False",
                        "explanation": "Replacement explanation",
                        "topic": "Other Topic",
                    }
                ],
            )

        mock_generate.side_effect = generation_with_new_attempt
        channel = mock_connection.return_value.channel.return_value
        Command().handle()
        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]
        callback(
            channel,
            SimpleNamespace(delivery_tag=790),
            None,
            json.dumps(
                {
                    "quiz_id": str(quiz.quiz_id),
                    "student_id": str(student_id),
                    "text": "Regeneration request",
                    "num_questions": 1,
                    "question_mode": "true_false",
                    "difficulty": 3,
                }
            ).encode("utf-8"),
        )

        quiz.refresh_from_db()
        # Existing questions and saved attempts must remain resumable.
        self.assertEqual(quiz.status, "READY")
        self.assertIsNone(quiz.error)
        self.assertTrue(
            Question.objects.filter(pk=original_question.pk).exists()
        )
        self.assertTrue(
            Answer.objects.filter(pk=saved["answer"].pk).exists()
        )
        mock_generate.assert_called_once()
        mock_store.assert_not_called()
        channel.basic_ack.assert_called_once_with(delivery_tag=790)


    @patch(
        "quiz.management.commands.run_quiz_worker.Exists",
        side_effect=RuntimeError("Simulated claim failure"),
    )
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_claim_failure_does_not_change_existing_quiz_status(
        self, mock_connection, mock_exists
    ):
        from quiz.management.commands.run_quiz_worker import Command

        quiz = Quiz.objects.create(
            student_id=uuid.uuid4(),
            title="Claim Failure Test",
            source="EXISTING",
            status="READY",
            num_questions=1,
            difficulty=3,
        )

        channel = mock_connection.return_value.channel.return_value
        Command().handle()
        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]
        callback(
            channel,
            SimpleNamespace(delivery_tag=791),
            None,
            json.dumps({
                "quiz_id": str(quiz.quiz_id),
                "student_id": str(quiz.student_id),
                "text": "A duplicate request",
                "num_questions": 1,
                "difficulty": 3,
            }).encode("utf-8"),
        )

        quiz.refresh_from_db()
        self.assertEqual(quiz.status, "READY")
        self.assertIsNone(quiz.error)
        mock_exists.assert_called_once()
        channel.basic_ack.assert_called_once_with(delivery_tag=791)


class QuizErrorAnalysisServiceTests(TestCase):

    def test_error_analysis_counts_answers_correctly(self):
        student_id = uuid.uuid4()

        quiz = Quiz.objects.create(
            student_id=student_id,
            title="Error Analysis Test",
            source="EXISTING",
            status="READY",
            num_questions=4,
            difficulty=3,
        )

        questions = []

        for i in range(1, 5):
            question = Question.objects.create(
                quiz=quiz,
                question_type="TRUE_FALSE",
                question_text=f"Question {i}",
                correct_answer="True",
                explanation="Test explanation",
                topic="Unit Testing" if i <= 3 else None,
                order=i,
            )
            questions.append(question)

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_id=student_id,
            status="SUBMITTED",
            score=1,
            total=4,
            submitted_at=timezone.now(),
        )

        Answer.objects.create(
            attempt=attempt,
            question=questions[0],
            selected_answer="True",
            is_correct=True,
        )

        Answer.objects.create(
            attempt=attempt,
            question=questions[1],
            selected_answer="False",
            is_correct=False,
        )

        # Question 3 and Question 4 are unanswered.

        result = get_student_error_analysis(student_id)

        overview = result["overview"]

        self.assertEqual(
            overview["total_analyzed_attempts"], 1
        )
        self.assertEqual(overview["total_questions"], 4)
        self.assertEqual(overview["correct_answers"], 1)
        self.assertEqual(overview["incorrect_answers"], 1)
        self.assertEqual(overview["unanswered_questions"], 2)
        self.assertEqual(overview["unclassified_questions"], 1)

        self.assertEqual(len(result["topic_performance"]), 1)

        topic = result["topic_performance"][0]

        self.assertEqual(topic["topic"], "Unit Testing")
        self.assertEqual(topic["total_questions"], 3)
        self.assertEqual(topic["correct_answers"], 1)
        self.assertEqual(topic["incorrect_answers"], 1)
        self.assertEqual(topic["unanswered_questions"], 1)

        self.assertEqual(topic["accuracy"], 33.33)
        self.assertEqual(topic["error_rate"], 66.67)
        self.assertEqual(topic["priority"], "HIGH")

        self.assertEqual(len(result["review_topics"]), 1)

    def test_excludes_in_progress_and_other_students(self):
        student_id = uuid.uuid4()
        other_student_id = uuid.uuid4()

        quiz = Quiz.objects.create(
            student_id=student_id,
            title="Student Quiz",
            source="EXISTING",
            status="READY",
            num_questions=1,
            difficulty=3,
        )

        question = Question.objects.create(
            quiz=quiz,
            question_type="TRUE_FALSE",
            question_text="Question 1",
            correct_answer="True",
            explanation="Explanation",
            topic="Unit Testing",
            order=1,
        )

        submitted = QuizAttempt.objects.create(
            quiz=quiz,
            student_id=student_id,
            status="SUBMITTED",
            score=0,
            total=1,
            submitted_at=timezone.now(),
        )

        Answer.objects.create(
            attempt=submitted,
            question=question,
            selected_answer="False",
            is_correct=False,
        )

        in_progress = QuizAttempt.objects.create(
            quiz=quiz,
            student_id=student_id,
            status="IN_PROGRESS",
            total=1,
        )

        Answer.objects.create(
            attempt=in_progress,
            question=question,
            selected_answer="True",
            is_correct=None,
        )

        other_quiz = Quiz.objects.create(
            student_id=other_student_id,
            title="Other Student Quiz",
            source="EXISTING",
            status="READY",
            num_questions=1,
            difficulty=3,
        )

        other_question = Question.objects.create(
            quiz=other_quiz,
            question_type="TRUE_FALSE",
            question_text="Question 2",
            correct_answer="True",
            explanation="Explanation",
            topic="Database Indexing",
            order=1,
        )

        other_attempt = QuizAttempt.objects.create(
            quiz=other_quiz,
            student_id=other_student_id,
            status="SUBMITTED",
            score=0,
            total=1,
            submitted_at=timezone.now(),
        )

        Answer.objects.create(
            attempt=other_attempt,
            question=other_question,
            selected_answer="False",
            is_correct=False,
        )

        result = get_student_error_analysis(student_id)
        overview = result["overview"]

        self.assertEqual(overview["total_analyzed_attempts"], 1)
        self.assertEqual(overview["total_questions"], 1)
        self.assertEqual(overview["incorrect_answers"], 1)
        self.assertEqual(overview["ungraded_answers"], 0)

        self.assertEqual(len(result["topic_performance"]), 1)
        self.assertEqual(
            result["topic_performance"][0]["topic"],
            "Unit Testing",
        )

    def test_same_topic_is_separated_by_course(self):
        student_id = uuid.uuid4()
        weak_course_id = uuid.uuid4()
        strong_course_id = uuid.uuid4()

        for course_id, is_correct in (
            (weak_course_id, False),
            (strong_course_id, True),
        ):
            quiz = Quiz.objects.create(
                student_id=student_id,
                course_id=course_id,
                title="Course Topic Isolation Quiz",
                source="EXISTING",
                status="READY",
                num_questions=3,
                difficulty=3,
            )

            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                student_id=student_id,
                status="SUBMITTED",
                score=3 if is_correct else 0,
                total=3,
                submitted_at=timezone.now(),
            )

            for index in range(1, 4):
                question = Question.objects.create(
                    quiz=quiz,
                    question_type="TRUE_FALSE",
                    question_text=f"Question {index}",
                    correct_answer="True",
                    explanation="Explanation",
                    topic="Unit Testing",
                    order=index,
                )
                Answer.objects.create(
                    attempt=attempt,
                    question=question,
                    selected_answer="True" if is_correct else "False",
                    is_correct=is_correct,
                )

        result = get_student_error_analysis(student_id)
        overview = result["overview"]

        self.assertEqual(overview["total_analyzed_attempts"], 2)
        self.assertEqual(overview["total_questions"], 6)
        self.assertEqual(overview["correct_answers"], 3)
        self.assertEqual(overview["incorrect_answers"], 3)

        self.assertEqual(len(result["topic_performance"]), 2)
        by_course = {
            stats["scope_id"]: stats
            for stats in result["topic_performance"]
        }
        self.assertEqual(
            set(by_course),
            {str(weak_course_id), str(strong_course_id)},
        )

        weak_topic = by_course[str(weak_course_id)]
        strong_topic = by_course[str(strong_course_id)]

        self.assertEqual(weak_topic["scope_type"], "course")
        self.assertEqual(strong_topic["scope_type"], "course")
        self.assertEqual(weak_topic["topic"], "Unit Testing")
        self.assertEqual(strong_topic["topic"], "Unit Testing")

        self.assertEqual(weak_topic["total_questions"], 3)
        self.assertEqual(weak_topic["error_rate"], 100.0)
        self.assertEqual(weak_topic["priority"], "HIGH")

        self.assertEqual(strong_topic["total_questions"], 3)
        self.assertEqual(strong_topic["error_rate"], 0.0)
        self.assertEqual(strong_topic["priority"], "LOW")

        self.assertEqual(len(result["review_topics"]), 1)
        self.assertEqual(
            result["review_topics"][0]["scope_id"],
            str(weak_course_id),
        )

    def test_aggregates_topic_across_multiple_quizzes(self):
        student_id = uuid.uuid4()
        course_id = uuid.uuid4()

        test_cases = [
            ("  Unit   Testing  ", [True, False]),
            ("unit testing", [False, None]),
        ]

        for quiz_index, (topic, outcomes) in enumerate(
            test_cases, start=1
        ):
            quiz = Quiz.objects.create(
                student_id=student_id,
                course_id=course_id,
                title=f"Quiz {quiz_index}",
                source="EXISTING",
                status="READY",
                num_questions=2,
                difficulty=3,
            )

            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                student_id=student_id,
                status="SUBMITTED",
                score=sum(value is True for value in outcomes),
                total=2,
                submitted_at=timezone.now(),
            )

            for index, outcome in enumerate(outcomes, start=1):
                question = Question.objects.create(
                    quiz=quiz,
                    question_type="TRUE_FALSE",
                    question_text=f"Question {index}",
                    correct_answer="True",
                    explanation="Explanation",
                    topic=topic,
                    order=index,
                )

                if outcome is not None:
                    Answer.objects.create(
                        attempt=attempt,
                        question=question,
                        selected_answer=(
                            "True" if outcome else "False"
                        ),
                        is_correct=outcome,
                    )

        result = get_student_error_analysis(student_id)

        self.assertEqual(
            result["overview"]["total_analyzed_attempts"], 2
        )
        self.assertEqual(len(result["topic_performance"]), 1)

        topic_stats = result["topic_performance"][0]

        self.assertEqual(topic_stats["topic"], "Unit Testing")
        self.assertEqual(topic_stats["scope_type"], "course")
        self.assertEqual(topic_stats["scope_id"], str(course_id))
        self.assertEqual(topic_stats["total_questions"], 4)
        self.assertEqual(topic_stats["correct_answers"], 1)
        self.assertEqual(topic_stats["incorrect_answers"], 2)
        self.assertEqual(topic_stats["unanswered_questions"], 1)
        self.assertEqual(topic_stats["accuracy"], 25.0)
        self.assertEqual(topic_stats["error_rate"], 75.0)
        self.assertEqual(topic_stats["priority"], "HIGH")
        self.assertEqual(len(result["review_topics"]), 1)

    def test_insufficient_data_and_ungraded_answer(self):
        student_id = uuid.uuid4()
        quiz = Quiz.objects.create(
            student_id=student_id,
            title="Limited Evidence Quiz",
            source="EXISTING",
            status="READY",
            num_questions=2,
            difficulty=3,
        )

        wrong_question = Question.objects.create(
            quiz=quiz,
            question_type="TRUE_FALSE",
            question_text="Question with an incorrect answer",
            correct_answer="True",
            explanation="Explanation",
            topic="Software Testing",
            order=1,
        )
        ungraded_question = Question.objects.create(
            quiz=quiz,
            question_type="TRUE_FALSE",
            question_text="Question awaiting grading",
            correct_answer="True",
            explanation="Explanation",
            topic="Software Testing",
            order=2,
        )

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_id=student_id,
            status="SUBMITTED",
            score=0,
            total=2,
            submitted_at=timezone.now(),
        )
        Answer.objects.create(
            attempt=attempt,
            question=wrong_question,
            selected_answer="False",
            is_correct=False,
        )
        Answer.objects.create(
            attempt=attempt,
            question=ungraded_question,
            selected_answer="True",
            is_correct=None,
        )

        result = get_student_error_analysis(student_id)
        overview = result["overview"]
        self.assertEqual(overview["total_questions"], 2)
        self.assertEqual(overview["incorrect_answers"], 1)
        self.assertEqual(overview["ungraded_answers"], 1)
        self.assertEqual(overview["unanswered_questions"], 0)

        self.assertEqual(len(result["topic_performance"]), 1)
        topic = result["topic_performance"][0]
        self.assertEqual(topic["total_questions"], 2)
        self.assertEqual(topic["evaluated_questions"], 1)
        self.assertEqual(topic["incorrect_answers"], 1)
        self.assertEqual(topic["ungraded_answers"], 1)
        self.assertEqual(topic["error_rate"], 100.0)
        self.assertEqual(topic["priority"], "INSUFFICIENT_DATA")
        self.assertEqual(len(result["review_topics"]), 1)

    def test_only_ungraded_answers_are_not_treated_as_errors(self):
        student_id = uuid.uuid4()
        quiz = Quiz.objects.create(
            student_id=student_id,
            title="Pending Grading Quiz",
            source="EXISTING",
            status="READY",
            num_questions=1,
            difficulty=3,
        )
        question = Question.objects.create(
            quiz=quiz,
            question_type="TRUE_FALSE",
            question_text="Question awaiting grading",
            correct_answer="True",
            explanation="Explanation",
            topic="Database Indexing",
            order=1,
        )
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_id=student_id,
            status="SUBMITTED",
            score=0,
            total=1,
            submitted_at=timezone.now(),
        )
        Answer.objects.create(
            attempt=attempt,
            question=question,
            selected_answer="False",
            is_correct=None,
        )

        result = get_student_error_analysis(student_id)
        topic = result["topic_performance"][0]
        self.assertEqual(topic["ungraded_answers"], 1)
        self.assertEqual(topic["incorrect_answers"], 0)
        self.assertEqual(topic["unanswered_questions"], 0)
        self.assertEqual(topic["evaluated_questions"], 0)
        self.assertEqual(topic["priority"], "INSUFFICIENT_DATA")
        self.assertEqual(result["review_topics"], [])

    def test_student_without_submitted_attempts_has_empty_analysis(self):
        result = get_student_error_analysis(uuid.uuid4())

        self.assertEqual(result["overview"]["total_analyzed_attempts"], 0)
        self.assertEqual(result["overview"]["total_questions"], 0)
        self.assertEqual(result["overview"]["unclassified_questions"], 0)
        self.assertEqual(result["topic_performance"], [])
        self.assertEqual(result["review_topics"], [])


class ReviewTopicsAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse("review_topics")
        self.student_id = uuid.uuid4()

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
            HTTP_X_STUDENT_ID="invalid-uuid",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(
            response.data["message"],
            "X-Student-ID must be a valid UUID",
        )

    def test_student_without_attempts_returns_empty_analysis(self):
        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])

        data = response.data["data"]

        self.assertEqual(
            data["overview"]["total_analyzed_attempts"], 0
        )
        self.assertEqual(data["topic_performance"], [])
        self.assertEqual(data["review_topics"], [])

    def test_returns_only_requested_student_topics(self):
        other_student_id = uuid.uuid4()
        course_id = uuid.uuid4()

        for student_id, topic_name in [
            (self.student_id, "Unit Testing"),
            (other_student_id, "Database Indexing"),
        ]:
            quiz = Quiz.objects.create(
                student_id=student_id,
                course_id=course_id,
                title="API Error Analysis Test",
                source="EXISTING",
                status="READY",
                num_questions=3,
                difficulty=3,
            )

            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                student_id=student_id,
                status="SUBMITTED",
                score=0,
                total=3,
                submitted_at=timezone.now(),
            )

            for index in range(1, 4):
                question = Question.objects.create(
                    quiz=quiz,
                    question_type="TRUE_FALSE",
                    question_text=f"Question {index}",
                    correct_answer="True",
                    explanation="Explanation",
                    topic=topic_name,
                    order=index,
                )

                Answer.objects.create(
                    attempt=attempt,
                    question=question,
                    selected_answer="False",
                    is_correct=False,
                )

        response = self.client.get(
            self.url,
            HTTP_X_STUDENT_ID=str(self.student_id),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])

        data = response.data["data"]

        self.assertEqual(
            data["overview"]["total_analyzed_attempts"], 1
        )
        self.assertEqual(data["overview"]["total_questions"], 3)
        self.assertEqual(len(data["topic_performance"]), 1)
        self.assertEqual(len(data["review_topics"]), 1)

        topic = data["review_topics"][0]

        self.assertEqual(topic["topic"], "Unit Testing")
        self.assertEqual(topic["scope_type"], "course")
        self.assertEqual(topic["scope_id"], str(course_id))
        self.assertEqual(topic["incorrect_answers"], 3)
        self.assertEqual(topic["error_rate"], 100.0)
        self.assertEqual(topic["priority"], "HIGH")
