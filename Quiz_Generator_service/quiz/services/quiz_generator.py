import re
import json
import logging
import random

from .llm_client import call_hf_llm


logger = logging.getLogger(__name__)


MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5
DEFAULT_DIFFICULTY = 3


DIFFICULTY_GUIDANCE = {
    1: {
        "name": "Very Easy",
        "instructions": (
            "- Focus on direct recall of facts explicitly stated in the text.\n"
            "- Questions should require little or no inference.\n"
            "- Use simple and clear wording.\n"
            "- Avoid combining multiple concepts in one question.\n"
            "- MCQ distractors should be plausible but clearly distinguishable "
            "using the provided text."
        )
    },

    2: {
        "name": "Easy",
        "instructions": (
            "- Focus on basic understanding of concepts explicitly explained "
            "in the text.\n"
            "- Questions may require a simple one-step inference.\n"
            "- Ask about meanings, purposes, relationships, or basic "
            "applications.\n"
            "- Avoid complex multi-step reasoning.\n"
            "- MCQ distractors should be plausible and related to the same topic."
        )
    },

    3: {
        "name": "Medium",
        "instructions": (
            "- Require application and moderate reasoning.\n"
            "- Questions may require connecting two related pieces of "
            "information from the text.\n"
            "- Prefer understanding and application over direct memorization.\n"
            "- Scenario-based questions are allowed when the answer is fully "
            "supported by the text.\n"
            "- MCQ distractors should be plausible enough to require careful "
            "understanding."
        )
    },

    4: {
        "name": "Hard",
        "instructions": (
            "- Require analysis rather than direct recall.\n"
            "- Prefer comparison, interpretation, application, or multi-step "
            "reasoning.\n"
            "- Questions may require combining multiple related concepts from "
            "the text.\n"
            "- Use scenarios where the student must determine how concepts "
            "apply.\n"
            "- MCQ distractors must be close and plausible, but only one answer "
            "may be fully correct.\n"
            "- Avoid questions whose answer can be copied directly from one "
            "sentence without reasoning."
        )
    },

    5: {
        "name": "Very Hard",
        "instructions": (
            "- Require deep reasoning and integration of multiple concepts.\n"
            "- Prefer synthesis, complex application, trade-offs, edge cases, "
            "or multi-step analysis when supported by the text.\n"
            "- The student should need to understand how several ideas interact, "
            "not merely remember individual facts.\n"
            "- MCQ distractors should represent realistic near-miss "
            "interpretations.\n"
            "- Keep exactly one unambiguously correct answer.\n"
            "- Difficulty must come from reasoning complexity, not from vague "
            "wording, obscure trivia, or information outside the text."
        )
    },
}


def normalize_difficulty(difficulty):
    try:
        difficulty = int(difficulty)

    except (TypeError, ValueError):
        return DEFAULT_DIFFICULTY

    return max(
        MIN_DIFFICULTY,
        min(MAX_DIFFICULTY, difficulty)
    )


def generate_quiz(
    text,
    num_questions,
    scope=None,
    question_mode='mixed',
    difficulty=DEFAULT_DIFFICULTY
):
    difficulty = normalize_difficulty(
        difficulty
    )

    difficulty_config = DIFFICULTY_GUIDANCE[
        difficulty
    ]

    difficulty_name = difficulty_config[
        "name"
    ]

    difficulty_instructions = difficulty_config[
        "instructions"
    ]

    # Determine how many MCQ vs True/False
    # questions to generate.
    if question_mode == "mcq":
        mcq_count = num_questions
        tf_count = 0

    elif question_mode == "true_false":
        mcq_count = 0
        tf_count = num_questions

    else:
        # Mixed mode:
        # ensure at least one question of each type
        # whenever num_questions >= 2.
        if num_questions >= 2:
            mcq_count = random.randint(
                1,
                num_questions - 1
            )

        else:
            mcq_count = 1

        tf_count = (
            num_questions - mcq_count
        )

    # Build the prompt according to
    # the requested question mode.
    if question_mode == "mcq":
        prompt = (
            f"Generate {num_questions} "
            f"Multiple Choice questions only "
            f"based on the provided text.\n\n"
        )

    elif question_mode == "true_false":
        prompt = (
            f"Generate {num_questions} "
            f"True/False questions only "
            f"based on the provided text.\n\n"
        )

    else:
        prompt = (
            f"Generate {num_questions} questions "
            f"({mcq_count} Multiple Choice and "
            f"{tf_count} True/False) "
            f"based on the provided text.\n\n"
        )

    # Question type restrictions.
    if question_mode == "mcq":
        prompt += (
            "IMPORTANT:\n"
            "- Generate only MCQ questions.\n"
            "- Do NOT generate TRUE_FALSE questions.\n\n"
        )

    elif question_mode == "true_false":
        prompt += (
            "IMPORTANT:\n"
            "- Generate only TRUE_FALSE questions.\n"
            "- Do NOT generate MCQ questions.\n\n"
        )

    else:
        prompt += (
            "IMPORTANT:\n"
            f"- Generate exactly {mcq_count} "
            f"MCQ questions.\n"
            f"- Generate exactly {tf_count} "
            f"TRUE_FALSE questions.\n\n"
        )

    # Adaptive difficulty instructions.
    prompt += (
        "ADAPTIVE DIFFICULTY REQUIREMENT:\n"
        f"- Target difficulty level: "
        f"{difficulty}/5 ({difficulty_name}).\n"
        f"{difficulty_instructions}\n\n"

        "GENERAL DIFFICULTY RULES:\n"
        "- Every question must be answerable using ONLY "
        "the provided text.\n"
        "- Do NOT use external knowledge to make a "
        "question harder.\n"
        "- Do NOT create trick questions or intentionally "
        "ambiguous wording.\n"
        "- Difficulty must come from the amount and depth "
        "of reasoning required.\n"
        "- The correct answer must be clearly and "
        "unambiguously supported by the provided text.\n"
        "- Keep all questions aligned with the requested "
        "difficulty level.\n"
    )

    if difficulty >= 4:
        prompt += (
            "- For TRUE_FALSE questions at this difficulty, "
            "prefer statements that require understanding "
            "relationships between concepts rather than "
            "simple factual recall.\n"
        )

    prompt += "\n"

    # Scope restriction.
    if scope:
        prompt += (
            "IMPORTANT SCOPE RESTRICTION:\n"
            f'- The requested scope is: "{scope}".\n'
            "- Generate questions ONLY from information "
            "explicitly present in the provided text that "
            "matches this scope.\n"
            "- Do NOT use any external knowledge.\n"
            "- Do NOT invent facts or concepts not mentioned "
            "in the text.\n"
            "- If the requested scope is not covered in the "
            "text, return an empty JSON array [].\n"
            "- If the scope is only partially covered, "
            "generate questions only from the covered parts.\n\n"
        )

    # MCQ format requirements.
    if question_mode == "mcq":
        prompt += (
            "IMPORTANT MCQ FORMAT:\n"
            "- Each MCQ must have exactly 4 meaningful "
            "full-text answer options.\n"
            "- Do NOT use placeholder options like "
            "A, B, C, D.\n"
            "- Do NOT make correct_answer a letter.\n"
            "- correct_answer must exactly equal one "
            "full option text.\n\n"
        )

    elif question_mode == "mixed":
        prompt += (
            "IMPORTANT MCQ FORMAT:\n"
            "- For every MCQ question, provide exactly "
            "4 meaningful full-text answer options.\n"
            "- Do NOT use placeholder options like "
            "A, B, C, D.\n"
            "- For MCQ, correct_answer must exactly equal "
            "one full option text.\n\n"
        )

    prompt += (
        f"Text:\n{text}\n\n"
    )

    prompt += (
        "TOPIC CLASSIFICATION:\n"
        "- Assign a concise and specific topic to each question.\n"
        "- The topic must be based only on the provided text.\n"
        "- Use consistent topic names for questions about "
        "the same concept.\n"
        "- Avoid generic topics such as General or Miscellaneous.\n"
        "- Do NOT invent topics not supported by the text.\n"
        "- If the topic cannot be identified reliably, "
        "use an empty string.\n\n"
    )

    prompt += (
        "Output MUST be exactly a JSON array of objects "
        "with the following schema. "
        "Do NOT wrap it in markdown block quotes "
        "(like ```json).\n"

        "[\n"
        "  {\n"
        '    "question_type": "MCQ" or "TRUE_FALSE",\n'
        '    "question_text": "...",\n'
        '    "options": '
        '"full option text 1|full option text 2|'
        'full option text 3|full option text 4", '
        '(For MCQ, provide exactly 4 full answer options '
        'separated by |. Do NOT use only letters like '
        'A, B, C, D. Leave as empty string for TRUE_FALSE.),\n'
        '    "correct_answer": "...", '
        '(For MCQ, this must exactly match one full option '
        'text, not a letter. For TRUE_FALSE, it must be '
        '"True" or "False".),\n'
        '    "explanation": "...",\n'
        '    "topic": "..."\n'
        "  }\n"
        "]"
    )

    raw_response = call_hf_llm(
        prompt
    )

    # Remove possible reasoning blocks from
    # models that emit <think> tags.
    cleaned_response = re.sub(
        r'<think>.*?</think>',
        '',
        raw_response,
        flags=re.DOTALL
    ).strip()

    if cleaned_response.startswith(
        '```json'
    ):
        cleaned_response = (
            cleaned_response[7:]
        )

    if cleaned_response.startswith(
        '```'
    ):
        cleaned_response = (
            cleaned_response[3:]
        )

    if cleaned_response.endswith(
        '```'
    ):
        cleaned_response = (
            cleaned_response[:-3]
        )

    cleaned_response = (
        cleaned_response.strip()
    )

    try:
        parsed_data = json.loads(
            cleaned_response
        )

    except json.JSONDecodeError as e:
        logger.error(
            f"Failed to parse LLM response "
            f"as JSON: {e}"
        )

        return raw_response, []

    if not isinstance(
        parsed_data,
        list
    ):
        logger.error(
            "LLM response must be a JSON array."
        )

        return raw_response, []

    valid_questions = []

    for item in parsed_data:
        if not isinstance(item, dict):
            logger.warning(
                f"Skipping non-object question: "
                f"{item}"
            )

            continue

        try:
            topic = item.get("topic")

            if isinstance(topic, str):
                topic = " ".join(topic.split())

                if (
                    not topic
                    or len(topic) > 255
                    or topic.casefold() in {
                        "general",
                        "miscellaneous",
                        "unknown",
                        "n/a",
                    }
                ):
                    topic = None
            else:
                topic = None

            item["topic"] = topic

            q_type = item.get(
                "question_type"
            )

            if q_type == "MCQ":
                options = [
                    opt.strip()
                    for opt in item.get(
                        "options",
                        ""
                    ).split("|")
                ]

                correct_answer = str(
                    item.get(
                        "correct_answer",
                        ""
                    )
                ).strip()

                # Reject placeholder answers such as
                # A | B | C | D.
                if all(
                    opt in {
                        "A",
                        "B",
                        "C",
                        "D"
                    }
                    for opt in options
                ):
                    logger.warning(
                        "Skipping placeholder "
                        f"MCQ options: {item}"
                    )

                    continue

                # MCQ must contain exactly four
                # answer options and correct_answer
                # must exactly match one of them.
                if (
                    len(options) == 4
                    and correct_answer in options
                ):
                    item["options"] = "|".join(
                        options
                    )

                    item["correct_answer"] = (
                        correct_answer
                    )

                    valid_questions.append(
                        item
                    )

                else:
                    logger.warning(
                        "Skipping malformed "
                        f"MCQ: {item}"
                    )

            elif q_type == "TRUE_FALSE":
                answer = str(
                    item.get(
                        "correct_answer",
                        ""
                    )
                ).strip()

                if answer.lower() in [
                    "true",
                    "false"
                ]:
                    item["correct_answer"] = (
                        "True"
                        if answer.lower() == "true"
                        else "False"
                    )

                    valid_questions.append(
                        item
                    )

                else:
                    logger.warning(
                        "Skipping malformed "
                        f"TRUE_FALSE: {item}"
                    )

            else:
                logger.warning(
                    "Skipping unsupported "
                    f"question type: {item}"
                )

        except Exception as e:
            logger.warning(
                f"Error validating question: "
                f"{item}. Error: {e}"
            )

    return (
        raw_response,
        valid_questions
    )