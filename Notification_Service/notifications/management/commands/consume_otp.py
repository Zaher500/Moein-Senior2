from django.core.management.base import BaseCommand
from notifications.rabbitmq_consumer import start_consuming


class Command(BaseCommand):
    help = "Start RabbitMQ OTP consumer"

    def handle(self, *args, **kwargs):
        self.stdout.write("🚀 Starting RabbitMQ Consumer...")
        start_consuming()