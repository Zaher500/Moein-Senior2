from quiz.models import QuizAttempt


MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
DEFAULT_DIFFICULTY = 3


def _clamp_difficulty(value):
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, value))


def get_next_difficulty(student_id, lecture_id=None, course_id=None):
    """
    Determine the difficulty for the student's next quiz.

    Priority:
    1. Previous attempts for the same lecture.
    2. If there is no lecture_id, use previous attempts for the same course.
    3. If there is no previous attempt, start at Medium (3).
    """

    attempts = QuizAttempt.objects.filter(
        student_id=student_id,
        status='SUBMITTED',
    )

    if lecture_id:
        attempts = attempts.filter(quiz__lecture_id=lecture_id)

    elif course_id:
        attempts = attempts.filter(quiz__course_id=course_id)

    else:
        return DEFAULT_DIFFICULTY

    last_attempt = (
        attempts
        .select_related("quiz")
        .order_by("-submitted_at")
        .first()
    )

    if not last_attempt:
        return DEFAULT_DIFFICULTY

    if last_attempt.total <= 0:
        return DEFAULT_DIFFICULTY

    percentage = (last_attempt.score / last_attempt.total) * 100

    current_difficulty = last_attempt.quiz.difficulty

    if percentage >= 85:
        next_difficulty = current_difficulty + 1

    elif percentage < 60:
        next_difficulty = current_difficulty - 1

    else:
        next_difficulty = current_difficulty

    return _clamp_difficulty(next_difficulty)