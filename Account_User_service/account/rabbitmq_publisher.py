import pika
import json


def publish_otp(email, otp):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host='localhost')
        )
        channel = connection.channel()

        # create queue if not exists
        channel.queue_declare(queue='send_otp_queue')

        message = {
        "email": email,
        "otp": otp,
        "retry_count": 0   #  جديد
        }

        channel.basic_publish(
            exchange='',
            routing_key='send_otp_queue',
            body=json.dumps(message)
        )

        print("OTP sent to RabbitMQ")

        connection.close()

    except Exception as e:
        print("RabbitMQ Error:", str(e))