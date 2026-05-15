import logging
from django.conf import settings
from django.apps import apps
from django.contrib import admin
from .base import BaseModelAdmin, AutoFieldsetsMixin
from .action_result_reporter import ActionResultReporter

logger = logging.getLogger(__name__)

from functools import wraps

def make_action(model, method_name, description):
    """
    Create an admin action function for the given model method.
    """
    @wraps(getattr(model, method_name))
    def action(self, request, queryset):
        reporter = ActionResultReporter()
        for obj in queryset:
            method = getattr(obj, method_name)
            try:
                result = method()
                if isinstance(result, dict) and 'warnings' in result:
                    reporter.add_warning(obj, result['warnings'])
                else:
                    reporter.add_success(obj)
            except Exception as e:
                logger.exception('Admin action failed')
                reporter.add_failure(obj, e)
        reporter.generate_message(request, action_label=description)
    action.short_description = description
    return action

def install():
    for app_label in getattr(settings, 'INSTALLED_ULTRA_APPS', []):
        logger.debug('Finding models for generating admin: app=%s', app_label)
        try:
            app_config = apps.get_app_config(app_label)
        except LookupError:
            logger.warning("AppConfig not found for '%s', skipping.", app_label)
            continue

        for model in app_config.get_models():
            admin_meta = getattr(model, 'Admin', None)
            if not admin_meta:
                logger.debug("Model '%s' has no Admin class, skipping.", model.__name__)
                continue

            # collect attrs from Admin stub
            attrs = {
                name: getattr(admin_meta, name)
                for name in vars(admin_meta)
                if not name.startswith('_')
            }

            # create and register the ModelAdmin
            AdminClass = type(
                f"{model.__name__}Admin",
                (AutoFieldsetsMixin, BaseModelAdmin),
                attrs
            )

            for attr_name, attr_value in vars(model).items():
                if getattr(attr_value, '_admin_action', False):
                    description = getattr(attr_value, '_admin_action_description', attr_name.replace('_', ' ').capitalize())
                    action_func = make_action(model, attr_name, description)
                    AdminClass.actions.append(action_func)

            admin.site.register(model, AdminClass)
            logger.info("Registered admin for model '%s.%s' with actions: %s.", app_label, model.__name__, attrs.get('actions', []))


install()

