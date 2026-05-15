import logging
import os
import sys

from django.core import checks
from django.utils.autoreload import DJANGO_AUTORELOAD_ENV, get_reloader

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
    if os.environ.get(DJANGO_AUTORELOAD_ENV) != "true":
        return []

    reloader = get_reloader()
    reloader_cls = reloader if isinstance(reloader, type) else reloader.__class__

    if reloader_cls.__name__ != "WatchmanReloader":

        availability = False

        try:
            from django.utils.autoreload import WatchmanReloader
            availability = WatchmanReloader.check_availability()
            
        except Exception as e:
            logger.error('Cannot use Watchman reloader: ', e)

    if not reloader_cls or reloader_cls.__name__ == "StatReloader":
        return [
            checks.Warning("Django is about to use StatReloader, which polls the filesystem with `os.stat()` and is considerably slower than native watchers.",
                hint="Install watchman for a faster, inotify-based file system watcher")
        ]

    return []
