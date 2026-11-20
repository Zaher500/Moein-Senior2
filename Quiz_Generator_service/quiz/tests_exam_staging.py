import uuid
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from quiz.services.exam_staging import (
    stage_exam_lecture_file,
    open_staged_exam_lecture_file,
    cleanup_exam_staging,
)


class ExamStagingTests(SimpleTestCase):

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.staging_root = (
            Path(self.temp_dir.name) / "staging"
        )

        patcher = patch(
            "quiz.services.exam_staging.STAGING_ROOT",
            self.staging_root,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.quiz_id = str(uuid.uuid4())
        self.lecture_id = str(uuid.uuid4())

    def test_stage_and_read_pdf(self):
        content = b"%PDF-1.4 test content"

        path = stage_exam_lecture_file(
            self.quiz_id,
            self.lecture_id,
            BytesIO(content),
            "lecture.pdf",
        )

        self.assertTrue(path.exists())

        file_obj, filename = open_staged_exam_lecture_file(
            self.quiz_id,
            self.lecture_id,
        )

        with file_obj:
            self.assertEqual(file_obj.read(), content)

        self.assertEqual(
            filename,
            f"{self.lecture_id}.pdf",
        )

    def test_invalid_identifier_rejected(self):
        with self.assertRaises(ValueError):
            stage_exam_lecture_file(
                "../../invalid",
                self.lecture_id,
                BytesIO(b"content"),
                "lecture.pdf",
            )

    def test_unsupported_extension_rejected(self):
        with self.assertRaises(ValueError):
            stage_exam_lecture_file(
                self.quiz_id,
                self.lecture_id,
                BytesIO(b"content"),
                "lecture.exe",
            )

    def test_empty_file_rejected(self):
        with self.assertRaises(ValueError):
            stage_exam_lecture_file(
                self.quiz_id,
                self.lecture_id,
                BytesIO(b""),
                "lecture.pdf",
            )

    def test_file_exceeding_size_limit_rejected(self):
        with patch(
            "quiz.services.exam_staging.MAX_STAGED_FILE_BYTES",
            4,
        ):
            with self.assertRaisesRegex(
                ValueError,
                "exceeds maximum allowed size",
            ):
                stage_exam_lecture_file(
                    self.quiz_id,
                    self.lecture_id,
                    BytesIO(b"12345"),
                    "lecture.pdf",
                )

        directory = self.staging_root / self.quiz_id

        self.assertEqual(
            list(directory.iterdir()) if directory.exists() else [],
            [],
        )
    def test_non_seekable_stream(self):
        class NonSeekableStream(BytesIO):
            def seekable(self):
                return False

            def seek(self, *args, **kwargs):
                raise AssertionError(
                    "seek() must not be called"
                )

        content = b"%PDF-1.4 streamed content"

        path = stage_exam_lecture_file(
            self.quiz_id,
            self.lecture_id,
            NonSeekableStream(content),
            "lecture.pdf",
        )

        self.assertTrue(path.exists())

        file_obj, filename = open_staged_exam_lecture_file(
            self.quiz_id,
            self.lecture_id,
        )

        with file_obj:
            self.assertEqual(file_obj.read(), content)

        self.assertEqual(
            filename,
            f"{self.lecture_id}.pdf",
        )
    def test_cleanup_removes_exam_files(self):
        path = stage_exam_lecture_file(
            self.quiz_id,
            self.lecture_id,
            BytesIO(b"content"),
            "lecture.pdf",
        )

        cleanup_exam_staging(self.quiz_id)

        self.assertFalse(path.exists())
        self.assertFalse(path.parent.exists())
