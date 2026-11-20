import uuid
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from quiz.services.exam_course_loader import (
    stage_course_lecture_file,
)


class ExamCourseLoaderTests(SimpleTestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.staging_root = Path(self.temp_dir.name) / "staging"

        patcher = patch(
            "quiz.services.exam_staging.STAGING_ROOT",
            self.staging_root,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.quiz_id = str(uuid.uuid4())
        self.lecture_id = str(uuid.uuid4())

        self.request = SimpleNamespace(
            headers={
                "X-Student-ID": str(uuid.uuid4()),
                "Authorization": "Bearer test-token",
            }
        )

    def make_response(
        self,
        status=200,
        content=b"%PDF-1.4 test",
        headers=None,
    ):
        response = requests.Response()
        response.status_code = status
        response.headers.update(headers or {})
        response.raw = BytesIO(content)
        return response

    def test_successful_file_download(self):
        response = self.make_response(
            headers={
                "Content-Disposition":
                    'attachment; filename="lecture.pdf"',
            }
        )

        with patch(
            "quiz.services.exam_course_loader.requests.get",
            return_value=response,
        ) as mock_get:
            path = stage_course_lecture_file(
                self.request,
                self.quiz_id,
                self.lecture_id,
            )

        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), b"%PDF-1.4 test")

        kwargs = mock_get.call_args.kwargs

        self.assertTrue(kwargs["stream"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (5, 60))
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer test-token",
        )

    def test_content_type_fallback(self):
        response = self.make_response(
            headers={"Content-Type": "application/pdf"}
        )

        with patch(
            "quiz.services.exam_course_loader.requests.get",
            return_value=response,
        ):
            path = stage_course_lecture_file(
                self.request,
                self.quiz_id,
                self.lecture_id,
            )

        self.assertEqual(path.suffix, ".pdf")

    def test_redirect_rejected(self):
        response = self.make_response(status=302)

        with patch(
            "quiz.services.exam_course_loader.requests.get",
            return_value=response,
        ):
            with self.assertRaises(RuntimeError):
                stage_course_lecture_file(
                    self.request,
                    self.quiz_id,
                    self.lecture_id,
                )

    def test_oversized_file_rejected(self):
        response = self.make_response(content=b"12345", headers={"Content-Type": "application/pdf"})

        with patch(
            "quiz.services.exam_course_loader.requests.get",
            return_value=response,
        ), patch(
            "quiz.services.exam_staging.MAX_STAGED_FILE_BYTES",
            4,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "exceeds maximum allowed size",
            ):
                stage_course_lecture_file(
                    self.request,
                    self.quiz_id,
                    self.lecture_id,
                )

        directory = self.staging_root / self.quiz_id
        self.assertFalse(
            directory.exists() and any(directory.iterdir())
        )

    def test_missing_student_id_rejected(self):
        request = SimpleNamespace(headers={})

        with patch(
            "quiz.services.exam_course_loader.requests.get"
        ) as mock_get:
            with self.assertRaises(ValueError):
                stage_course_lecture_file(
                    request,
                    self.quiz_id,
                    self.lecture_id,
                )

            mock_get.assert_not_called()

    def test_connection_timeout(self):
        with patch(
            "quiz.services.exam_course_loader.requests.get",
            side_effect=requests.Timeout,
        ):
            with self.assertRaises(requests.Timeout):
                stage_course_lecture_file(
                    self.request,
                    self.quiz_id,
                    self.lecture_id,
                )
