import json
import os
import time
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "stt_service.settings",
)

import django

django.setup()

import pika
from django.conf import settings
from stt.summarizer import summarize_transcript
from stt.mongo_store import (
    get_job_for_summary,
    update_summary_status,
    mark_summary_failed,
    save_summary_result,
)


def callback(
    ch,
    method,
    properties,
    body,
):

    job_id = None

    try:

        message = json.loads(body)

        job_id = message["job_id"]

        print("==========================================")
        print("Received summary job")
        print(f"Job ID: {job_id}")
        print("==========================================")

        # ----------------------------------
        # Mark summary processing
        # ----------------------------------

        update_summary_status(
            job_id,
            "processing",
        )

        # ----------------------------------
        # Load cleaned transcript from Mongo
        # ----------------------------------

        job = get_job_for_summary(
            job_id
        )

        if not job:

            raise ValueError(
                f"STT job not found: {job_id}"
            )

        cleaned_transcript = (
            job.get(
                "cleaned_transcript",
                ""
            )
            or ""
        ).strip()

        if not cleaned_transcript:

            raise ValueError(
                "Cleaned transcript is empty"
            )

        # ----------------------------------
        # Temporary test only
        # ----------------------------------

        print("==========================================")
        print("Cleaned transcript loaded successfully")
        print(
            f"Transcript chars: "
            f"{len(cleaned_transcript)}"
        )
        print("==========================================")


        # ----------------------------------
        # Summarize transcript
        # ----------------------------------

        summary = summarize_transcript(
            cleaned_transcript
        )


        # ----------------------------------
        # Save summary to MongoDB
        # ----------------------------------

        save_summary_result(
            job_id=job_id,
            summary=summary,
        )


        print("==========================================")
        print(
            f"Summary completed for: "
            f"{job_id}"
        )
        print(
            f"Summary chars: "
            f"{len(summary)}"
        )
        print("==========================================")


        ch.basic_ack(
            delivery_tag=method.delivery_tag
        )

    except Exception as e:

        print("==========================================")
        print(
            f"Summary consumer error: {e}"
        )
        print("==========================================")

        if job_id:

            try:

                mark_summary_failed(
                    job_id,
                    str(e),
                )

            except Exception as mongo_error:

                print(
                    f"Failed to update summary "
                    f"status: {mongo_error}"
                )

        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False,
        )


def start_summary_consumer():

    while True:

        try:

            connection = (
                pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=settings.RABBITMQ_HOST,
                        heartbeat=600,
                        blocked_connection_timeout=300,
                    )
                )
            )

            channel = (
                connection.channel()
            )

            channel.queue_declare(
                queue=(
                    settings
                    .RABBITMQ_SUMMARY_QUEUE
                ),
                durable=True,
            )

            channel.basic_qos(
                prefetch_count=1
            )

            channel.basic_consume(
                queue=(
                    settings
                    .RABBITMQ_SUMMARY_QUEUE
                ),
                on_message_callback=callback,
                auto_ack=False,
            )

            print(
                "Waiting for summary jobs..."
            )

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
    start_summary_consumer()