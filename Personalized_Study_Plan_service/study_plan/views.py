
import hmac
import logging

from datetime import date
from uuid import UUID
from django.utils import timezone
import requests
from django.conf import settings

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from study_plan.db.mongo import get_extracted_text,update_study_task_status,save_study_plan,save_replanned_study_plan
from pymongo.errors import PyMongoError

from study_plan.db.mongo import get_student_study_plans,get_student_study_plan
from study_plan.services.course_client import (
    get_verified_course_lectures
)

from study_plan.services.lecture_analyzer import (
    analyze_lecture_with_gemini
)

from study_plan.services.plan_generator import (
    prepare_multi_course_plan
)

from study_plan.services.scheduler import (
    generate_multi_course_schedule
)
from study_plan.services.replanner import (
    replan_study_plan,
)


logger = logging.getLogger(__name__)


def is_gateway_request(request):
    received_secret = request.headers.get(
        "X-GATEWAY-SECRET", ""
    )

    expected_secret = getattr(
        settings, "GATEWAY_SECRET", ""
    )

    return bool(expected_secret) and hmac.compare_digest(
        received_secret,
        expected_secret
    )


def parse_date(value, field_name):
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be YYYY-MM-DD"
        )

    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f"Invalid {field_name}. Use YYYY-MM-DD"
        )


# ----------------------------------------
# 1. Gateway Connection Test
# ----------------------------------------

@api_view(["GET"])
def test_study_plan(request):

    if not is_gateway_request(request):
        return Response(
            {"error": "Forbidden"},
            status=status.HTTP_403_FORBIDDEN
        )

    student_id = request.headers.get("X-Student-ID")

    if not student_id:
        return Response(
            {"error": "Student identity missing"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    return Response(
        {
            "message": "Study Plan Service connected successfully",
            "student_id": student_id,
            "service": "Personalized Study Plan"
        },
        status=status.HTTP_200_OK
    )


# ----------------------------------------
# 2. Generate Personalized Study Plan
# ----------------------------------------

@api_view(["POST"])
def generate_study_plan(request):

    # 1. Verify Gateway
    if not is_gateway_request(request):
        return Response(
            {"error": "Forbidden"},
            status=status.HTTP_403_FORBIDDEN
        )

    # 2. Get student identity
    try:
        student_id = str(
            UUID(request.headers.get("X-Student-ID", ""))
        )
    except (ValueError, TypeError, AttributeError):
        return Response(
            {"error": "Valid student identity required"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # 3. Get Bearer Token
    authorization = request.headers.get(
        "Authorization", ""
    )

    scheme, separator, access_token = (
        authorization.partition(" ")
    )

    if (
        scheme.lower() != "bearer"
        or not separator
        or not access_token.strip()
    ):
        return Response(
            {"error": "Bearer token required"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    access_token = access_token.strip()

    # 4. Validate request body
    data = request.data

    if not isinstance(data, dict):
        return Response(
            {"error": "JSON object required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        start_date = parse_date(
            data.get("start_date"),
            "start_date"
        )

        daily_minutes = data.get(
            "daily_study_minutes"
        )

        if (
            type(daily_minutes) is not int
            or not 5 <= daily_minutes <= 1440
        ):
            raise ValueError(
                "daily_study_minutes must be between 5 and 1440"
            )

        selected_courses = data.get("courses")

        if (
            not isinstance(selected_courses, list)
            or not selected_courses
        ):
            raise ValueError(
                "Select at least one course"
            )

        if len(selected_courses) > 10:
            raise ValueError(
                "Maximum 10 courses per request"
            )

        seen_course_ids = set()
        total_lectures = 0
        validated_courses = []

        for selected_course in selected_courses:

            if not isinstance(selected_course, dict):
                raise ValueError(
                    "Each course must be an object"
                )

            try:
                course_id = str(
                    UUID(str(selected_course.get("course_id")))
                )
            except (ValueError, TypeError, AttributeError):
                raise ValueError("Invalid course_id")

            if course_id in seen_course_ids:
                raise ValueError(
                    "Duplicate course_id"
                )

            seen_course_ids.add(course_id)

            exam_date = parse_date(
                selected_course.get("exam_date"),
                "exam_date"
            )

            if exam_date <= start_date:
                raise ValueError(
                    "Exam date must be after start_date"
                )

            knowledge_level = selected_course.get(
                "knowledge_level"
            )

            if knowledge_level not in (
                "beginner",
                "intermediate",
                "advanced"
            ):
                raise ValueError(
                    "Invalid knowledge_level"
                )

            lecture_ids = selected_course.get(
                "lecture_ids"
            )

            if (
                not isinstance(lecture_ids, list)
                or not lecture_ids
            ):
                raise ValueError(
                    "Select at least one lecture per course"
                )

            total_lectures += len(lecture_ids)

            validated_courses.append({
                "course_id": course_id,
                "lecture_ids": lecture_ids,
                "exam_date": exam_date.isoformat(),
                "knowledge_level": knowledge_level
            })

        if total_lectures > 20:
            raise ValueError(
                "Maximum 20 lectures per request"
            )

    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 5. Verify courses and analyze lectures
    prepared_courses = []

    try:
        for selected_course in validated_courses:

            verified_course = get_verified_course_lectures(
                course_id=selected_course["course_id"],
                lecture_ids=selected_course["lecture_ids"],
                access_token=access_token
            )

            analyzed_lectures = []

            for lecture in verified_course["lectures"]:

                lecture_id = lecture["lecture_id"]

                # Check whether extracted text exists
                extracted_text = get_extracted_text(
                    lecture_id=lecture_id,
                    student_id=student_id
                )

                if not extracted_text or not extracted_text.strip():
                    return Response(
                        {
                            "error": "Lecture text is not ready",
                            "lecture_id": lecture_id
                        },
                        status=status.HTTP_409_CONFLICT
                    )

                # Cached analysis or Gemini
                analysis = analyze_lecture_with_gemini(
                    lecture_id=lecture_id,
                    student_id=student_id
                )

                analyzed_lectures.append({
                    "lecture_id": lecture_id,
                    "topics": analysis["topics"]
                })

            prepared_courses.append({
                "course_id": verified_course["course_id"],
                "course_name": verified_course["course_name"],
                "exam_date": selected_course["exam_date"],
                "knowledge_level": selected_course["knowledge_level"],
                "lectures": analyzed_lectures
            })

    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )

    except (requests.RequestException, RuntimeError):
        logger.exception("Courses service request failed")
        return Response(
            {"error": "Unable to retrieve course information"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    except Exception:
        logger.exception("Lecture analysis failed")
        return Response(
            {"error": "Lecture analysis unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # 6. Prepare tasks and generate schedule
    try:
        prepared = prepare_multi_course_plan(
            courses=prepared_courses,
            start_date=start_date.isoformat(),
            daily_study_minutes=daily_minutes
        )

        if prepared["status"] == "insufficient_time":
            return Response(
                {
                    "status": "insufficient_time",
                    "message": "Not enough time before exams",
                    "deadline_checks": prepared.get(
                        "deadline_checks", []
                    )
                },
                status=status.HTTP_200_OK
            )

        if prepared["status"] != "prepared":
            raise ValueError(
                "Unexpected plan preparation status"
            )


        schedule = generate_multi_course_schedule(
            prepared
        )

        # Save the generated plan only if ready
        if schedule.get("status") != "ready":
            return Response(
                {
                    "error": "Study plan is not ready",
                    "schedule_status": schedule.get("status")
                },
                status=status.HTTP_409_CONFLICT
            )

        # Save the parameters used to generate the plan
        generation_parameters = {
            "start_date": start_date.isoformat(),
            "daily_study_minutes": daily_minutes,
            "courses": validated_courses
        }

        # Save study plan in MongoDB
        saved_plan = save_study_plan(
            student_id=student_id,
            schedule=schedule,
            generation_parameters=generation_parameters
        )

        # Return the saved plan with its unique ID
        return Response(
            saved_plan,
            status=status.HTTP_201_CREATED
        )


    except (ValueError, KeyError, TypeError):
        logger.exception("Study plan generation failed")
        return Response(
            {"error": "Unable to generate study plan"},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception:
        logger.exception("Study plan scheduler failed")
        return Response(
            {"error": "Study plan service unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )




# ----------------------------------------
# 3. Get My Saved Study Plans
# ----------------------------------------

@api_view(["GET"])
def list_study_plans(request):

    if not is_gateway_request(request):
        return Response(
            {"error": "Forbidden"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        student_id = str(
            UUID(request.headers.get("X-Student-ID", ""))
        )
    except (ValueError, TypeError, AttributeError):
        return Response(
            {"error": "Valid student identity required"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        plans = get_student_study_plans(
            student_id=student_id
        )

        return Response(
            {
                "count": len(plans),
                "plans": plans
            },
            status=status.HTTP_200_OK
        )

    except PyMongoError:
        logger.exception("Failed to retrieve study plans")
        return Response(
            {"error": "Unable to retrieve study plans"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


# ----------------------------------------
# 4. Get One Saved Study Plan
# ----------------------------------------

@api_view(["GET"])
def study_plan_detail(request, plan_id):

    if not is_gateway_request(request):
        return Response(
            {"error": "Forbidden"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        student_id = str(
            UUID(request.headers.get("X-Student-ID", ""))
        )
    except (ValueError, TypeError, AttributeError):
        return Response(
            {"error": "Valid student identity required"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    try:
        plan = get_student_study_plan(
            plan_id=str(plan_id),
            student_id=student_id
        )

        if plan is None:
            return Response(
                {"error": "Study plan not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            plan,
            status=status.HTTP_200_OK
        )

    except PyMongoError:
        logger.exception("Failed to retrieve study plan")
        return Response(
            {"error": "Unable to retrieve study plan"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )



# ----------------------------------------
# 5. Update Study Task Progress
# ----------------------------------------

@api_view(["PATCH"])
def update_study_task(request, plan_id, task_id):

    # 1. Verify request comes from Gateway
    if not is_gateway_request(request):
        return Response(
            {"error": "Forbidden"},
            status=status.HTTP_403_FORBIDDEN
        )

    # 2. Get student identity
    try:
        student_id = str(
            UUID(request.headers.get("X-Student-ID", ""))
        )
    except (ValueError, TypeError, AttributeError):
        return Response(
            {"error": "Valid student identity required"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # 3. Validate request body
    if not isinstance(request.data, dict):
        return Response(
            {"error": "JSON object required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    completion_status = request.data.get(
        "completion_status"
    )

    allowed_statuses = {
        "pending",
        "completed",
        "missed"
    }

    if completion_status not in allowed_statuses:
        return Response(
            {
                "error": "Invalid completion_status",
                "allowed_values": sorted(allowed_statuses)
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # 4. Update task in MongoDB
    try:
        updated = update_study_task_status(
            student_id=student_id,
            plan_id=str(plan_id),
            task_id=str(task_id),
            completion_status=completion_status
        )

        if not updated:
            return Response(
                {"error": "Study plan or task not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "message": "Task status updated successfully",
                "plan_id": str(plan_id),
                "task_id": str(task_id),
                "completion_status": completion_status
            },
            status=status.HTTP_200_OK
        )

    except PyMongoError:
        logger.exception("Failed to update study task")
        return Response(
            {"error": "Unable to update task"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )




# ----------------------------------------
# 6. Adaptive Study Plan Replanning
# ----------------------------------------

@api_view(["POST"])
def replan_saved_study_plan(request, plan_id):

    # 1. Verify request comes from Gateway
    if not is_gateway_request(request):
        return Response(
            {"error": "Forbidden"},
            status=status.HTTP_403_FORBIDDEN
        )

    # 2. Get student identity
    try:
        student_id = str(
            UUID(request.headers.get("X-Student-ID", ""))
        )
    except (ValueError, TypeError, AttributeError):
        return Response(
            {"error": "Valid student identity required"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # 3. Validate optional daily study minutes
    if not isinstance(request.data, dict):
        return Response(
            {"error": "JSON object required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    daily_minutes = request.data.get(
        "daily_study_minutes"
    )

    if daily_minutes is not None:
        if (
            type(daily_minutes) is not int
            or not 5 <= daily_minutes <= 1440
        ):
            return Response(
                {
                    "error":
                    "daily_study_minutes must be between 5 and 1440"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    try:
        # 4. Retrieve the student's saved plan
        plan = get_student_study_plan(
            plan_id=str(plan_id),
            student_id=student_id
        )

        if plan is None:
            return Response(
                {"error": "Study plan not found"},
                status=status.HTTP_404_NOT_FOUND
            )


        # 5. Get replanning date from request
        requested_date = request.data.get("replan_date")

        if requested_date is None:
            replan_date = timezone.localdate().isoformat()
        else:
            if not isinstance(requested_date, str):
                return Response(
                    {"error": "replan_date must be a valid date in YYYY-MM-DD format"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                replan_date = date.fromisoformat(
                    requested_date
                ).isoformat()
            except ValueError:
                return Response(
                    {"error": "Invalid replan_date. Use YYYY-MM-DD"},
                    status=status.HTTP_400_BAD_REQUEST
                )


        # 6. Generate replanned schedule
        replanned = replan_study_plan(
            plan=plan,
            replan_date=replan_date,
            daily_study_minutes=daily_minutes
        )

        # 7. Handle insufficient time
        if replanned["status"] == "insufficient_time":
            return Response(
                {
                    "status": "insufficient_time",
                    "message": "Not enough time before exams",
                    "deadline_checks": replanned.get(
                        "deadline_checks", []
                    )
                },
                status=status.HTTP_409_CONFLICT
            )

        if replanned["status"] != "ready":
            raise ValueError(
                "Unexpected replanning status"
            )

        # 8. Save the updated schedule
        saved_plan = save_replanned_study_plan(
            student_id=student_id,
            original_plan=plan,
            replan_result=replanned
        )

        # 9. Handle concurrent modifications
        if saved_plan is None:
            return Response(
                {
                    "error":
                    "Study plan was modified. Please retry."
                },
                status=status.HTTP_409_CONFLICT
            )

        # 10. Return saved result
        return Response(
            {
                "message": "Study plan replanned successfully",
                "plan": saved_plan
            },
            status=status.HTTP_200_OK
        )

    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )

    except PyMongoError:
        logger.exception("Replanning database error")
        return Response(
            {"error": "Database unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    except Exception:
        logger.exception("Adaptive replanning failed")
        return Response(
            {"error": "Unable to replan study plan"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
