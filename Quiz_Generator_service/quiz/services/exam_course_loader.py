import os
from email.message import Message

import requests

from .exam_staging import stage_exam_lecture_file


CONTENT_TYPE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def stage_course_lecture_file(request, quiz_id, lecture_id):
    base_url = os.getenv(
        "COURSE_SERVICE_URL",
        "http://localhost:8002",
    ).rstrip("/")

    url = f"{base_url}/api/lectures/{lecture_id}/file/"

    student_id = request.headers.get("X-Student-ID")

    if not student_id:
        raise ValueError("X-Student-ID is required")

    headers = {
        "X-Student-ID": student_id,
    }

    authorization = request.headers.get("Authorization")

    if authorization:
        headers["Authorization"] = authorization

    with requests.get(
        url,
        headers=headers,
        stream=True,
        timeout=(5, 60),
        allow_redirects=False,
    ) as response:
        if response.status_code != 200:
            raise RuntimeError(
                "Course Service did not return a lecture file"
            )

        disposition = Message()
        disposition["Content-Disposition"] = (
            response.headers.get("Content-Disposition", "")
        )

        filename = disposition.get_filename()

        if not filename:
            content_type = response.headers.get(
                "Content-Type",
                "",
            ).split(";", 1)[0].strip().lower()

            extension = CONTENT_TYPE_EXTENSIONS.get(content_type)

            if not extension:
                raise ValueError(
                    "Course Service returned an unidentified file type"
                )

            filename = f"{lecture_id}{extension}"

        response.raw.decode_content = True

        return stage_exam_lecture_file(
            quiz_id=quiz_id,
            lecture_id=lecture_id,
            file_obj=response.raw,
            filename=filename,
        )
