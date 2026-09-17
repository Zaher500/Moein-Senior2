import json
import os
import time

import pika
from django.conf import settings
from faster_whisper import WhisperModel

from stt.mongo_store import (
    update_job_status,
    save_job_result,
    mark_job_failed,
)

from stt.ai_cleanup import clean_long_transcript_with_qwen_client
from stt.notification_producer import send_notification


# ==============================
# Environment setup
# ==============================
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


# ==============================
# STT Settings
# ==============================

LANGUAGE = "ar"

BEAM_SIZE = 3

DEVICE = "cuda"
COMPUTE_TYPE = "int8_float16"

VAD_MIN_SILENCE_MS = 500


# مؤقتاً للتأكد من الـ STT لحاله
ENABLE_QWEN_CLEANUP = True


# ==============================
# Load Whisper model once
# ==============================

print("==========================================")
print("Loading faster-whisper model...")
print("Model: large-v3")
print(f"Device: {DEVICE}")
print(f"Compute type: {COMPUTE_TYPE}")
print(f"Beam size: {BEAM_SIZE}")
print(f"Language: {LANGUAGE}")
print(f"VAD silence: {VAD_MIN_SILENCE_MS} ms")
print("==========================================")


model_load_start = time.time()

model = WhisperModel(
    "large-v3",
    device=DEVICE,
    compute_type=COMPUTE_TYPE,
    download_root="models",
)

model_load_time = time.time() - model_load_start

print(
    f"faster-whisper model loaded "
    f"in {model_load_time:.2f} seconds"
)


# ==============================
# Speech-to-text
# ==============================

def transcribe_audio(local_file_path: str) -> str:

    print("==========================================")
    print("Starting transcription...")
    print(f"Audio: {local_file_path}")
    print("==========================================")

    transcription_start = time.time()

    # نعطي Whisper الملف الأصلي مباشرة
    # بدون preprocessing
    segments, info = model.transcribe(
        local_file_path,

        language=LANGUAGE,

        beam_size=BEAM_SIZE,

        vad_filter=True,

        vad_parameters=dict(
            min_silence_duration_ms=VAD_MIN_SILENCE_MS
        ),

        word_timestamps=False,
    )

    texts = []
    segment_count = 0

    # مهم:
    # faster-whisper بيرجع generator
    # والمعالجة الفعلية بتصير أثناء iteration
    for segment in segments:

        text = (segment.text or "").strip()

        if not text:
            continue

        texts.append(text)
        segment_count += 1

    raw_transcript = " ".join(texts).strip()

    transcription_time = (
        time.time() - transcription_start
    )

    print("==========================================")
    print("Transcription finished")
    print(f"Language: {info.language}")
    print(
        f"Language probability: "
        f"{info.language_probability:.4f}"
    )
    print(f"Segments: {segment_count}")
    print(
        f"Transcription time: "
        f"{transcription_time:.2f} seconds"
    )
    print("==========================================")

    return raw_transcript


# ==============================
# Full processing pipeline
# ==============================

def process_audio_job(local_file_path: str) -> dict:

    # 1. Whisper
    raw_transcript = transcribe_audio(
        local_file_path
    )

    # 2. Qwen
    #
    # مؤقتاً موقفينه حتى نتأكد أن
    # Whisper + RabbitMQ + Mongo شغالين صح.
    #
    if ENABLE_QWEN_CLEANUP:

        print("Starting Qwen cleanup...")

        cleaned_transcript = (
            clean_long_transcript_with_qwen_client(
                raw_transcript
            )
        )

        print("Qwen cleanup completed")

    else:

        print(
            "Qwen cleanup disabled "
            "- using raw transcript"
        )

        cleaned_transcript = raw_transcript

    return {
        "raw_transcript": raw_transcript,
        "cleaned_transcript": cleaned_transcript,
    }


# ==============================
# Helper for notifications
# ==============================

def safe_send_notification(
    user_id,
    message,
    notif_type,
):

    try:

        send_notification(
            user_id,
            message,
            notif_type,
        )

    except Exception as e:

        print(
            f"Notification failed: {e}"
        )


# ==============================
# RabbitMQ callback
# ==============================

def callback(
    ch,
    method,
    properties,
    body,
):

    job_id = None
    user_id = None

    try:

        message = json.loads(body)

        job_id = message["job_id"]

        local_file_path = (
            message["local_file_path"]
        )

        original_file_name = message.get(
            "original_file_name",
            "unknown",
        )

        user_id = message.get("user_id")

        # ----------------------------------
        # Mark processing
        # ----------------------------------

        update_job_status(
            job_id,
            "processing",
        )

        if user_id:

            safe_send_notification(
                user_id,
                "the audio is processing",
                "transcribe",
            )

        print("==========================================")
        print("Received job from RabbitMQ")
        print(f"Job ID: {job_id}")
        print(
            f"Original file name: "
            f"{original_file_name}"
        )
        print(
            f"Local file path: "
            f"{local_file_path}"
        )
        print("==========================================")

        # ----------------------------------
        # Check audio
        # ----------------------------------

        if not os.path.exists(
            local_file_path
        ):

            raise FileNotFoundError(
                f"Audio file not found: "
                f"{local_file_path}"
            )

        # ----------------------------------
        # Process
        # ----------------------------------

        result = process_audio_job(
            local_file_path
        )

        raw_transcript = (
            result["raw_transcript"]
        )

        cleaned_transcript = (
            result["cleaned_transcript"]
        )

        # ----------------------------------
        # Save MongoDB
        # ----------------------------------

        save_job_result(
            job_id=job_id,
            raw_transcript=raw_transcript,
            cleaned_transcript=cleaned_transcript,
        )

        # ----------------------------------
        # Notification
        # ----------------------------------

        if user_id:

            safe_send_notification(
                user_id,
                "the audio is completed",
                "transcribe",
            )

        print("==========================================")
        print(f"DONE Job: {job_id}")
        print("==========================================")

        ch.basic_ack(
            delivery_tag=method.delivery_tag
        )

    except Exception as e:

        if job_id:

            mark_job_failed(
                job_id,
                str(e),
            )

        if user_id:

            safe_send_notification(
                user_id,
                "the audio failed to process",
                "transcribe",
            )

        print("==========================================")
        print(f"ERROR: {str(e)}")
        print("==========================================")

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False,
        )


# ==============================
# Start consumer
# ==============================

def start_consumer():

    while True:

        try:

            rabbitmq_host = (
                settings.RABBITMQ_HOST
            )

            rabbitmq_queue = (
                settings.RABBITMQ_QUEUE
            )

            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=rabbitmq_host,
                    heartbeat=600,
                    blocked_connection_timeout=300,
                )
            )

            channel = connection.channel()

            channel.queue_declare(
                queue=rabbitmq_queue,
                durable=True,
            )

            # GPU عليه job واحد بنفس الوقت
            channel.basic_qos(
                prefetch_count=1
            )

            channel.basic_consume(
                queue=rabbitmq_queue,
                on_message_callback=callback,
                auto_ack=False,
            )

            print("Waiting for STT jobs...")

            channel.start_consuming()

        except AttributeError as e:

            print(
                f"Settings error: {e}"
            )

            break

        except Exception as e:

            print(
                f"RabbitMQ / runtime error: {e}"
            )

            print(
                "Reconnecting in 5 seconds..."
            )

            time.sleep(5)


if __name__ == "__main__":
    start_consumer()