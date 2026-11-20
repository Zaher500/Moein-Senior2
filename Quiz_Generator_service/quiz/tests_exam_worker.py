import json
import uuid
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from quiz.models import Quiz, Question
from quiz.management.commands.run_quiz_worker import Command


class ExamWorkerTests(TestCase):

    @patch("quiz.services.exam_staging.cleanup_exam_staging")
    @patch("quiz.services.exam_staging.open_staged_exam_lecture_file")
    @patch("quiz.management.commands.run_quiz_worker.store_llm_response")
    @patch("quiz.management.commands.run_quiz_worker.generate_exam_questions")
    @patch("quiz.management.commands.run_quiz_worker.extract_text_from_file")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_exam_worker_generates_and_saves_questions(
        self,
        mock_connection,
        mock_extract,
        mock_generate_exam,
        mock_store,
        mock_open,
        mock_cleanup,
    ):
        student_id = uuid.uuid4()
        course_id = uuid.uuid4()
        lecture_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ]

        quiz = Quiz.objects.create(
            student_id=student_id,
            course_id=course_id,
            source="EXAM",
            status="PENDING",
            title="Multi-Lecture Exam",
            num_questions=3,
            difficulty=3,
            exam_lecture_ids=lecture_ids,
        )

        mock_open.side_effect = [
            (BytesIO(b"lecture one"), "lecture1.pdf"),
            (BytesIO(b"lecture two"), "lecture2.pdf"),
        ]

        mock_extract.side_effect = [
            "Content of lecture one",
            "Content of lecture two",
        ]

        questions = [
            {
                "question_type": "TRUE_FALSE",
                "question_text": f"Question {i}",
                "options": "",
                "correct_answer": "True",
                "explanation": f"Explanation {i}",
                "topic": "Testing",
                "source_lecture_id": lecture_ids[0] if i <= 2 else lecture_ids[1],
            }
            for i in range(1, 4)
        ]

        mock_generate_exam.return_value = (
            {"lecture1": "raw1", "lecture2": "raw2"},
            questions,
        )

        channel = mock_connection.return_value.channel.return_value

        Command().handle()

        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]

        payload = {
            "quiz_id": str(quiz.quiz_id),
            "source_type": "EXAM",
            "student_id": str(student_id),
            "course_id": str(course_id),
            "num_questions": 3,
            "question_mode": "mixed",
            "difficulty": 3,
        }

        callback(
            channel,
            SimpleNamespace(delivery_tag=123),
            None,
            json.dumps(payload).encode("utf-8"),
        )

        quiz.refresh_from_db()

        self.assertEqual(quiz.status, "READY")
        self.assertEqual(quiz.questions.count(), 3)

        saved_questions = list(
            Question.objects.filter(quiz=quiz)
            .order_by("order")
        )

        self.assertEqual(
            [str(q.source_lecture_id) for q in saved_questions],
            [lecture_ids[0], lecture_ids[0], lecture_ids[1]],
        )

        mock_generate_exam.assert_called_once()
        mock_cleanup.assert_called_once_with(quiz.quiz_id)

        channel.basic_ack.assert_called_once_with(
            delivery_tag=123
        )


    @patch("quiz.services.exam_staging.cleanup_exam_staging")
    @patch("quiz.services.exam_staging.open_staged_exam_lecture_file")
    @patch("quiz.management.commands.run_quiz_worker.generate_exam_questions")
    @patch("quiz.management.commands.run_quiz_worker.extract_text_from_file")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_exam_worker_rejects_empty_extracted_text(
        self,
        mock_connection,
        mock_extract,
        mock_generate,
        mock_open,
        mock_cleanup,
    ):
        student_id = uuid.uuid4()
        course_id = uuid.uuid4()
        lecture_id = str(uuid.uuid4())

        quiz = Quiz.objects.create(
            student_id=student_id,
            course_id=course_id,
            source="EXAM",
            status="PENDING",
            title="Empty Lecture Exam",
            num_questions=2,
            difficulty=3,
            exam_lecture_ids=[lecture_id],
        )

        mock_open.return_value = (
            BytesIO(b"scanned pdf"),
            "lecture.pdf",
        )

        mock_extract.return_value = "   "

        channel = mock_connection.return_value.channel.return_value

        Command().handle()

        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]

        payload = {
            "quiz_id": str(quiz.quiz_id),
            "source_type": "EXAM",
            "student_id": str(student_id),
            "course_id": str(course_id),
            "num_questions": 2,
            "question_mode": "mixed",
        }

        callback(
            channel,
            SimpleNamespace(delivery_tag=456),
            None,
            json.dumps(payload).encode("utf-8"),
        )

        quiz.refresh_from_db()

        self.assertEqual(quiz.status, "FAILED")
        self.assertEqual(quiz.questions.count(), 0)
        self.assertIn("no usable text", quiz.error)

        mock_generate.assert_not_called()
        mock_cleanup.assert_called_once_with(quiz.quiz_id)

        channel.basic_ack.assert_called_once_with(
            delivery_tag=456
        )


    @patch("quiz.services.exam_staging.cleanup_exam_staging")
    @patch("quiz.services.exam_staging.open_staged_exam_lecture_file")
    @patch("quiz.management.commands.run_quiz_worker.generate_exam_questions")
    @patch("quiz.management.commands.run_quiz_worker.extract_text_from_file")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_exam_worker_rejects_incomplete_questions(
        self,
        mock_connection,
        mock_extract,
        mock_generate,
        mock_open,
        mock_cleanup,
    ):
        student_id = uuid.uuid4()
        course_id = uuid.uuid4()
        lecture_id = str(uuid.uuid4())

        quiz = Quiz.objects.create(
            student_id=student_id,
            course_id=course_id,
            source="EXAM",
            status="PENDING",
            title="Incomplete Exam Test",
            num_questions=3,
            difficulty=3,
            exam_lecture_ids=[lecture_id],
        )

        mock_open.return_value = (
            BytesIO(b"lecture content"),
            "lecture.pdf",
        )

        mock_extract.return_value = "Valid lecture text"

        mock_generate.return_value = (
            {"lecture": "raw response"},
            [
                {
                    "question_type": "TRUE_FALSE",
                    "question_text": f"Question {i}",
                    "options": "",
                    "correct_answer": "True",
                    "explanation": "Test",
                    "source_lecture_id": lecture_id,
                }
                for i in range(1, 3)
            ],
        )

        channel = mock_connection.return_value.channel.return_value

        Command().handle()

        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]

        payload = {
            "quiz_id": str(quiz.quiz_id),
            "source_type": "EXAM",
            "student_id": str(student_id),
            "course_id": str(course_id),
            "num_questions": 3,
            "question_mode": "mixed",
        }

        callback(
            channel,
            SimpleNamespace(delivery_tag=789),
            None,
            json.dumps(payload).encode("utf-8"),
        )

        quiz.refresh_from_db()

        self.assertEqual(quiz.status, "FAILED")
        self.assertEqual(quiz.questions.count(), 0)
        self.assertIn("incomplete", quiz.error.lower())

        mock_generate.assert_called_once()
        mock_cleanup.assert_called_once_with(quiz.quiz_id)

        channel.basic_ack.assert_called_once_with(
            delivery_tag=789
        )


    @patch("quiz.services.exam_staging.cleanup_exam_staging")
    @patch("quiz.services.exam_staging.open_staged_exam_lecture_file")
    @patch("quiz.management.commands.run_quiz_worker.generate_exam_questions")
    @patch("quiz.management.commands.run_quiz_worker.extract_text_from_file")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_exam_worker_rejects_wrong_distribution(
        self,
        mock_connection,
        mock_extract,
        mock_generate,
        mock_open,
        mock_cleanup,
    ):
        student_id = uuid.uuid4()
        course_id = uuid.uuid4()
        lecture_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ]

        quiz = Quiz.objects.create(
            student_id=student_id,
            course_id=course_id,
            source="EXAM",
            status="PENDING",
            title="Wrong Distribution Test",
            num_questions=3,
            difficulty=3,
            exam_lecture_ids=lecture_ids,
        )

        mock_open.side_effect = [
            (BytesIO(b"lecture 1"), "lecture1.pdf"),
            (BytesIO(b"lecture 2"), "lecture2.pdf"),
        ]

        mock_extract.side_effect = [
            "Lecture one content",
            "Lecture two content",
        ]

        mock_generate.return_value = (
            {"lecture1": "raw1", "lecture2": "raw2"},
            [
                {
                    "question_type": "TRUE_FALSE",
                    "question_text": f"Question {i}",
                    "options": "",
                    "correct_answer": "True",
                    "explanation": "Test explanation",
                    "source_lecture_id": lecture_ids[0],
                }
                for i in range(1, 4)
            ],
        )

        channel = mock_connection.return_value.channel.return_value

        Command().handle()

        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]

        payload = {
            "quiz_id": str(quiz.quiz_id),
            "source_type": "EXAM",
            "student_id": str(student_id),
            "course_id": str(course_id),
            "num_questions": 3,
            "question_mode": "mixed",
        }

        callback(
            channel,
            SimpleNamespace(delivery_tag=900),
            None,
            json.dumps(payload).encode("utf-8"),
        )

        quiz.refresh_from_db()

        self.assertEqual(quiz.status, "FAILED")
        self.assertEqual(quiz.questions.count(), 0)
        self.assertIn("distribution", quiz.error.lower())

        mock_generate.assert_called_once()
        mock_cleanup.assert_called_once_with(quiz.quiz_id)

        channel.basic_ack.assert_called_once_with(
            delivery_tag=900
        )


    @patch("quiz.management.commands.run_quiz_worker.generate_exam_questions")
    @patch("quiz.management.commands.run_quiz_worker.extract_text_from_file")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_exam_worker_missing_staged_file(
        self,
        mock_connection,
        mock_extract,
        mock_generate,
    ):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from quiz.services.exam_staging import stage_exam_lecture_file

        student_id = uuid.uuid4()
        course_id = uuid.uuid4()
        lecture_ids = [
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        ]

        quiz = Quiz.objects.create(
            student_id=student_id,
            course_id=course_id,
            source="EXAM",
            status="PENDING",
            title="Missing Staged File Test",
            num_questions=2,
            difficulty=3,
            exam_lecture_ids=lecture_ids,
        )

        mock_extract.return_value = "Lecture one content"

        with TemporaryDirectory() as temp_dir:
            staging_root = Path(temp_dir) / "staging"

            with patch(
                "quiz.services.exam_staging.STAGING_ROOT",
                staging_root,
            ):
                first_file = stage_exam_lecture_file(
                    quiz.quiz_id,
                    lecture_ids[0],
                    BytesIO(b"%PDF-1.4 test content"),
                    "lecture.pdf",
                )

                self.assertTrue(first_file.exists())

                # The second lecture is intentionally missing.

                channel = (
                    mock_connection.return_value
                    .channel.return_value
                )

                Command().handle()

                callback = (
                    channel.basic_consume
                    .call_args.kwargs["on_message_callback"]
                )

                payload = {
                    "quiz_id": str(quiz.quiz_id),
                    "source_type": "EXAM",
                    "student_id": str(student_id),
                    "course_id": str(course_id),
                    "num_questions": 2,
                    "question_mode": "mixed",
                }

                callback(
                    channel,
                    SimpleNamespace(delivery_tag=901),
                    None,
                    json.dumps(payload).encode("utf-8"),
                )

                quiz.refresh_from_db()

                self.assertEqual(quiz.status, "FAILED")
                self.assertEqual(quiz.questions.count(), 0)

                self.assertIn(
                    "Expected one staged file",
                    quiz.error,
                )

                mock_extract.assert_called_once()
                mock_generate.assert_not_called()

                self.assertFalse(first_file.exists())
                self.assertFalse(first_file.parent.exists())

                channel.basic_ack.assert_called_once_with(
                    delivery_tag=901
                )


    @patch("quiz.services.exam_staging.cleanup_exam_staging")
    @patch("quiz.services.exam_staging.open_staged_exam_lecture_file")
    @patch("quiz.management.commands.run_quiz_worker.store_llm_response")
    @patch("quiz.management.commands.run_quiz_worker.generate_exam_questions")
    @patch("quiz.management.commands.run_quiz_worker.extract_text_from_file")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_attempt_started_during_exam_generation_preserves_answers(
        self,
        mock_connection,
        mock_extract,
        mock_generate,
        mock_store,
        mock_open,
        mock_cleanup,
    ):
        from quiz.models import QuizAttempt, Answer

        student_id = uuid.uuid4()
        lecture_id = str(uuid.uuid4())

        quiz = Quiz.objects.create(
            student_id=student_id,
            course_id=uuid.uuid4(),
            source="EXAM",
            status="PENDING",
            title="Exam Save Resume Test",
            num_questions=1,
            difficulty=3,
            exam_lecture_ids=[lecture_id],
        )

        original_question = Question.objects.create(
            quiz=quiz,
            question_type="TRUE_FALSE",
            question_text="Original question",
            correct_answer="True",
            explanation="Original explanation",
            source_lecture_id=lecture_id,
            order=1,
        )

        mock_open.return_value = (
            BytesIO(b"lecture content"),
            "lecture.pdf",
        )
        mock_extract.return_value = "Valid lecture text"

        created = {}

        def generate_with_attempt(**kwargs):
            attempt = QuizAttempt.objects.create(
                quiz=quiz,
                student_id=student_id,
                status="IN_PROGRESS",
                total=1,
            )

            answer = Answer.objects.create(
                attempt=attempt,
                question=original_question,
                selected_answer="True",
                is_correct=None,
            )

            created["attempt_id"] = attempt.pk
            created["answer_id"] = answer.pk

            return (
                {"lecture": "raw response"},
                [
                    {
                        "question_type": "TRUE_FALSE",
                        "question_text": "Replacement question",
                        "options": "",
                        "correct_answer": "False",
                        "explanation": "Replacement explanation",
                        "source_lecture_id": lecture_id,
                    }
                ],
            )

        mock_generate.side_effect = generate_with_attempt

        channel = mock_connection.return_value.channel.return_value

        Command().handle()

        callback = channel.basic_consume.call_args.kwargs[
            "on_message_callback"
        ]

        payload = {
            "quiz_id": str(quiz.quiz_id),
            "source_type": "EXAM",
            "student_id": str(student_id),
            "num_questions": 1,
            "question_mode": "mixed",
        }

        callback(
            channel,
            SimpleNamespace(delivery_tag=902),
            None,
            json.dumps(payload).encode("utf-8"),
        )

        quiz.refresh_from_db()
        original_question.refresh_from_db()

        self.assertEqual(quiz.status, "READY")
        self.assertEqual(quiz.questions.count(), 1)

        self.assertEqual(
            original_question.question_text,
            "Original question",
        )

        self.assertTrue(
            QuizAttempt.objects.filter(
                pk=created["attempt_id"]
            ).exists()
        )

        saved_answer = Answer.objects.get(
            pk=created["answer_id"]
        )

        self.assertEqual(
            saved_answer.question_id,
            original_question.pk,
        )
        self.assertEqual(
            saved_answer.selected_answer,
            "True",
        )

        self.assertFalse(
            Question.objects.filter(
                quiz=quiz,
                question_text="Replacement question",
            ).exists()
        )

        mock_generate.assert_called_once()
        mock_store.assert_not_called()
        mock_cleanup.assert_called_once_with(quiz.quiz_id)

        channel.basic_ack.assert_called_once_with(
            delivery_tag=902
        )


    @patch("quiz.management.commands.run_quiz_worker.generate_exam_questions")
    @patch("quiz.management.commands.run_quiz_worker.pika.BlockingConnection")
    def test_duplicate_exam_message_preserves_staging(
        self,
        mock_connection,
        mock_generate,
    ):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from quiz.services.exam_staging import stage_exam_lecture_file

        student_id = uuid.uuid4()
        lecture_id = str(uuid.uuid4())

        quiz = Quiz.objects.create(
            student_id=student_id,
            course_id=uuid.uuid4(),
            source="EXAM",
            status="PROCESSING",
            title="Duplicate Exam Message",
            num_questions=1,
            difficulty=3,
            exam_lecture_ids=[lecture_id],
        )

        with TemporaryDirectory() as temp_dir:
            with patch(
                "quiz.services.exam_staging.STAGING_ROOT",
                Path(temp_dir) / "staging",
            ):
                staged_file = stage_exam_lecture_file(
                    quiz.quiz_id,
                    lecture_id,
                    BytesIO(b"%PDF-1.4 test content"),
                    "lecture.pdf",
                )

                channel = (
                    mock_connection.return_value
                    .channel.return_value
                )

                Command().handle()

                callback = (
                    channel.basic_consume
                    .call_args.kwargs["on_message_callback"]
                )

                payload = {
                    "quiz_id": str(quiz.quiz_id),
                    "source_type": "EXAM",
                    "student_id": str(student_id),
                    "num_questions": 1,
                    "question_mode": "mixed",
                }

                callback(
                    channel,
                    SimpleNamespace(delivery_tag=903),
                    None,
                    json.dumps(payload).encode("utf-8"),
                )

                quiz.refresh_from_db()

                self.assertEqual(quiz.status, "PROCESSING")
                self.assertEqual(quiz.questions.count(), 0)

                # The original worker still needs this file.
                self.assertTrue(staged_file.exists())

                mock_generate.assert_not_called()

                channel.basic_ack.assert_called_once_with(
                    delivery_tag=903
                )
