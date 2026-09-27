import os
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .mongo_store import create_stt_job, get_job_by_id ,get_summary_by_job_id
from .producer import send_job_to_queue
from .auth_helpers import get_user_from_headers


@csrf_exempt
def upload_audio_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    user_data = get_user_from_headers(request)
    student_id = user_data.get("student_id")
    user_id = user_data.get("user_id")

    if not student_id:
        return JsonResponse({"error": "Missing student ID"}, status=400)

    if not user_id:
        return JsonResponse({"error": "Missing user ID"}, status=400)

    audio_file = request.FILES.get("audio")
    if not audio_file:
        return JsonResponse({"error": "No audio file provided"}, status=400)

    job_id = str(uuid.uuid4())

    file_extension = os.path.splitext(audio_file.name)[1]
    stored_file_name = f"{job_id}{file_extension}"

    upload_dir = settings.MEDIA_ROOT / "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    saved_file_path = upload_dir / stored_file_name

    with open(saved_file_path, "wb+") as destination:
        for chunk in audio_file.chunks():
            destination.write(chunk)

    job_data = {
        "job_id": job_id,
        "student_id": student_id,
        "user_id": user_id,
        "local_file_path": str(saved_file_path),
        "original_file_name": audio_file.name,
    }

    create_stt_job(
        job_id=job_id,
        student_id=student_id,
        user_id=user_id,
        original_file_name=audio_file.name,
        local_file_path=str(saved_file_path),
    )

    send_job_to_queue(job_data)

    print("==========================================")
    print("Audio uploaded successfully")
    print(f" Job ID: {job_id}")
    print(f" User ID: {user_id}")
    print(f" Student ID: {student_id}")
    print(f" Original file name: {audio_file.name}")
    print(f" Saved locally at: {saved_file_path}")
    print("Job sent to RabbitMQ successfully")
    print("==========================================")

    return JsonResponse({
        "message": "Audio uploaded and job queued successfully",
        "job_id": job_id,
        "user_id": user_id,
        "student_id": student_id,
    }, status=202)

def get_transcript_status_view(request, job_id):
    if request.method != "GET":
        return JsonResponse({"error": "Only GET method allowed"}, status=405)

    user_data = get_user_from_headers(request)
    student_id = user_data.get("student_id")

    if not student_id:
        return JsonResponse({"error": "Missing student ID"}, status=400)

    job = get_job_by_id(job_id, student_id)

    if not job:
        return JsonResponse({"error": "Job not found"}, status=404)

    return JsonResponse(job, status=200)




def get_summary_view(request, job_id):

    if request.method != "GET":
        return JsonResponse(
            {"error": "Only GET method allowed"},
            status=405
        )

    # Get student identity
    user_data = get_user_from_headers(request)
    student_id = user_data.get("student_id")

    if not student_id:
        return JsonResponse(
            {"error": "Missing student ID"},
            status=401
        )

    # Retrieve summary from MongoDB
    job = get_summary_by_job_id(job_id, student_id)

    if not job:
        return JsonResponse(
            {"error": "Job not found"},
            status=404
        )

    summary_status = job.get("summary_status", "not_started")

    response_data = {
        "job_id": job_id,
        "summary_status": summary_status,
    }

    # Summary is ready
    if summary_status == "completed":

        response_data["summary"] = job.get("summary", "")

    # Summary generation failed
    elif summary_status == "failed":

        response_data["message"] = "Summary generation failed"

    # Summary is not ready yet
    elif summary_status in ["not_started", "queued", "processing"]:

        response_data["message"] = "Summary is not ready yet"

    else:

        response_data["message"] = "Unknown summary status"

    return JsonResponse(response_data, status=200)