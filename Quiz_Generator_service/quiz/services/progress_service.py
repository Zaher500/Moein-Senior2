from quiz.models import QuizAttempt


def get_student_progress(student_id):
    attempts = (
        QuizAttempt.objects
        .filter(student_id=student_id, total__gt=0)
        .select_related("quiz")
        .order_by("submitted_at")
    )

    attempts = list(attempts)

    if not attempts:
        return {
            "overview": {
                "total_attempts": 0,
                "unique_quizzes_completed": 0,
                "average_score": 0.0,
                "best_score": 0.0,
                "latest_score": 0.0,
                "total_questions": 0,
                "correct_answers": 0,
                "accuracy": 0.0,
            },
            "score_trend": [],
            "lecture_performance": [],
            "difficulty_progression": [],
        }

    total_attempts = len(attempts)
    unique_quizzes_completed = len({
        attempt.quiz_id
        for attempt in attempts
    })

    total_questions = sum(
        attempt.total
        for attempt in attempts
    )

    correct_answers = sum(
        attempt.score
        for attempt in attempts
    )

    percentages = [
        (attempt.score / attempt.total) * 100
        for attempt in attempts
    ]

    average_score = sum(percentages) / total_attempts
    best_score = max(percentages)
    latest_score = percentages[-1]

    accuracy = (
        (correct_answers / total_questions) * 100
        if total_questions > 0
        else 0.0
    )

    score_trend = []
    difficulty_progression = []
    lecture_stats = {}

    for attempt, percentage in zip(attempts, percentages):
        score_trend.append({
            "attempt_id": str(attempt.attempt_id),
            "quiz_id": str(attempt.quiz_id),
            "title": attempt.quiz.title,
            "submitted_at": attempt.submitted_at,
            "percentage": round(percentage, 2),
        })

        difficulty_progression.append({
            "attempt_id": str(attempt.attempt_id),
            "quiz_id": str(attempt.quiz_id),
            "submitted_at": attempt.submitted_at,
            "difficulty": attempt.quiz.difficulty,
            "percentage": round(percentage, 2),
        })

        lecture_id = attempt.quiz.lecture_id

        if lecture_id:
            lecture_key = str(lecture_id)

            if lecture_key not in lecture_stats:
                lecture_stats[lecture_key] = {
                    "lecture_id": lecture_key,
                    "attempts": 0,
                    "percentage_sum": 0.0,
                }

            lecture_stats[lecture_key]["attempts"] += 1
            lecture_stats[lecture_key]["percentage_sum"] += percentage

    lecture_performance = []

    for lecture in lecture_stats.values():
        lecture_performance.append({
            "lecture_id": lecture["lecture_id"],
            "attempts": lecture["attempts"],
            "average_score": round(
                lecture["percentage_sum"] / lecture["attempts"],
                2
            ),
        })

    return {
        "overview": {
            "total_attempts": total_attempts,
            "unique_quizzes_completed": unique_quizzes_completed,
            "average_score": round(average_score, 2),
            "best_score": round(best_score, 2),
            "latest_score": round(latest_score, 2),
            "total_questions": total_questions,
            "correct_answers": int(correct_answers),
            "accuracy": round(accuracy, 2),
        },
        "score_trend": score_trend,
        "lecture_performance": lecture_performance,
        "difficulty_progression": difficulty_progression,
    }