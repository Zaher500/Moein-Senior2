def distribute_questions(lecture_ids, num_questions):
    if not lecture_ids:
        raise ValueError("At least one lecture is required")

    if len(set(lecture_ids)) != len(lecture_ids):
        raise ValueError("Duplicate lectures are not allowed")

    if (
        isinstance(num_questions, bool)
        or not isinstance(num_questions, int)
        or num_questions < len(lecture_ids)
    ):
        raise ValueError(
            "Question count must be at least the number of lectures"
        )

    base, remainder = divmod(num_questions, len(lecture_ids))

    return [
        (lecture_id, base + (1 if index < remainder else 0))
        for index, lecture_id in enumerate(lecture_ids)
    ]

def generate_exam_questions(
    lecture_texts,
    num_questions,
    question_mode="mixed",
    difficulty=3,
):
    from .quiz_generator import generate_quiz

    if question_mode not in ("mcq", "true_false", "mixed"):
        raise ValueError("Invalid question mode")

    distribution = distribute_questions(
        list(lecture_texts.keys()),
        num_questions,
    )

    expected_type = {
        "mcq": "MCQ",
        "true_false": "TRUE_FALSE",
        "mixed": None,
    }[question_mode]

    combined_questions = []
    raw_responses = {}
    seen_questions = set()

    for lecture_id, count in distribution:
        text = lecture_texts[lecture_id]

        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"Lecture {lecture_id} has no usable text"
            )

        raw_response, questions = generate_quiz(
            text=text,
            num_questions=count,
            question_mode=question_mode,
            difficulty=difficulty,
        )

        raw_responses[str(lecture_id)] = raw_response
        lecture_questions = []

        for question in questions:
            if not isinstance(question, dict):
                continue

            question_type = question.get("question_type")

            if question_type not in ("MCQ", "TRUE_FALSE"):
                continue

            if expected_type and question_type != expected_type:
                continue

            question_text = question.get("question_text")

            if not isinstance(question_text, str):
                continue

            normalized_text = " ".join(
                question_text.casefold().split()
            )

            if not normalized_text or normalized_text in seen_questions:
                continue

            seen_questions.add(normalized_text)

            lecture_questions.append({
                **question,
                "source_lecture_id": str(lecture_id),
            })

            if len(lecture_questions) == count:
                break

        if len(lecture_questions) != count:
            raise ValueError(
                f"Lecture {lecture_id}: expected {count} "
                f"unique questions, got {len(lecture_questions)}"
            )

        combined_questions.extend(lecture_questions)

    return raw_responses, combined_questions


def collect_exam_lecture_texts(lecture_ids, load_text):
    if not isinstance(lecture_ids, list) or not lecture_ids:
        raise ValueError("Exam must contain lectures")

    if len(set(lecture_ids)) != len(lecture_ids):
        raise ValueError("Duplicate lecture IDs")

    lecture_texts = {}

    for lecture_id in lecture_ids:
        text = load_text(lecture_id)

        if not isinstance(text, str) or not text.strip():
            raise ValueError(
                f"Lecture {lecture_id} has no usable text"
            )

        lecture_texts[lecture_id] = text.strip()

    return lecture_texts
