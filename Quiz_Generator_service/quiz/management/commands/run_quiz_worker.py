import json
from collections import Counter
import pika

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, OuterRef

from quiz.models import Quiz, QuizAttempt, Question
from quiz.services.quiz_generator import generate_quiz
from quiz.services.exam_generator import (
    generate_exam_questions,
    collect_exam_lecture_texts,
    distribute_questions,
)
from quiz.services.file_extractor import extract_text_from_file
from quiz.services.mongo_store import store_llm_response


def normalize_options(options):
    if options is None:
        return ""

    if isinstance(options, list):
        return " | ".join(
            str(opt).strip()
            for opt in options
        )

    return str(options)


class Command(BaseCommand):
    help = "Run RabbitMQ worker for quiz generation"

    def handle(self, *args, **options):
        credentials = pika.PlainCredentials(
            settings.RABBITMQ_USER,
            settings.RABBITMQ_PASSWORD
        )

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=settings.RABBITMQ_HOST,
                port=settings.RABBITMQ_PORT,
                credentials=credentials
            )
        )

        channel = connection.channel()

        channel.queue_declare(
            queue=settings.RABBITMQ_QUEUE,
            durable=True
        )

        channel.basic_qos(
            prefetch_count=1
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Quiz worker is running..."
            )
        )

        def callback(
            ch,
            method,
            properties,
            body
        ):
            payload = json.loads(body)

            quiz_id = payload.get("quiz_id")
            lecture_id = payload.get("lecture_id")
            student_id = payload.get("student_id")
            text = payload.get("text")

            num_questions = payload.get(
                "num_questions",
                5
            )

            scope = payload.get("scope")

            question_mode = payload.get(
                "question_mode",
                "mixed"
            )

            payload_difficulty = payload.get(
                "difficulty"
            )

            quiz = None
            claimed = 0

            try:
                quiz = Quiz.objects.get(
                    quiz_id=quiz_id
                )

                # The DB value is used as a fallback
                # for older RabbitMQ messages that do not
                # contain the difficulty field.
                difficulty = (
                    payload_difficulty
                    if payload_difficulty is not None
                    else quiz.difficulty
                )

                # A single conditional UPDATE claims a pending quiz only
                # when it has no attempts, including incomplete ones.
                # EXISTS avoids a related-table join in MySQL UPDATE.
                has_attempts = QuizAttempt.objects.filter(
                    quiz_id=OuterRef("pk")
                )
                claimed = (
                    Quiz.objects.filter(
                        quiz_id=quiz_id,
                        status="PENDING",
                    )
                    .filter(~Exists(has_attempts))
                    .update(status="PROCESSING", error=None)
                )

                if claimed == 0:
                    self.stdout.write(
                        f"Skipping quiz {quiz_id}: "
                        "not pending or already has attempts"
                    )
                    ch.basic_ack(
                        delivery_tag=method.delivery_tag
                    )
                    return

                if quiz.source == "EXAM":
                    from quiz.services.exam_staging import (
                        open_staged_exam_lecture_file,
                    )

                    difficulty = quiz.difficulty
                    student_id = str(quiz.student_id)
                    lecture_id = None

                    def load_exam_text(selected_lecture_id):
                        file_obj, filename = (
                            open_staged_exam_lecture_file(
                                quiz.quiz_id,
                                selected_lecture_id,
                            )
                        )

                        with file_obj:
                            return extract_text_from_file(
                                file_obj,
                                filename,
                            )

                    lecture_texts = collect_exam_lecture_texts(
                        quiz.exam_lecture_ids,
                        load_exam_text,
                    )

                    raw_response, valid_questions = (
                        generate_exam_questions(
                            lecture_texts=lecture_texts,
                            num_questions=quiz.num_questions,
                            question_mode=question_mode,
                            difficulty=difficulty,
                        )
                    )

                    if (
                        not isinstance(valid_questions, list)
                        or len(valid_questions) != quiz.num_questions
                    ):
                        raise ValueError(
                            "Exam generation returned an incomplete "
                            "question set"
                        )

                    expected_counts = dict(
                        distribute_questions(
                            quiz.exam_lecture_ids,
                            quiz.num_questions,
                        )
                    )

                    actual_counts = Counter(
                        str(question.get("source_lecture_id"))
                        for question in valid_questions
                        if isinstance(question, dict)
                    )

                    if actual_counts != expected_counts:
                        raise ValueError(
                            "Exam questions do not match "
                            "lecture distribution"
                        )

                else:
                    if not text:
                        raise Exception(
                            "No text found in RabbitMQ payload"
                        )

                    raw_response, valid_questions = generate_quiz(
                        text=text,
                        num_questions=num_questions,
                        scope=scope,
                        question_mode=question_mode,
                        difficulty=difficulty,
                    )

                self.stdout.write(
                    f"Processing quiz {quiz_id} "
                    f"with difficulty {difficulty}/5"
                )

                replacement_blocked = False
                with transaction.atomic():
                    # Lock the quiz while checking for newly created attempts.
                    locked_quiz = Quiz.objects.select_for_update().get(
                        quiz_id=quiz_id
                    )
                    if locked_quiz.attempts.exists():
                        # An attempt appeared after this worker claimed the quiz.
                        # Keep its original questions and make it resumable.
                        if not locked_quiz.questions.exists():
                            raise ValueError(
                                "Cannot resume quiz: attempts exist but questions are missing"
                            )
                        locked_quiz.status = "READY"
                        locked_quiz.error = None
                        locked_quiz.save(update_fields=["status", "error"])
                        replacement_blocked = True
                    else:
                        quiz.questions.all().delete()

                        for i, q_data in enumerate(
                            valid_questions,
                            start=1
                        ):
                            Question.objects.create(
                                quiz=quiz,
                                question_type=q_data.get(
                                    "question_type"
                                ),
                                question_text=q_data.get(
                                    "question_text"
                                ),
                                topic=q_data.get(
                                    "topic"
                                ),
                                options=normalize_options(
                                    q_data.get("options")
                                ),
                                correct_answer=q_data.get(
                                    "correct_answer"
                                ),
                                explanation=q_data.get(
                                    "explanation",
                                    ""
                                ),
                                source_lecture_id=(
                                    q_data.get("source_lecture_id")
                                    if quiz.source == "EXAM"
                                    else None
                                ),
                                order=i
                            )

                        if valid_questions:
                            quiz.status = "READY"
                            quiz.error = None
                        else:
                            quiz.status = "FAILED"
                            quiz.error = (
                                "LLM failed to generate valid "
                                "questions matching the "
                                "requested schema."
                            )

                        quiz.save(
                            update_fields=[
                                "status",
                                "error"
                            ]
                        )

                if replacement_blocked:
                    self.stdout.write(
                        f"Skipping question replacement for quiz {quiz_id}: "
                        "existing attempts must be preserved"
                    )
                    ch.basic_ack(
                        delivery_tag=method.delivery_tag
                    )
                    return

                try:
                    store_llm_response(
                        quiz_id=quiz.quiz_id,
                        lecture_id=lecture_id,
                        student_id=student_id,
                        raw_response=raw_response,
                        parsed_questions=valid_questions
                    )

                except Exception:
                    pass

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Quiz {quiz_id} processed "
                        f"successfully at difficulty "
                        f"{difficulty}/5"
                    )
                )

            except Exception as e:
                # Only a worker that successfully claimed this quiz may
                # mark it FAILED, and only while it is still PROCESSING.
                if claimed:
                    Quiz.objects.filter(
                        quiz_id=quiz_id,
                        status="PROCESSING",
                    ).update(
                        status="FAILED",
                        error=str(e),
                    )

                self.stdout.write(
                    self.style.ERROR(
                        f"Quiz {quiz_id} failed: "
                        f"{str(e)}"
                    )
                )

            finally:
                if (
                    claimed
                    and quiz is not None
                    and quiz.source == "EXAM"
                ):
                    try:
                        from quiz.services.exam_staging import (
                            cleanup_exam_staging,
                        )

                        cleanup_exam_staging(quiz.quiz_id)

                    except OSError as cleanup_error:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Exam staging cleanup failed "
                                f"for {quiz_id}: {cleanup_error}"
                            )
                        )

            ch.basic_ack(
                delivery_tag=method.delivery_tag
            )

        channel.basic_consume(
            queue=settings.RABBITMQ_QUEUE,
            on_message_callback=callback
        )

        channel.start_consuming()
