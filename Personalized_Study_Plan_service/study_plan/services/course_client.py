
import requests

from uuid import UUID
from django.conf import settings


def get_verified_course_lectures(
    course_id: str,
    lecture_ids: list[str],
    access_token: str
):
    """
    Fetch a student's course and validate
    the selected lectures through API Gateway.
    """

    # 1. Validate input
    try:
        course_id = str(UUID(str(course_id)))

        selected_ids = [
            str(UUID(str(lecture_id)))
            for lecture_id in lecture_ids
        ]

    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid course or lecture ID")

    if not selected_ids:
        raise ValueError("Select at least one lecture")

    if len(selected_ids) != len(set(selected_ids)):
        raise ValueError("Duplicate lecture IDs")

    if not access_token:
        raise ValueError("Access token is required")

    # 2. Request course lectures through Gateway
    gateway_url = settings.GATEWAY_BASE_URL.rstrip("/")

    url = (
        f"{gateway_url}/api/courses/"
        f"{course_id}/lectures/"
    )

    response = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=20
    )

    # 3. Check authentication and ownership
    if response.status_code in (401, 403, 404):
        raise ValueError(
            "Course not found or access denied"
        )

    if not response.ok:
        raise RuntimeError(
            "Courses service is unavailable"
        )

    data = response.json()

    course = data.get("course", {})
    available_lectures = data.get("lectures", [])

    if str(course.get("course_id")) != course_id:
        raise ValueError("Course identity mismatch")

    if not isinstance(available_lectures, list):
        raise ValueError("Invalid lectures response")

    # 4. Index available lectures
    lecture_map = {
        str(lecture["lecture_id"]): lecture
        for lecture in available_lectures
    }

    # 5. Validate selected lectures
    verified_lectures = []

    for lecture_id in selected_ids:

        lecture = lecture_map.get(lecture_id)

        if lecture is None:
            raise ValueError(
                f"Lecture not found in selected course: "
                f"{lecture_id}"
            )

        verified_lectures.append({
            "lecture_id": lecture_id,
            "lecture_name": lecture["lecture_name"]
        })

    # 6. Return trusted course information
    return {
        "course_id": course_id,
        "course_name": course["course_name"],
        "lectures": verified_lectures
    }
