import logging
import os
import sys

from django.core import checks
from django.utils import autoreload

# Configure logging
logger = logging.getLogger(__name__)

@checks.register()
def check_debug_and_allowed_hosts(app_configs, **kwargs):
    """
    System check to log the values of settings.DEBUG and settings.ALLOWED_HOSTS.
    """
    from django.conf import settings

    # Log DEBUG setting
    logger.info("DEBUG setting: %s", settings.DEBUG)

    # Log ALLOWED_HOSTS setting
    logger.debug("Allowed hosts: %s", settings.ALLOWED_HOSTS)

    return []

@checks.register()
def check_vendor_in_sys_path(app_configs, **kwargs):
    """
    System check to verify that 'vendor' is in sys.path and logs sys.path.
    """
    vendor_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'vendor'))

    #TODO: This seems to come too late, not necessary?
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)

    # Log the entire sys.path
    logger.debug("Current sys.path: %s", sys.path)

    return []

@checks.register()
def check_statreloader_usage(app_configs, **kwargs):
    """
    Warn when Django is about to use the slow StatReloader.
    """
    if os.environ.get(autoreload.DJANGO_AUTORELOAD_ENV) != "true":
        return []

    # Looked up on the module, so the reloader djultra's dev command puts in place counts
    if not isinstance(autoreload.get_reloader(), autoreload.StatReloader):
        return []

    return [
        checks.Warning("Django is about to use StatReloader, which polls the filesystem with `os.stat()` and is considerably slower than native watchers.",
            hint="Run the dev server with `manage.py dev`, which watches files through inotify with django-watchfiles")
    ]
