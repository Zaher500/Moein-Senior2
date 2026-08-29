import uuid
import os

from pymongo import MongoClient
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Quiz, Question, QuizAttempt, Answer
from .serializers import QuizSerializer
from .services.file_extractor import extract_text_from_file
from .services.course_client import fetch_lecture_file
from .services.quiz_generator import generate_quiz
from .services.mongo_store import store_llm_response
from .services.difficulty_engine import get_next_difficulty
from .services.progress_service import get_student_progress
from .rabbitmq_client import publish_quiz_job


def build_response(success, message, data=None, status_code=200):
    return Response({
        "success": success,
        "message": message,
        "data": data or {}
    }, status=status_code)


def _validate_num_questions(num_questions):
    try:
        num_questions = int(num_questions)
        if num_questions <= 0:
            raise ValueError
        return num_questions, None
    except (TypeError, ValueError):
        return None, build_response(
            False,
            'num_questions must be a positive integer',
            status_code=400
        )


def _validate_uuid(value, field_name):
    try:
        uuid.UUID(str(value))
        return None
    except (ValueError, TypeError):
        return build_response(
            False,
            f'{field_name} must be a valid UUID',
            status_code=400
        )


def _validate_file(file_obj):
    if not file_obj:
        return build_response(
            False,
            'File is required',
            status_code=400
        )

    allowed_extensions = ['.pdf', '.docx']
    filename = file_obj.name.lower()

    if not any(filename.endswith(ext) for ext in allowed_extensions):
        return build_response(
            False,
            'Only PDF and DOCX files are allowed',
            status_code=400
        )

    if file_obj.size == 0:
        return build_response(
            False,
            'Uploaded file is empty',
            status_code=400
        )

    return None


def is_scope_in_text(scope, text):
    scope_words = [
        w.strip().lower()
        for w in scope.split()
        if len(w.strip()) > 2
    ]

    text_lower = text.lower()

    if not scope_words:
        return False

    matches = sum(
        1 for word in scope_words
        if word in text_lower
    )

    return (matches / len(scope_words)) >= 0.5


def _process_quiz_generation(
    request,
    source_type,
    text,
    num_questions,
    lecture_id,
    course_id,
    title,
    scope=None,
    question_mode='mixed'
):
    student_id = request.headers.get('X-Student-ID')

    if not student_id:
        return build_response(
            False,
            'X-Student-ID header is missing',
            status_code=400
        )

    difficulty = get_next_difficulty(
        student_id=student_id,
        lecture_id=lecture_id,
        course_id=course_id,
    )

    quiz = Quiz.objects.create(
        lecture_id=lecture_id,
        course_id=course_id,
        student_id=student_id,
        title=title,
        source=source_type,
        status='PROCESSING',
        num_questions=num_questions,
        difficulty=difficulty,
    )

    try:
        raw_response, valid_questions = generate_quiz(
           text=text,
           num_questions=num_questions,
           scope=scope,
           question_mode=question_mode,
           difficulty=difficulty,
        )

        with transaction.atomic():
            for i, q_data in enumerate(valid_questions, start=1):
                Question.objects.create(
                    quiz=quiz,
                    question_type=q_data.get('question_type'),
                    question_text=q_data.get('question_text'),
                    options=q_data.get('options', []),
                    correct_answer=q_data.get('correct_answer'),
                    explanation=q_data.get('explanation', ''),
                    order=i
                )

            if valid_questions:
                quiz.status = 'READY'
                quiz.error = None
            else:
                quiz.status = 'FAILED'
                quiz.error = (
                    "LLM failed to generate valid questions "
                    "matching the requested schema."
                )

            quiz.save()

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

        return build_response(
            True,
            "Quiz generated successfully",
            {
                "quiz_id": quiz.quiz_id,
                "status": quiz.status,
                "difficulty": quiz.difficulty,
                "generated_count": len(valid_questions)
            },
            status_code=201
        )

    except Exception as e:
        quiz.status = 'FAILED'
        quiz.error = str(e)
        quiz.save()

        return build_response(
            False,
            "Quiz generation failed",
            {
                "error": str(e)
            },
            status_code=500
        )


def _create_pending_quiz_and_publish(
    request,
    source_type,
    *,
    lecture_id=None,
    course_id=None,
    title='Generated Quiz',
    num_questions=5,
    question_mode='mixed',
    scope=None,
    text=None,
    original_filename=None,
):
    student_id = request.headers.get('X-Student-ID')

    if not student_id:
        return build_response(
            False,
            'X-Student-ID header is required',
            status_code=401
        )

    # Determine the difficulty of the new quiz
    # from the student's latest attempt in the same lecture/course.
    difficulty = get_next_difficulty(
        student_id=student_id,
        lecture_id=lecture_id,
        course_id=course_id,
    )

    try:
        quiz = Quiz.objects.create(
            student_id=student_id,
            lecture_id=lecture_id,
            course_id=course_id,
            title=title,
            source=source_type,
            status='PENDING',
            num_questions=num_questions,
            difficulty=difficulty,
        )
    except Exception as e:
        return build_response(
            False,
            f'Failed to create pending quiz: {str(e)}',
            status_code=500
        )

    payload = {
        'quiz_id': str(quiz.quiz_id),
        'student_id': str(student_id),
        'lecture_id': str(lecture_id) if lecture_id else None,
        'course_id': str(course_id) if course_id else None,
        'title': title,
        'source_type': source_type,
        'num_questions': num_questions,
        'question_mode': question_mode,
        'difficulty': difficulty,
    }

    if scope:
        payload['scope'] = scope

    if text:
        payload['text'] = text

    if original_filename:
        payload['original_filename'] = original_filename

    try:
        publish_quiz_job(payload)

    except Exception as e:
        quiz.status = 'FAILED'
        quiz.save(update_fields=['status'])

        return build_response(
            False,
            f'Failed to queue quiz generation: {str(e)}',
            status_code=500
        )

    return build_response(
        True,
        'Quiz generation started successfully',
        data={
            'quiz_id': str(quiz.quiz_id),
            'status': quiz.status,
            'difficulty': quiz.difficulty,
        },
        status_code=202
    )


@api_view(['POST'])
def generate_from_existing_view(request):
    lecture_id = request.data.get('lecture_id')
    course_id = request.data.get('course_id')
    num_questions = request.data.get('num_questions', 5)
    title = request.data.get('title', 'Generated Quiz')
    question_mode = request.data.get('question_mode', 'mixed')

    if question_mode not in ['mcq', 'true_false', 'mixed']:
        return build_response(
            False,
            'question_mode must be mcq, true_false, or mixed',
            status_code=400
        )

    if not all([lecture_id, course_id]):
        return build_response(
            False,
            'lecture_id and course_id are required fields',
            status_code=400
        )

    error = _validate_uuid(lecture_id, 'lecture_id')
    if error:
        return error

    error = _validate_uuid(course_id, 'course_id')
    if error:
        return error

    num_questions, error_response = _validate_num_questions(
        num_questions
    )

    if error_response:
        return error_response

    try:
        file_obj, filename = fetch_lecture_file(
            request,
            lecture_id
        )

        text = extract_text_from_file(
            file_obj,
            filename
        )

    except Exception as e:
        return build_response(
            False,
            str(e),
            status_code=500
        )

    return _create_pending_quiz_and_publish(
        request=request,
        source_type='EXISTING',
        lecture_id=lecture_id,
        course_id=course_id,
        title=title,
        num_questions=num_questions,
        question_mode=question_mode,
        text=text,
        original_filename=filename,
    )


@api_view(['POST'])
def generate_from_file_view(request):
    file_obj = request.FILES.get('file')

    lecture_id = request.data.get('lecture_id') or None
    course_id = request.data.get('course_id') or None

    num_questions = request.data.get(
        'num_questions',
        5
    )

    title = request.data.get(
        'title',
        'Generated Quiz'
    )

    question_mode = request.data.get(
        'question_mode',
        'mixed'
    )

    if question_mode not in ['mcq', 'true_false', 'mixed']:
        return build_response(
            False,
            'question_mode must be mcq, true_false, or mixed',
            status_code=400
        )

    if not file_obj:
        return build_response(
            False,
            'file is required',
            status_code=400
        )

    if lecture_id:
        error = _validate_uuid(
            lecture_id,
            'lecture_id'
        )

        if error:
            return error

    if course_id:
        error = _validate_uuid(
            course_id,
            'course_id'
        )

        if error:
            return error

    file_error = _validate_file(file_obj)

    if file_error:
        return file_error

    num_questions, error_response = _validate_num_questions(
        num_questions
    )

    if error_response:
        return error_response

    try:
        text = extract_text_from_file(
            file_obj,
            file_obj.name
        )

    except Exception as e:
        return build_response(
            False,
            f'File extraction failed: {str(e)}',
            status_code=500
        )

    return _create_pending_quiz_and_publish(
        request=request,
        source_type='FILE',
        lecture_id=lecture_id,
        course_id=course_id,
        title=title,
        num_questions=num_questions,
        question_mode=question_mode,
        text=text,
        original_filename=file_obj.name,
    )


@api_view(['POST'])
def generate_from_scope_view(request):
    lecture_id = request.data.get('lecture_id')
    course_id = request.data.get('course_id')

    num_questions = request.data.get(
        'num_questions',
        5
    )

    title = request.data.get(
        'title',
        'Generated Quiz'
    )

    scope = request.data.get('scope')

    question_mode = request.data.get(
        'question_mode',
        'mixed'
    )

    if question_mode not in ['mcq', 'true_false', 'mixed']:
        return build_response(
            False,
            'question_mode must be mcq, true_false, or mixed',
            status_code=400
        )

    if not all([
        lecture_id,
        course_id,
        scope
    ]):
        return build_response(
            False,
            'lecture_id, course_id, and scope are required fields',
            status_code=400
        )

    error = _validate_uuid(
        lecture_id,
        'lecture_id'
    )

    if error:
        return error

    error = _validate_uuid(
        course_id,
        'course_id'
    )

    if error:
        return error

    num_questions, error_response = _validate_num_questions(
        num_questions
    )

    if error_response:
        return error_response

    try:
        file_obj, filename = fetch_lecture_file(
            request,
            lecture_id
        )

    except Exception as e:
        return build_response(
            False,
            f'Failed to fetch lecture file: {str(e)}',
            status_code=500
        )

    if not file_obj:
        return build_response(
            False,
            'Lecture file not found',
            status_code=404
        )

    try:
        file_obj.seek(0)

        text = extract_text_from_file(
            file_obj,
            filename
        )

    except Exception as e:
        return build_response(
            False,
            f'File extraction failed: {str(e)}',
            status_code=500
        )

    return _create_pending_quiz_and_publish(
        request=request,
        source_type='SCOPE',
        lecture_id=lecture_id,
        course_id=course_id,
        title=title,
        num_questions=num_questions,
        question_mode=question_mode,
        scope=scope,
        text=text,
        original_filename=filename,
    )


@api_view(['GET', 'DELETE'])
def quiz_detail_view(request, quiz_id):
    error = _validate_uuid(
        quiz_id,
        'quiz_id'
    )

    if error:
        return error

    quiz = get_object_or_404(
        Quiz,
        quiz_id=quiz_id
    )

    if request.method == 'GET':
        serializer = QuizSerializer(quiz)

        return build_response(
            True,
            "Quiz fetched successfully",
            serializer.data,
            status_code=200
        )

    try:
        mongo_uri = os.getenv(
            'MONGO_URI',
            'mongodb://localhost:27017'
        )

        mongo_db_name = os.getenv(
            'MONGO_DB',
            'quiz_results'
        )

        client = MongoClient(mongo_uri)

        db = client[mongo_db_name]

        db['llm_generation_logs'].delete_one({
            "quiz_id": str(quiz_id)
        })

        client.close()

    except Exception:
        pass

    quiz.delete()

    return build_response(
        True,
        "Quiz deleted successfully",
        status_code=204
    )


@api_view(['GET'])
def quiz_status_view(request, quiz_id):
    error = _validate_uuid(
        quiz_id,
        'quiz_id'
    )

    if error:
        return error

    quiz = get_object_or_404(
        Quiz,
        quiz_id=quiz_id
    )

    return build_response(
        True,
        "Quiz status fetched",
        {
            "quiz_id": quiz.quiz_id,
            "status": quiz.status,
            "error": quiz.error
        },
        status_code=200
    )


@api_view(['GET'])
def quiz_by_lecture_view(request, lecture_id):
    error = _validate_uuid(
        lecture_id,
        'lecture_id'
    )

    if error:
        return error

    quizzes = Quiz.objects.filter(
        lecture_id=lecture_id
    )

    serializer = QuizSerializer(
        quizzes,
        many=True
    )

    return build_response(
        True,
        "Lecture quizzes fetched successfully",
        serializer.data,
        status_code=200
    )


@api_view(['POST'])
def quiz_submit_view(request, quiz_id):
    error = _validate_uuid(
        quiz_id,
        'quiz_id'
    )

    if error:
        return error

    quiz = get_object_or_404(
        Quiz,
        quiz_id=quiz_id
    )

    student_id = request.headers.get(
        'X-Student-ID'
    )

    if not student_id:
        return build_response(
            False,
            'X-Student-ID header is missing',
            status_code=400
        )

    answers_data = request.data.get(
        'answers',
        []
    )

    if not isinstance(
        answers_data,
        list
    ):
        return build_response(
            False,
            'answers must be a JSON array',
            status_code=400
        )

    if not answers_data:
        return build_response(
            False,
            'answers list cannot be empty',
            status_code=400
        )

    for ans in answers_data:
        if (
            'question_id' not in ans
            or
            'selected_answer' not in ans
        ):
            return build_response(
                False,
                'Each answer must contain question_id and selected_answer',
                status_code=400
            )

        question_id_error = _validate_uuid(
            ans.get('question_id'),
            'question_id'
        )

        if question_id_error:
            return question_id_error

    total_questions = quiz.questions.count()

    if total_questions == 0:
        return build_response(
            False,
            'This quiz has no valid questions to score.',
            status_code=400
        )

    score = 0
    results = []

    with transaction.atomic():
        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student_id=student_id,
            score=0.0,
            total=total_questions
        )

        for ans_data in answers_data:
            q_id = str(
                ans_data.get('question_id')
            ).strip()

            selected_answer = str(
                ans_data.get(
                    'selected_answer',
                    ''
                )
            ).strip()

            question = quiz.questions.filter(
                question_id=q_id
            ).first()

            if not question:
                continue

            is_correct = (
                selected_answer.lower()
                ==
                str(
                    question.correct_answer
                ).strip().lower()
            )

            if is_correct:
                score += 1

            Answer.objects.create(
                attempt=attempt,
                question=question,
                selected_answer=selected_answer,
                is_correct=is_correct
            )

            results.append({
                "question_id": str(
                    question.question_id
                ),
                "question_text": question.question_text,
                "selected_answer": selected_answer,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "explanation": question.explanation
            })

        percentage = (
            score / total_questions
        ) * 100.0

        attempt.score = score
        attempt.save()

    return build_response(
        True,
        "Quiz submitted successfully",
        {
            "attempt_id": str(
                attempt.attempt_id
            ),
            "score": score,
            "total": total_questions,
            "percentage": round(
                percentage,
                2
            ),
            "results": results
        },
        status_code=201
    )


@api_view(['GET'])
def learning_progress_view(request):
    student_id = request.headers.get('X-Student-ID')

    if not student_id:
        return build_response(
            False,
            'X-Student-ID header is missing',
            status_code=400
        )

    student_id_error = _validate_uuid(
        student_id,
        'X-Student-ID'
    )

    if student_id_error:
        return student_id_error

    progress = get_student_progress(student_id)

    return build_response(
        True,
        "Learning progress fetched successfully",
        progress,
        status_code=200
    )
