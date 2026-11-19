from quiz.models import QuizAttempt


MIN_EVIDENCE = 3


def _empty_counts():
    return {
        "total_questions": 0,
        "correct_answers": 0,
        "incorrect_answers": 0,
        "unanswered_questions": 0,
        "ungraded_answers": 0,
    }


def _count_question(counts, answer):
    counts["total_questions"] += 1

    if answer is None:
        counts["unanswered_questions"] += 1
    elif answer.is_correct is True:
        counts["correct_answers"] += 1
    elif answer.is_correct is False:
        counts["incorrect_answers"] += 1
    else:
        counts["ungraded_answers"] += 1


def _get_scope(quiz):
    if quiz.course_id:
        return "course", str(quiz.course_id)

    if quiz.lecture_id:
        return "lecture", str(quiz.lecture_id)

    return "quiz", str(quiz.quiz_id)


def _calculate_priority(error_rate, evidence_count):
    if evidence_count < MIN_EVIDENCE:
        return "INSUFFICIENT_DATA"

    if error_rate >= 60:
        return "HIGH"

    if error_rate >= 30:
        return "MEDIUM"

    return "LOW"


def get_student_error_analysis(student_id):
    attempts = (
        QuizAttempt.objects.filter(
            student_id=student_id,
            status="SUBMITTED",
            total__gt=0,
        )
        .select_related("quiz")
        .prefetch_related(
            "quiz__questions",
            "answers",
        )
        .order_by("submitted_at", "attempt_id")
    )

    overview = {
        "total_analyzed_attempts": 0,
        **_empty_counts(),
        "unclassified_questions": 0,
    }

    topic_stats = {}

    for attempt in attempts:
        overview["total_analyzed_attempts"] += 1

        answers_by_question = {
            answer.question_id: answer for answer in attempt.answers.all()
        }

        scope_type, scope_id = _get_scope(attempt.quiz)

        for question in attempt.quiz.questions.all():
            answer = answers_by_question.get(question.question_id)

            _count_question(overview, answer)

            topic = " ".join((question.topic or "").split())

            if not topic:
                overview["unclassified_questions"] += 1
                continue

            key = (
                scope_type,
                scope_id,
                topic.casefold(),
            )

            if key not in topic_stats:
                topic_stats[key] = {
                    "topic": topic,
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    **_empty_counts(),
                }

            _count_question(topic_stats[key], answer)

    topic_performance = []

    for stats in topic_stats.values():
        evidence_count = (
            stats["correct_answers"]
            + stats["incorrect_answers"]
            + stats["unanswered_questions"]
        )

        errors = stats["incorrect_answers"] + stats["unanswered_questions"]

        accuracy = (
            stats["correct_answers"] / evidence_count * 100 if evidence_count else 0.0
        )

        error_rate = errors / evidence_count * 100 if evidence_count else 0.0

        stats["evaluated_questions"] = evidence_count
        stats["accuracy"] = round(accuracy, 2)
        stats["error_rate"] = round(error_rate, 2)

        stats["priority"] = _calculate_priority(
            error_rate,
            evidence_count,
        )

        topic_performance.append(stats)

    priority_order = {
        "HIGH": 0,
        "MEDIUM": 1,
        "LOW": 2,
        "INSUFFICIENT_DATA": 3,
    }

    topic_performance.sort(
        key=lambda item: (
            priority_order[item["priority"]],
            -item["error_rate"],
            -item["evaluated_questions"],
            item["topic"].casefold(),
        )
    )

    review_topics = [
        stats
        for stats in topic_performance
        if (stats["incorrect_answers"] + stats["unanswered_questions"]) > 0
    ]

    return {
        "overview": overview,
        "topic_performance": topic_performance,
        "review_topics": review_topics,
    }
