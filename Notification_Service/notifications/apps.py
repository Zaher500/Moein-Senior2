#from django.apps import AppConfig


#class NotificationsConfig(AppConfig):
#    name = 'notifications'

#AYO
# import os
# import threading
# from django.apps import AppConfig


# class NotificationsConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'notifications'
#     def ready(self):
#         # 🔥 الحل هنا
#         if os.environ.get('RUN_MAIN') != 'true':
#             return

#         from .notification_consumer import start_notifications_consumer

#         thread = threading.Thread(target=start_notifications_consumer)
#         thread.daemon = True
#         thread.start()

import os
import threading
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'

    def ready(self):
        if os.environ.get('RUN_MAIN') != 'true':
            return

        from .notification_consumer import start_notifications_consumer
        from .rabbitmq_consumer import start_consuming

        # 🔔 Notifications
        threading.Thread(target=start_notifications_consumer, daemon=True).start()

        # 📩 OTP Emails
        threading.Thread(target=start_consuming, daemon=True).start()