import pika
import json
import uuid
import threading
import os

from .in_memory_store import notifications_store


def callback(ch, method, properties, body):
    try:
        data = json.loads(body)

        user_id = str(data.get("user_id"))
        message = data.get("message")
        type_ = data.get("type")

        print(f"Notification for {user_id}: {message}")

        if user_id not in notifications_store:
            notifications_store[user_id] = []

        notifications_store[user_id].append({
            "id": str(uuid.uuid4()),
            "message": message,
            "type": type_,
            "is_read": False
        })

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(" Error:", str(e))


#Local RabbitMQ 
def start_local_consumer():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost')
    )
    channel = connection.channel()

    channel.queue_declare(queue='notifications_queue')

    channel.basic_consume(
        queue='notifications_queue',
        on_message_callback=callback,
        auto_ack=False
    )

    print("Local Notifications Consumer Running...")
    channel.start_consuming()


# CloudAMQP
def start_cloud_consumer():
    cloud_url = os.environ.get("CLOUDAMQP_URL")

    if not cloud_url:
        print("CLOUDAMQP_URL not set, skipping cloud consumer")
        return
    # cloud_url format: amqps://username:password@host/vhost
    params = pika.URLParameters(cloud_url)   

    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue='notifications_queue')

    channel.basic_consume(
        queue='notifications_queue',
        on_message_callback=callback,
        auto_ack=False
    )

    print("Cloud Notifications Consumer Running...")
    channel.start_consuming()


def start_notifications_consumer():
    # Run both local and cloud consumers in separate threads 
    threading.Thread(target=start_local_consumer).start()
    threading.Thread(target=start_cloud_consumer).start()