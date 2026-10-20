
from copy import deepcopy
from datetime import date, timedelta
from math import ceil
from uuid import uuid4


def replan_study_plan(
    plan: dict,
    replan_date: str,
    daily_study_minutes: int | None = None
):
    """
    Replan unfinished tasks without modifying
    the original saved plan or MongoDB.
    """

    if not isinstance(plan, dict):
        raise ValueError("Invalid saved plan")

    parameters = plan.get("generation_parameters") or {}
    courses = parameters.get("courses") or []
    original_schedule = plan.get("schedule")

    if not courses or not isinstance(original_schedule, list):
        raise ValueError("Saved plan is missing courses or schedule")

    start = date.fromisoformat(replan_date)
    original_start = date.fromisoformat(plan["start_date"])

    if start < original_start:
        raise ValueError(
            "Replan date cannot be before original start date"
        )

    daily_limit = (
        parameters.get("daily_study_minutes")
        if daily_study_minutes is None
        else daily_study_minutes
    )

    if type(daily_limit) is not int or not 5 <= daily_limit <= 1440:
        raise ValueError(
            "daily_study_minutes must be between 5 and 1440"
        )

    # 1. Retrieve exam dates from saved parameters
    deadlines = {
        str(course["course_id"]): date.fromisoformat(
            course["exam_date"]
        )
        for course in courses
    }

    completed_by_date = {}
    remaining = []
    task_ids = set()

    # 2. Separate completed from unfinished tasks
    for day in original_schedule:
        original_day = date.fromisoformat(day["date"])

        for original_task in day["tasks"]:
            task = deepcopy(original_task)

            task_id = task.get("task_id")
            duration = task.get("duration_minutes")
            state = task.get("completion_status")
            course_id = str(task.get("course_id"))

            if not task_id or task_id in task_ids:
                raise ValueError("Missing or duplicate task_id")

            task_ids.add(task_id)

            if type(duration) is not int or duration <= 0:
                raise ValueError("Invalid task duration")

            if state not in {"pending", "completed", "missed"}:
                raise ValueError("Invalid task status")

            if course_id not in deadlines:
                raise ValueError(
                    "Task course is not in saved plan"
                )

            if state == "completed":
                completed_by_date.setdefault(
                    original_day, []
                ).append(task)

            else:
                remaining.append({
                    "task": task,
                    "deadline": deadlines[course_id],
                    "original_date": original_day,
                    "minutes_left": duration,
                    "assigned_once": False
                })

    # All tasks already completed
    if not remaining:
        return {
            "status": "ready",
            "plan_id": plan.get("plan_id"),
            "replan_date": replan_date,
            "daily_study_minutes": daily_limit,
            "remaining_minutes": 0,
            "schedule": deepcopy(original_schedule)
        }

    # 3. Prioritize exams and study before review
    remaining.sort(
        key=lambda item: (
            item["deadline"],
            0 if item["task"]["type"] == "study" else 1,
            item["original_date"]
        )
    )

    # Reserve the time of completed tasks that
    # remain displayed on their original dates.
    def available_on(day):
        used = sum(
            task["duration_minutes"]
            for task in completed_by_date.get(day, [])
        )
        return max(0, daily_limit - used)

    def capacity_before(end_date, from_date):
        total = 0
        cursor = from_date

        while cursor < end_date:
            total += available_on(cursor)
            cursor += timedelta(days=1)

        return total

    # 4. Check whether remaining time is enough
    deadline_checks = []

    for deadline in sorted({
        item["deadline"] for item in remaining
    }):
        required = sum(
            item["minutes_left"]
            for item in remaining
            if item["deadline"] <= deadline
        )

        available = capacity_before(deadline, start)

        deadline_checks.append({
            "exam_date": deadline.isoformat(),
            "required_minutes": required,
            "available_minutes": available,
            "shortage_minutes": max(
                0, required - available
            )
        })

    if any(
        check["shortage_minutes"] > 0
        for check in deadline_checks
    ):
        return {
            "status": "insufficient_time",
            "deadline_checks": deadline_checks
        }

    total_remaining = sum(
        item["minutes_left"] for item in remaining
    )

    scheduled_by_date = {}
    current = start

    last_exam = max(
        item["deadline"] for item in remaining
    )

    # 5. Redistribute unfinished tasks
    while current < last_exam and any(
        item["minutes_left"] > 0
        for item in remaining
    ):

        capacity_today = available_on(current)

        if capacity_today == 0:
            current += timedelta(days=1)
            continue

        active = [
            item for item in remaining
            if item["minutes_left"] > 0
        ]

        days_left = (last_exam - current).days

        average_target = ceil(
            (
                sum(item["minutes_left"] for item in active)
                / days_left
            ) / 5
        ) * 5

        # Minimum time needed today to respect deadlines
        urgent_minimum = 0

        for deadline in sorted({
            item["deadline"] for item in active
        }):
            required = sum(
                item["minutes_left"]
                for item in active
                if item["deadline"] <= deadline
            )

            future_capacity = capacity_before(
                deadline,
                current + timedelta(days=1)
            )

            urgent_minimum = max(
                urgent_minimum,
                required - future_capacity
            )

        target = min(
            capacity_today,
            max(average_target, urgent_minimum)
        )

        # Prefer completing the first task together
        first = active[0]

        if target < first["minutes_left"] <= capacity_today:
            target = first["minutes_left"]

        available = target

        for item in active:
            if available == 0:
                break

            amount = min(
                available,
                item["minutes_left"]
            )

            new_task = deepcopy(item["task"])

            new_task["duration_minutes"] = amount
            new_task["completion_status"] = "pending"

            # If split, preserve the original ID on
            # the first segment and generate new IDs
            # for additional segments.
            if item["assigned_once"]:
                new_task["task_id"] = str(uuid4())

                new_task["source_task_id"] = (
                    item["task"].get(
                        "source_task_id",
                        item["task"]["task_id"]
                    )
                )
            else:
                item["assigned_once"] = True

            # Preserve useful rescheduling history
            if item["task"]["completion_status"] == "missed":
                new_task["replanned_from_status"] = "missed"

            if item["original_date"] != current:
                new_task["replanned_from_date"] = (
                    item["original_date"].isoformat()
                )

            scheduled_by_date.setdefault(
                current, []
            ).append(new_task)

            item["minutes_left"] -= amount
            available -= amount

        current += timedelta(days=1)

    # 6. Final deadline validation
    if any(
        item["minutes_left"] > 0
        for item in remaining
    ):
        return {
            "status": "insufficient_time",
            "deadline_checks": deadline_checks
        }

    # 7. Merge preserved completed tasks
    #    with newly scheduled pending tasks
    result_schedule = []

    all_dates = sorted(
        set(completed_by_date)
        | set(scheduled_by_date)
    )

    for day in all_dates:
        tasks = (
            completed_by_date.get(day, [])
            + scheduled_by_date.get(day, [])
        )

        result_schedule.append({
            "date": day.isoformat(),
            "total_minutes": sum(
                task["duration_minutes"]
                for task in tasks
            ),
            "tasks": tasks
        })

    return {
        "status": "ready",
        "plan_id": plan.get("plan_id"),
        "replan_date": replan_date,
        "daily_study_minutes": daily_limit,
        "remaining_minutes": total_remaining,
        "schedule": result_schedule
    }
