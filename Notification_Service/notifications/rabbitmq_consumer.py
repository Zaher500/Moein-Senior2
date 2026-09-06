import json
import pika

from .utils import send_email_otp


MAX_RETRIES = 3


def callback(ch, method, properties, body):
    data = None

    try:
        data = json.loads(body)

        email = data.get("email")
        otp = data.get("otp")
        retry_count = data.get("retry_count", 0)

        print(f"Received OTP for {email} | Retry: {retry_count}")

        send_email_otp(email, otp)

        # Successfully processed
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print("Error:", str(e))

        # If the message itself is invalid JSON, there is nothing useful to retry.
        if not isinstance(data, dict):
            print("Invalid OTP message format. Message discarded.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        retry_count = data.get("retry_count", 0)

        if retry_count < MAX_RETRIES:
            data["retry_count"] = retry_count + 1

            ch.basic_publish(
                exchange="",
                routing_key="send_otp_queue",
                body=json.dumps(data),
            )

            print(f"Retrying... ({retry_count + 1})")

        else:
            ch.basic_publish(
                exchange="",
                routing_key="send_otp_failed_queue",
                body=json.dumps(data),
            )

            print("Sent to Dead Letter Queue")

        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consuming():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host="localhost")
    )
    channel = connection.channel()

    channel.queue_declare(queue="send_otp_queue")
    channel.queue_declare(queue="send_otp_failed_queue")

    channel.basic_consume(
        queue="send_otp_queue",
        on_message_callback=callback,
        auto_ack=False,
    )

    print("Waiting for messages...")
    channel.start_consuming()