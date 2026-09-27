import json

import pika
from django.conf import settings


def send_summary_job_to_queue(job_id: str):

    payload = {
        "job_id": job_id,
    }

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST
        )
    )

    try:

        channel = connection.channel()

        channel.queue_declare(
            queue=settings.RABBITMQ_SUMMARY_QUEUE,
            durable=True,
        )

        channel.basic_publish(
            exchange="",
            routing_key=settings.RABBITMQ_SUMMARY_QUEUE,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=2
            ),
        )

        print(
            f"Summary job queued successfully: {job_id}"
        )

    finally:

        if connection.is_open:
            connection.close()