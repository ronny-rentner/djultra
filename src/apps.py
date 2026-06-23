from django.apps import AppConfig
#import os

# When collecting autocompletions we should not pollute the output with logs
#if os.environ.get("DJANGO_AUTO_COMPLETE"):
#    import logging
#    logging.disable()

class DjultraConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'djultra'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Allow Django models to define `serializer_defaults` attribute as a model._meta option
        import django.db.models.options as options
        options.DEFAULT_NAMES = (*options.DEFAULT_NAMES, 'serializer_defaults')

    def ready(self):
        from . import checks
