import os
import sys
import signal
import logging

from django.core.management.commands.runserver import Command as RunserverCommand
from django.db import connections
from django.conf import settings
from django.utils.autoreload import DJANGO_AUTORELOAD_ENV

from django_tasks_db.management.commands.db_worker import Worker

import setproctitle

from . import fastmanage_daemon

logger = logging.getLogger(__name__)

class Command(RunserverCommand):
    help = "Run Django's devserver and fork child to run db_worker and fastmanage daemon."

    def _terminate_and_wait(self, pid, name):
        if not pid:
            return
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info(f"Sent SIGTERM to {name} (pid={pid})")
        except OSError:
            logger.warning(
                f"Could not SIGTERM {name} (pid={pid}); may have already exited"
            )
        try:
            os.waitpid(pid, 0)
            logger.info(f"{name} (pid={pid}) exited")
        except Exception:
            logger.warning(f"Could not waitpid for {name} (pid={pid})")

    def _run_worker(self):
        """Launch the django-tasks db_worker"""
        worker = Worker(
            queue_names=["default"],
            interval=1,
            batch=False,
            backend_name="default",
            startup_delay=True,
            max_tasks=None,
            worker_id="default",
        )
        worker.run()

    def handle(self, *args, **options):
        if "DJANGO_RUNSERVER_HIDE_WARNING" not in os.environ:
            os.environ["DJANGO_RUNSERVER_HIDE_WARNING"] = "true"

        setproctitle.setproctitle("django-main")

        # Redirect command output to logger
        self.stdout.write = logger.info
        self.stderr.write = logger.error

        use_reloader = options.get("use_reloader", False)
        is_main = os.environ.get(DJANGO_AUTORELOAD_ENV) == "true"

        if use_reloader and not is_main:
            super().handle(*args, **options)
            return

        self.child_pids = {}

        # Launch fastmanage daemon
        daemon_enabled = getattr(settings, fastmanage_daemon.CONF_ENABLE, True)
        if daemon_enabled:
            connections.close_all()
            daemon_pid = os.fork()
            if daemon_pid == 0:
                os.setsid()
                setproctitle.setproctitle("django-fastmanage-daemon")
                daemon = fastmanage_daemon.FastmanageDaemon()
                daemon.start()
                os._exit(0)
            self.child_pids["daemon"] = daemon_pid

        # Launch db_worker process
        db_worker_enabled = getattr(settings, "DJU_DEV_DB_WORKER_ENABLE", True)
        if db_worker_enabled:
            connections.close_all()
            worker_pid = os.fork()
            if worker_pid == 0:
                os.setsid()
                setproctitle.setproctitle("django-tasks-db-worker")
                self._run_worker()
                os._exit(0)
            self.child_pids["worker"] = worker_pid

        # Launch local dev server
        try:
            logger.info(
                "Starting Django dev server "
                f"(worker_pid={self.child_pids.get('worker', 'skipped')}, "
                f"daemon_pid={self.child_pids.get('daemon', 'skipped')})"
            )
            setproctitle.setproctitle("django-dev-server")
            super().handle(*args, **options)
        finally:
            logger.info("Shutting down child processes...")
            for name, pid in self.child_pids.items():
                self._terminate_and_wait(pid, name)
