from django.apps import AppConfig
#import os

# When collecting autocompletions we should not pollute the output with logs
#if os.environ.get("DJANGO_AUTO_COMPLETE"):
#    import logging
#    logging.disable()

class DjultraConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'djultra'

    def ready(self):
        from . import checks
