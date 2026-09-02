import os
import subprocess

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Dump the current PostgreSQL database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dump-file',
            type=str,
            help='The name of the dump file to create (default: <db_name>.sql)'
        )

    def handle(self, *args, **options):
        db_settings = settings.DATABASES['default']
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST'] or 'localhost'
        db_port = db_settings['PORT'] or '5432'

        dump_file = options['dump_file'] or f'{db_name}.sql'

        # Export the current database
        dump_options = f'--no-owner --no-acl --clean --if-exists'
        dump_command = f'pg_dump -U {db_user} -h {db_host} -p {db_port} -d {db_name} -f {dump_file} {dump_options}'

        self.stdout.write(self.style.SUCCESS(f'Running command: {dump_command}'))
        os.environ['PGPASSWORD'] = db_password

        try:
            subprocess.check_call(dump_command, shell=True)
        except subprocess.CalledProcessError as e:
            self.stderr.write(self.style.ERROR(f'Error during dump: {e}'))
            return

        # Restore this once a site defines SQL functions whose bodies use unqualified
        # names: pg_dump empties search_path, and they cannot resolve then.
        # Modify the dump file to replace the search_path setting
        # try:
        #     # Updating the search path is necessary for the dumps to work with anonymous functions
        #     sed_command = f"sed -i \"s/SELECT pg_catalog.set_config('search_path', '', false);/SELECT pg_catalog.set_config('search_path', 'public, pg_catalog', false);/\" {dump_file}"
        #     self.stdout.write(self.style.SUCCESS(f'Running sed command: {sed_command}'))
        #     subprocess.check_call(sed_command, shell=True)
        #
        #     # Verify the replacement
        #     grep_command = f"grep \"pg_catalog.set_config('search_path'\" {dump_file}"
        #     self.stdout.write(self.style.SUCCESS(f'Running grep command: {grep_command}'))
        #     grep_output = subprocess.check_output(grep_command, shell=True).decode('utf-8')
        #
        #     self.stdout.write(self.style.SUCCESS(f'Grep output:\n{grep_output}'))
        #     self.stdout.write(self.style.SUCCESS(f'Dump of database {db_name} modified successfully.'))
        #     self.stdout.write(self.style.SUCCESS(f'Dump file updated: {dump_file}'))
        #
        # except subprocess.CalledProcessError as e:
        #     self.stderr.write(self.style.ERROR(f'Error during sed/grep: {e}'))
        #     return
