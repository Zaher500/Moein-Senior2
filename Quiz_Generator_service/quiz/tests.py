import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Answer, Quiz, Question, QuizAttempt


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