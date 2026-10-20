
from datetime import date, timedelta
from math import ceil


LEVEL_MULTIPLIERS = {
    "beginner": 1.5,
    "intermediate": 1.0,
    "advanced": 0.8
}


def round_to_five(minutes):
    return max(5, ceil(minutes / 5) * 5)


def generate_study_plan(
    lecture_analysis: dict,
    start_date: str,
    exam_date: str,
    daily_study_minutes: int,
    knowledge_level: str = "intermediate"
):
    """
    Generate a personalized study schedule
    using an existing lecture analysis.
    """

    # 1. Validate student preferences
    if knowledge_level not in LEVEL_MULTIPLIERS:
        raise ValueError("Invalid knowledge level")

    if daily_study_minutes <= 0:
        raise ValueError("Daily study minutes must be positive")

    start = date.fromisoformat(start_date)
    exam = date.fromisoformat(exam_date)

    if exam <= start:
        raise ValueError("Exam date must be after start date")

    available_days = (exam - start).days

    # 2. Adjust topic study time
    multiplier = LEVEL_MULTIPLIERS[knowledge_level]

    tasks = []

    for topic in lecture_analysis["topics"]:
        base_minutes = topic["estimated_study_minutes"]

        adjusted_minutes = round_to_five(
            base_minutes * multiplier
        )

        tasks.append({
            "type": "study",
            "topic": topic["name"],
            "difficulty": topic["difficulty"],
            "importance": topic["importance"],
            "page_numbers": topic["page_numbers"],
            "remaining_minutes": adjusted_minutes
        })

    if not tasks:
        raise ValueError("No topics found in lecture analysis")

    total_study_minutes = sum(
        task["remaining_minutes"] for task in tasks
    )

    # 3. Add review time
    review_minutes = round_to_five(
        total_study_minutes * 0.20
    )

    tasks.append({
        "type": "review",
        "topic": "Review important lecture concepts",
        "remaining_minutes": review_minutes
    })

    required_minutes = total_study_minutes + review_minutes
    available_minutes = available_days * daily_study_minutes

    # 4. Check whether the plan fits before the exam
    if required_minutes > available_minutes:
        return {
            "status": "insufficient_time",
            "required_minutes": required_minutes,
            "available_minutes": available_minutes,
            "missing_minutes": required_minutes - available_minutes,
            "schedule": []
        }

    # 5. Distribute study tasks over available days
    schedule = []
    task_index = 0

    for day_index in range(available_days):
        current_date = start + timedelta(days=day_index)
        remaining_daily_time = daily_study_minutes
        daily_tasks = []

        while remaining_daily_time > 0 and task_index < len(tasks):
            task = tasks[task_index]

            assigned_minutes = min(
                task["remaining_minutes"],
                remaining_daily_time
            )

            daily_tasks.append({
                "type": task["type"],
                "topic": task["topic"],
                "duration_minutes": assigned_minutes
            })

            task["remaining_minutes"] -= assigned_minutes
            remaining_daily_time -= assigned_minutes

            if task["remaining_minutes"] == 0:
                task_index += 1

        if daily_tasks:
            schedule.append({
                "date": current_date.isoformat(),
                "tasks": daily_tasks
            })

        if task_index == len(tasks):
            break

    return {
        "status": "ready",
        "lecture_id": lecture_analysis["lecture_id"],
        "knowledge_level": knowledge_level,
        "start_date": start_date,
        "exam_date": exam_date,
        "total_study_minutes": total_study_minutes,
        "review_minutes": review_minutes,
        "total_required_minutes": required_minutes,
        "schedule": schedule
    }



def prepare_multi_course_plan(
    courses: list[dict],
    start_date: str,
    daily_study_minutes: int
):
    """
    Prepare study requirements for multiple courses.
    Scheduling will be handled separately.
    """

    if not courses:
        raise ValueError("At least one course is required")

    if daily_study_minutes <= 0:
        raise ValueError("Daily study minutes must be positive")

    start = date.fromisoformat(start_date)

    prepared_courses = []
    seen_course_ids = set()
    total_required_minutes = 0

    for course in courses:

        # 1. Read course information
        course_id = str(course["course_id"])
        course_name = course["course_name"]
        exam_date = date.fromisoformat(course["exam_date"])
        knowledge_level = course["knowledge_level"]
        lectures = course["lectures"]

        if course_id in seen_course_ids:
            raise ValueError("Duplicate course_id")

        seen_course_ids.add(course_id)

        if exam_date <= start:
            raise ValueError(
                f"Invalid exam date for {course_name}"
            )

        if knowledge_level not in LEVEL_MULTIPLIERS:
            raise ValueError(
                f"Invalid knowledge level for {course_name}"
            )

        if not lectures:
            raise ValueError(
                f"No lectures selected for {course_name}"
            )

        multiplier = LEVEL_MULTIPLIERS[knowledge_level]

        course_tasks = []
        course_study_minutes = 0
        seen_lecture_ids = set()

        # 2. Process all selected lectures
        for lecture in lectures:

            lecture_id = str(lecture["lecture_id"])

            if lecture_id in seen_lecture_ids:
                raise ValueError(
                    f"Duplicate lecture: {lecture_id}"
                )

            seen_lecture_ids.add(lecture_id)

            if not lecture.get("topics"):
                raise ValueError(
                    f"No topics found for lecture {lecture_id}"
                )

            for topic in lecture["topics"]:

                base_minutes = topic["estimated_study_minutes"]

                if base_minutes <= 0:
                    raise ValueError(
                        "Topic study time must be positive"
                    )

                adjusted_minutes = round_to_five(
                    base_minutes * multiplier
                )

                course_tasks.append({
                    "type": "study",
                    "course_id": course_id,
                    "lecture_id": lecture_id,
                    "topic": topic["name"],
                    "difficulty": topic["difficulty"],
                    "importance": topic["importance"],
                    "page_numbers": topic["page_numbers"],
                    "duration_minutes": adjusted_minutes,
                    "deadline": exam_date.isoformat()
                })

                course_study_minutes += adjusted_minutes

        # 3. Calculate review time for this course
        review_minutes = round_to_five(
            course_study_minutes * 0.20
        )

        course_tasks.append({
            "type": "review",
            "course_id": course_id,
            "lecture_id": None,
            "topic": f"Review {course_name}",
            "duration_minutes": review_minutes,
            "deadline": exam_date.isoformat()
        })

        course_required_minutes = (
            course_study_minutes + review_minutes
        )

        total_required_minutes += course_required_minutes

        # 4. Store prepared course data
        prepared_courses.append({
            "course_id": course_id,
            "course_name": course_name,
            "exam_date": exam_date.isoformat(),
            "knowledge_level": knowledge_level,
            "study_minutes": course_study_minutes,
            "review_minutes": review_minutes,
            "required_minutes": course_required_minutes,
            "tasks": course_tasks
        })

    # 5. Check shared capacity before each exam date
    deadline_checks = []

    exam_dates = sorted({
        course["exam_date"]
        for course in prepared_courses
    })

    for deadline in exam_dates:
        days_available = (
            date.fromisoformat(deadline) - start
        ).days

        available_minutes = (
            days_available * daily_study_minutes
        )

        required_by_deadline = sum(
            course["required_minutes"]
            for course in prepared_courses
            if course["exam_date"] <= deadline
        )

        deadline_checks.append({
            "exam_date": deadline,
            "required_minutes": required_by_deadline,
            "available_minutes": available_minutes,
            "missing_minutes": max(
                0,
                required_by_deadline - available_minutes
            )
        })

    has_shortage = any(
        check["missing_minutes"] > 0
        for check in deadline_checks
    )

    return {
        "status": (
            "insufficient_time" if has_shortage
            else "prepared"
        ),
        "start_date": start.isoformat(),
        "daily_study_minutes": daily_study_minutes,
        "total_courses": len(prepared_courses),
        "total_required_minutes": total_required_minutes,
        "courses": prepared_courses,
        "deadline_checks": deadline_checks
    }
