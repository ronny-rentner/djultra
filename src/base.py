from itertools import chain

from django.db import models
from django.urls import reverse
from django.utils.html import escape, format_html

#from Relonee.core.services import GoogleTranslate


import logging
logger = logging.getLogger(__name__)


def admin_action(description=None):
    """Decorator to mark model methods as admin actions"""

    def decorator(func):
        func._admin_action = True
        func._admin_action_description = description or func.__name__.replace('_', ' ').capitalize()
        return func
    return decorator

# class TranslationMixin:
#     def translate_fields(self, target_language='de', source_language=None, save=True):
#         translator = GoogleTranslate()

#         fields = self._meta.get_fields()
#         # TODO: Don't hardcode '_german'
#         fields_to_translate = {f.name: f.name.replace('_german', '') for f in fields if f.name.endswith('_german')}

#         for target_field, source_field in fields_to_translate.items():
#             source_value = getattr(self, source_field, None)
#             if source_value:
#                 result = translator.translate_text(target_language, [source_value], source_language)
#                 if result:
#                     setattr(self, target_field, result[0]['translatedText'])

#         if save:
#             self.save()

class BaseQuerySet(models.QuerySet):
    def delete(self, *args, **kwargs):
        """Additionally calls the delete() method on reach record before actually deleting"""
        for instance in self:
            # Check if the model instance has a custom `delete` method
            if hasattr(instance, 'delete') and callable(instance.delete):
                # Call the instance's delete method
                instance.delete(*args, **kwargs)
            else:
                # No custom delete method, proceed with default deletion
                continue

        # Perform bulk deletion for remaining records
        super().delete(*args, **kwargs)

class BaseManager(models.Manager):
    def get_queryset(self):
        return BaseQuerySet(self.model, using=self._db)

class BaseModel(models.Model):
    class Admin:
        pass

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BaseManager()

    def get_admin_url(self):
        """Return the admin change URL for the model instance."""
        opts = self._meta
        return reverse(f'admin:{opts.app_label}_{opts.model_name}_change', args=[self.id])

    # TODO: Why do we need this method here? Add documentation if it's necessary.
    def admin_link(self, link_text=None):
        return format_html('<a href="{}">{}</a>', self.get_admin_url(), escape(self if link_text is None else link_text))

    def to_dict(self, fields=None, exclude=None, include=None):
        if exclude is None:
            exclude = getattr(self, 'dict_exclude_fields', None)

        opts = self._meta
        data = {}
        for f in chain(opts.concrete_fields, include or []): #, opts.private_fields, opts.many_to_many):
            if isinstance(f, str):
                data[f] = getattr(self, f)
            else:
                if fields and f.name not in fields:
                    continue
                if exclude and f.name in exclude:
                    continue
                data[f.name] = f.value_from_object(self)

        #logger.debug('to_dict(): ', data)
        return data

    class Meta:
        abstract = True
