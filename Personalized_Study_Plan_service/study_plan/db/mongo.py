
import hashlib
from datetime import datetime, timezone
from pymongo import MongoClient,ReturnDocument
from django.conf import settings
from copy import deepcopy
from uuid import uuid4


# MongoDB connection
client = MongoClient(
    settings.MONGO_URI,
    serverSelectionTimeoutMS=5000
)


# ==========================================
# Existing Summarization Database
# ==========================================

summarization_db = client["summarization_service"]

summaries_collection = summarization_db["summaries"]


def get_extracted_text(
    lecture_id: str,
    student_id: str
):
    """
    Retrieve original extracted lecture text.
    """

    document = summaries_collection.find_one(
        {
            "lecture_id": str(lecture_id),
            "student_id": str(student_id)
        },
        {
            "_id": 0,
            "extracted_text": 1
        }
    )

    if not document:
        return None

    return document.get("extracted_text")


# ==========================================
# Personalized Study Plan Database
# ==========================================

study_plan_db = client["personalized_study_plan_service"]

lecture_analyses_collection = study_plan_db[
    "lecture_analyses"
]


def calculate_content_hash(extracted_text: str):
    """
    Generate a fingerprint of the lecture text.
    """

    return hashlib.sha256(
        extracted_text.encode("utf-8")
    ).hexdigest()


def save_lecture_analysis(
    lecture_id: str,
    student_id: str,
    extracted_text: str,
    model_name: str,
    analysis: dict,
    analyzer_version: str = "v1"
):
    """
    Save or update Gemini lecture analysis.
    """

    if not extracted_text or not extracted_text.strip():
        raise ValueError("Extracted text cannot be empty")

    if not isinstance(analysis, dict):
        raise ValueError("Analysis must be a dictionary")

    now = datetime.now(timezone.utc)

    content_hash = calculate_content_hash(
        extracted_text
    )

    lecture_analyses_collection.update_one(
        {
            "lecture_id": str(lecture_id),
            "student_id": str(student_id)
        },
        {
            "$set": {
                "analysis": analysis,
                "content_hash": content_hash,
                "model_name": model_name,
                "analyzer_version": analyzer_version,
                "updated_at": now
            },
            "$setOnInsert": {
                "created_at": now
            }
        },
        upsert=True
    )


def get_saved_lecture_analysis(
    lecture_id: str,
    student_id: str,
    extracted_text: str,
    model_name: str,
    analyzer_version: str = "v1"
):
    """
    Return a saved analysis only if it matches
    the current lecture content, model, and
    analyzer version.
    """

    if not extracted_text or not extracted_text.strip():
        return None

    content_hash = calculate_content_hash(
        extracted_text
    )

    document = lecture_analyses_collection.find_one(
        {
            "lecture_id": str(lecture_id),
            "student_id": str(student_id),
            "content_hash": content_hash,
            "model_name": model_name,
            "analyzer_version": analyzer_version
        },
        {
            "_id": 0,
            "analysis": 1
        }
    )

    if not document:
        return None

    return document.get("analysis")



# ==========================================
# Saved Study Plans
# ==========================================

study_plans_collection = study_plan_db["study_plans"]


def serialize_study_plan(document):
    """
    Convert MongoDB dates into JSON-compatible strings.
    """

    if document is None:
        return None

    result = dict(document)
    result.pop("_id", None)

    for field in ("created_at", "updated_at"):
        value = result.get(field)

        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)

            result[field] = value.isoformat().replace(
                "+00:00", "Z"
            )

    return result


def save_study_plan(
    student_id: str,
    schedule: dict,
    generation_parameters: dict
):
    """
    Save a generated study plan in MongoDB.
    Each plan receives a unique plan_id.
    """

    if not student_id:
        raise ValueError("Student ID is required")

    if not isinstance(schedule, dict):
        raise ValueError("Schedule must be a dictionary")

    if schedule.get("status") != "ready":
        raise ValueError("Only ready plans can be saved")

    if not isinstance(schedule.get("schedule"), list):
        raise ValueError("Invalid schedule")

    if not isinstance(generation_parameters, dict):
        raise ValueError("Invalid generation parameters")

    now = datetime.now(timezone.utc)

    # Copy the schedule to avoid modifying
    # the original scheduler result.
    saved_schedule = deepcopy(schedule["schedule"])

    # Assign stable IDs to tasks for future
    # progress tracking.
    for day in saved_schedule:
        for task in day.get("tasks", []):
            task["task_id"] = str(uuid4())
            task["completion_status"] = "pending"

    document = {
        "plan_id": str(uuid4()),
        "student_id": str(student_id),
        "status": "ready",
        "start_date": schedule["start_date"],
        "total_courses": schedule["total_courses"],
        "total_required_minutes": schedule[
            "total_required_minutes"
        ],
        "schedule": saved_schedule,
        "generation_parameters": deepcopy(
            generation_parameters
        ),
        "created_at": now,
        "updated_at": now
    }

    study_plans_collection.insert_one(document)

    return serialize_study_plan(document)



def get_student_study_plans(
    student_id: str,
    limit: int = 20
):
    """
    Get saved study plans belonging to a student,
    including progress statistics.
    """

    if not student_id:
        raise ValueError("Student ID is required")

    documents = study_plans_collection.find(
        {
            "student_id": str(student_id)
        },
        {
            "_id": 0,
            "plan_id": 1,
            "status": 1,
            "start_date": 1,
            "total_courses": 1,
            "total_required_minutes": 1,
            "created_at": 1,
            "updated_at": 1,
            "schedule": 1
        }
    ).sort(
        "created_at", -1
    ).limit(limit)

    plans = []

    for document in documents:

        plan = serialize_study_plan(document)

        # Calculate progress from saved tasks
        plan["progress"] = calculate_study_plan_progress(
            plan.get("schedule", [])
        )

        # List API does not need to return all tasks
        plan.pop("schedule", None)

        plans.append(plan)

    return plans


def get_student_study_plan(
    plan_id: str,
    student_id: str
):
    """
    Get one saved study plan.

    Both plan_id and student_id must match,
    preventing access to another student's plan.
    """

    if not plan_id or not student_id:
        raise ValueError(
            "Plan ID and Student ID are required"
        )

    document = study_plans_collection.find_one(
        {
            "plan_id": str(plan_id),
            "student_id": str(student_id)
        },
        {
            "_id": 0
        }
    )
    if document is None:
        return None

    plan = serialize_study_plan(document)

    plan["progress"] = calculate_study_plan_progress(
        plan.get("schedule", [])
    )

    return plan





# ==========================================
# Study Plan Progress Tracking
# ==========================================

def update_study_task_status(
    student_id: str,
    plan_id: str,
    task_id: str,
    completion_status: str
):
    """
    Update one task's completion status.

    The plan must belong to the student,
    and the task must exist inside the plan.
    """

    allowed_statuses = {
        "pending",
        "completed",
        "missed"
    }

    if completion_status not in allowed_statuses:
        raise ValueError(
            "Invalid completion status"
        )

    if not student_id or not plan_id or not task_id:
        raise ValueError(
            "Student ID, Plan ID and Task ID are required"
        )

    now = datetime.now(timezone.utc)

    result = study_plans_collection.update_one(
        {
            "plan_id": str(plan_id),
            "student_id": str(student_id),
            "schedule.tasks.task_id": str(task_id)
        },
        {
            "$set": {
                "schedule.$[day].tasks.$[task].completion_status":
                    completion_status,
                "updated_at": now
            }
        },
        array_filters=[
            {
                "day.tasks.task_id": str(task_id)
            },
            {
                "task.task_id": str(task_id)
            }
        ]
    )

    return result.matched_count > 0



# ==========================================
# Calculate Study Plan Progress
# ==========================================


def calculate_study_plan_progress(schedule):
    """
    Calculate progress based on original tasks.

    Split tasks are grouped using source_task_id,
    so replanning does not artificially increase
    the total number of tasks.
    """

    task_groups = {}

    for day in schedule:
        for task in day.get("tasks", []):

            original_task_id = (
                task.get("source_task_id")
                or task.get("task_id")
            )

            if not original_task_id:
                continue

            completion_status = task.get(
                "completion_status", "pending"
            )

            task_groups.setdefault(
                original_task_id, []
            ).append(completion_status)

    total_tasks = len(task_groups)

    completed_tasks = 0
    pending_tasks = 0
    missed_tasks = 0

    for statuses in task_groups.values():

        # An original task is completed only when
        # all its scheduled parts are completed.
        if all(
            state == "completed"
            for state in statuses
        ):
            completed_tasks += 1

        elif "missed" in statuses:
            missed_tasks += 1

        else:
            pending_tasks += 1

    completion_percentage = (
        round(
            completed_tasks / total_tasks * 100,
            2
        )
        if total_tasks else 0
    )

    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "missed_tasks": missed_tasks,
        "completion_percentage": completion_percentage
    }





# ==========================================
# Save Adaptive Replanning Result
# ==========================================

def save_replanned_study_plan(
    student_id: str,
    original_plan: dict,
    replan_result: dict
):
    """
    Save a replanned schedule only if the
    original plan has not changed.

    Preserves the original plan_id,
    completed tasks and progress information.
    """

    if replan_result.get("status") != "ready":
        raise ValueError(
            "Only ready replanning results can be saved"
        )

    plan_id = original_plan.get("plan_id")

    if (
        not plan_id
        or str(original_plan.get("student_id")) != str(student_id)
        or str(replan_result.get("plan_id")) != str(plan_id)
    ):
        raise ValueError("Plan identity mismatch")

    # Original version used for concurrency protection
    try:
        expected_updated_at = datetime.fromisoformat(
            original_plan["updated_at"].replace(
                "Z", "+00:00"
            )
        )
    except (KeyError, ValueError, TypeError):
        raise ValueError("Invalid original plan timestamp")

    new_schedule = deepcopy(
        replan_result.get("schedule")
    )

    if not isinstance(new_schedule, list):
        raise ValueError("Invalid replanned schedule")

    # Validate task IDs, statuses and total durations
    seen_task_ids = set()
    total_minutes = 0

    for day in new_schedule:

        if not isinstance(day, dict):
            raise ValueError("Invalid schedule day")

        day_minutes = 0

        for task in day.get("tasks", []):

            task_id = task.get("task_id")
            duration = task.get("duration_minutes")
            task_status = task.get("completion_status")

            if not task_id or task_id in seen_task_ids:
                raise ValueError(
                    "Duplicate or missing task ID"
                )

            if type(duration) is not int or duration <= 0:
                raise ValueError("Invalid task duration")

            if task_status not in {
                "pending", "completed", "missed"
            }:
                raise ValueError("Invalid task status")

            seen_task_ids.add(task_id)
            day_minutes += duration

        if day_minutes != day.get("total_minutes"):
            raise ValueError("Invalid daily total")

        total_minutes += day_minutes

    if total_minutes != original_plan.get(
        "total_required_minutes"
    ):
        raise ValueError(
            "Replanned minutes do not match original plan"
        )

    daily_minutes = replan_result.get(
        "daily_study_minutes"
    )

    if (
        type(daily_minutes) is not int
        or not 5 <= daily_minutes <= 1440
    ):
        raise ValueError("Invalid daily study minutes")

    now = datetime.now(timezone.utc)

    # Atomically save only if the plan hasn't
    # been modified since it was read.
    updated_document = study_plans_collection.find_one_and_update(
        {
            "plan_id": str(plan_id),
            "student_id": str(student_id),
            "updated_at": expected_updated_at
        },
        {
            "$set": {
                "schedule": new_schedule,
                "generation_parameters.daily_study_minutes":
                    daily_minutes,
                "updated_at": now
            },
            "$push": {
                "replan_history": {
                    "replan_date": replan_result[
                        "replan_date"
                    ],
                    "remaining_minutes": replan_result[
                        "remaining_minutes"
                    ],
                    "daily_study_minutes": daily_minutes,
                    "saved_at": now
                }
            }
        },
        return_document=ReturnDocument.AFTER
    )

    if updated_document is None:
        return None

    saved_plan = serialize_study_plan(
        updated_document
    )

    saved_plan["progress"] = calculate_study_plan_progress(
        saved_plan.get("schedule", [])
    )

    return saved_plan
