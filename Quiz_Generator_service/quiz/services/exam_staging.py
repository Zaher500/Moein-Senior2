import shutil
import tempfile
import uuid
from pathlib import Path


STAGING_ROOT = (
    Path(tempfile.gettempdir())
    / "moein_quiz_exam_staging"
)

SUPPORTED_EXTENSIONS = {".pdf", ".docx"}
MAX_STAGED_FILE_BYTES = 50 * 1024 * 1024


def _canonical_uuid(value):
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid staging identifier") from exc


def _exam_directory(quiz_id):
    return STAGING_ROOT / _canonical_uuid(quiz_id)


def stage_exam_lecture_file(
    quiz_id,
    lecture_id,
    file_obj,
    filename,
):
    lecture_id = _canonical_uuid(lecture_id)
    extension = Path(str(filename)).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported exam file format: {extension}"
        )

    directory = _exam_directory(quiz_id)
    directory.mkdir(parents=True, exist_ok=True)

    destination = directory / f"{lecture_id}{extension}"
    temporary_path = None

    try:
        seekable = getattr(file_obj, "seekable", None)

        if callable(seekable) and seekable():
            file_obj.seek(0)

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=directory,
            prefix=".upload-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

            total_bytes = 0

            while True:
                chunk = file_obj.read(1024 * 1024)

                if not chunk:
                    break

                total_bytes += len(chunk)

                if total_bytes > MAX_STAGED_FILE_BYTES:
                    raise ValueError(
                        "Lecture file exceeds maximum allowed size"
                    )

                temporary_file.write(chunk)

        if temporary_path.stat().st_size == 0:
            raise ValueError("Lecture file is empty")

        temporary_path.replace(destination)
        return destination

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def open_staged_exam_lecture_file(quiz_id, lecture_id):
    lecture_id = _canonical_uuid(lecture_id)
    directory = _exam_directory(quiz_id)

    candidates = [
        directory / f"{lecture_id}{extension}"
        for extension in SUPPORTED_EXTENSIONS
    ]

    existing = [
        path for path in candidates if path.is_file()
    ]

    if len(existing) != 1:
        raise FileNotFoundError(
            f"Expected one staged file for lecture {lecture_id}"
        )

    file_path = existing[0]
    return file_path.open("rb"), file_path.name


def cleanup_exam_staging(quiz_id):
    directory = _exam_directory(quiz_id)

    if directory.exists():
        shutil.rmtree(directory)
