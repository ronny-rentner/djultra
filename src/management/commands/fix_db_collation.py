from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.backends.postgresql.psycopg_any import sql


class Command(BaseCommand):
    help = 'Fix a database collation version mismatch by rebuilding indexes and refreshing the recorded version.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default', choices=connections, help='Django database alias (default: default).')

    def handle(self, *args, **options):
        connection = connections[options['database']]
        if connection.vendor != 'postgresql':
            raise CommandError('fix_db_collation requires PostgreSQL.')
        # REINDEX DATABASE cannot run inside a transaction.
        if not connection.get_autocommit():
            raise CommandError('fix_db_collation requires autocommit; run it outside a transaction.')

        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT datname, datcollversion, pg_database_collation_actual_version(oid) '
                'FROM pg_database WHERE datname = current_database()'
            )
            database_name, recorded_version, actual_version = cursor.fetchone()
            if recorded_version is None or actual_version is None or recorded_version == actual_version:
                self.stdout.write(f'database "{database_name}" has no recorded collation version mismatch; no repair needed.')
                return

            self.stdout.write(self.style.WARNING(f'database "{database_name}" has a collation version mismatch'))
            self.stdout.write(f'Recorded version: {recorded_version}; current version: {actual_version}.')
            self.stdout.write(f'Rebuilding indexes in database "{database_name}"; queries and writes can block until completion.')
            cursor.execute(sql.SQL('REINDEX DATABASE {}').format(sql.Identifier(database_name)))
            # Keep the mismatch recorded if rebuilding fails.
            cursor.execute(sql.SQL('ALTER DATABASE {} REFRESH COLLATION VERSION').format(sql.Identifier(database_name)))

        self.stdout.write(self.style.SUCCESS(f'Fixed collation version mismatch for database "{database_name}".'))
