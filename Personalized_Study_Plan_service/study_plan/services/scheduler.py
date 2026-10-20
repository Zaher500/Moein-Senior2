
from datetime import date, timedelta
from math import ceil
from uuid import uuid4


def round_up_to_five(minutes):
    return ceil(minutes / 5) * 5


def generate_multi_course_schedule(prepared: dict):
    """
    Schedule multiple courses using shared daily study time.

    Priorities:
    - Finish before each course exam.
    - Prioritize earlier exam dates.
    - Balance workload across available days.
    - Schedule reviews after study tasks.
    """

    if prepared["status"] != "prepared":
        return {
            "status": "insufficient_time",
            "deadline_checks": prepared.get(
                "deadline_checks", []
            ),
            "schedule": []
        }

    start = date.fromisoformat(prepared["start_date"])
    daily_limit = prepared["daily_study_minutes"]

    if daily_limit <= 0:
        raise ValueError("Daily limit must be positive")

    # 1. Collect all tasks from all courses
    tasks = []

    for course in prepared["courses"]:
        exam_date = date.fromisoformat(
            course["exam_date"]
        )

        if exam_date <= start:
            raise ValueError("Invalid exam date")

        for task in course["tasks"]:
            duration = task["duration_minutes"]
            deadline = date.fromisoformat(
                task["deadline"]
            )

            if duration <= 0:
                raise ValueError(
                    "Task duration must be positive"
                )

            if deadline != exam_date:
                raise ValueError(
                    "Task deadline does not match exam date"
                )

            tasks.append({
            **task,
            "course_name": course["course_name"],
            "_deadline": deadline,
            "_remaining": duration,
            "_source_task_id": str(uuid4())
            })

    if not tasks:
        raise ValueError("No study tasks found")

    # 2. Prioritize earlier exams.
    # For the same deadline, study before review.
    tasks.sort(
        key=lambda task: (
            task["_deadline"],
            0 if task["type"] == "study" else 1
        )
    )

    deadlines = sorted({
        task["_deadline"] for task in tasks
    })

    last_exam = max(deadlines)

    schedule = []
    current_date = start

    # 3. Distribute tasks day by day
    while current_date < last_exam:

        remaining_tasks = [
            task for task in tasks
            if task["_remaining"] > 0
        ]

        if not remaining_tasks:
            break

        if any(
            task["_deadline"] <= current_date
            for task in remaining_tasks
        ):
            return {
                "status": "insufficient_time",
                "schedule": schedule
            }

        total_remaining = sum(
            task["_remaining"]
            for task in remaining_tasks
        )

        days_remaining = (
            last_exam - current_date
        ).days

        # Balanced daily study target
        daily_target = round_up_to_five(
            total_remaining / days_remaining
        )

        # Minimum work required today to meet
        # all upcoming exam deadlines
        urgent_minimum = 0

        for deadline in deadlines:
            if deadline <= current_date:
                continue

            required = sum(
                task["_remaining"]
                for task in remaining_tasks
                if task["_deadline"] <= deadline
            )

            future_days = (
                deadline - current_date
            ).days - 1

            minimum_today = (
                required - future_days * daily_limit
            )

            urgent_minimum = max(
                urgent_minimum,
                minimum_today
            )

        if urgent_minimum > daily_limit:
            return {
                "status": "insufficient_time",
                "schedule": schedule
            }

        daily_target = min(
            daily_limit,
            max(daily_target, urgent_minimum)
        )
        # Prefer completing the first study topic in one session
        first_pending = next(
            (
                task for task in tasks
                if task["_remaining"] > 0
            ),
            None
        )

        if (
            first_pending is not None
            and first_pending["type"] == "study"
            and daily_target < first_pending["_remaining"] <= daily_limit
        ):
          daily_target = first_pending["_remaining"]

        available_today = daily_target
        daily_tasks = []

        # 4. Assign time to prioritized tasks
        for task in tasks:
            if available_today <= 0:
                break

            if task["_remaining"] <= 0:
                continue

            # Avoid unnecessary topic splitting
            minutes_done_today = (
                daily_target - available_today
            )

            if (
                task["type"] == "study"
                and daily_tasks
                and task["_remaining"] > available_today
                and minutes_done_today >= urgent_minimum
            ):
                break

            assigned = min(
                task["_remaining"],
                available_today
            )

            daily_tasks.append({
                "type": task["type"],
                "course_id": task["course_id"],
                "course_name": task["course_name"],
                "lecture_id": task["lecture_id"],
                "topic": task["topic"],
                "duration_minutes": assigned,
                "page_numbers": task.get(
                    "page_numbers", []
                ),
                "source_task_id": task["_source_task_id"]
})

            task["_remaining"] -= assigned
            available_today -= assigned

        if daily_tasks:
            schedule.append({
                "date": current_date.isoformat(),
                "total_minutes": sum(
                    task["duration_minutes"]
                    for task in daily_tasks
                ),
                "tasks": daily_tasks
            })

        current_date += timedelta(days=1)

    # 5. Final validation
    unfinished = [
        task for task in tasks
        if task["_remaining"] > 0
    ]

    if unfinished:
        return {
            "status": "insufficient_time",
            "schedule": schedule
        }

    return {
        "status": "ready",
        "start_date": prepared["start_date"],
        "total_courses": prepared["total_courses"],
        "total_required_minutes": prepared[
            "total_required_minutes"
        ],
        "schedule": schedule
    }
