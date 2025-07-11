import logging
import os
import signal

from django.core.management.commands.runserver import Command as RunserverCommand
from django.db import connections
from django_tasks.backends.database.management.commands.db_worker import Worker
from django.utils.autoreload import DJANGO_AUTORELOAD_ENV

logger = logging.getLogger(__name__)


class Command(RunserverCommand):
    help = "Run Django's devserver in the parent process and fork a child to run the db_worker."

    def handle(self, *args, **options):

        if "DJANGO_RUNSERVER_HIDE_WARNING" not in os.environ:
            os.environ["DJANGO_RUNSERVER_HIDE_WARNING"] = "true"

        #TODO: Not sure if this is a good idea but this redirects messages to the log
        self.stdout.write = logger.info
        self.stderr.write = logger.error

        use_reloader = options["use_reloader"]
        is_main = os.environ.get(DJANGO_AUTORELOAD_ENV) == 'true'

        if use_reloader and not is_main:
            super().handle(*args, **options)
            return

        connections.close_all()
        pid = os.fork()
        self.pid = pid
        if pid == 0:
            self._run_worker()
        else:
            try:
                logger.info(f'Django dev server starting: pid={self.pid}')
                super().handle(*args, **options)
            finally:
                logger.info(f'Django dev server finished: pid={self.pid}')
                os.kill(pid, signal.SIGTERM)
                os.waitpid(pid, 0)

    def _run_worker(self):
        try:
            logger.info(f'Worker starting: pid={self.pid}')
            worker = Worker(
                queue_names=["default"],
                interval=1,
                batch=False,
                backend_name="default",
                startup_delay=True,
                max_tasks=None,
                worker_id="default"
            )
            worker.run()
        finally:
            logger.info(f'Worker finished: pid={self.pid}')
