from django.core.management.base import BaseCommand
from notifications.notification_consumer import start_notifications_consumer


class Command(BaseCommand):
    help = "Start Notifications Consumer"

    def handle(self, *args, **kwargs):
        self.stdout.write("🚀 Starting Notifications Consumer...")
        start_notifications_consumer()