import http
import http.cookies
import logging
import re
import threading
import time
from http.cookies import Morsel

import requests
from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, connection
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound

logger = logging.getLogger(__name__)

class RequestIDMiddleware:
    _thread_locals = threading.local()

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # HTTP_X_REQUEST_ID and HTTP_X_START_TIME are set in wsgi.py
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        start_time = request.META.get('HTTP_X_START_TIME')
        RequestIDMiddleware._thread_locals.request = request
        RequestIDMiddleware._thread_locals.request_id = request_id
        RequestIDMiddleware._thread_locals.start_time = start_time
        RequestIDMiddleware._thread_locals.first_log_message_sent = False

        # Log the request ID at the start of the request
        logger.info(f'<Request> "{request.method} {request.path}" id={request_id}')
        #logger.info(f"Request start time: {start_time}")

        # Add the nonce to the request for CSP
        #request.csp_nonce = request_id  # Using request_id as nonce
        setattr(request, "_csp_nonce", request_id)

        response = self.get_response(request)
        return response

    @staticmethod
    def get_request():
        return getattr(RequestIDMiddleware._thread_locals, 'request', False)

    @staticmethod
    def is_first_log_message():
        return getattr(RequestIDMiddleware._thread_locals, 'first_log_message_sent', False)

    @staticmethod
    def set_first_log_message_sent():
        RequestIDMiddleware._thread_locals.first_log_message_sent = True

    @staticmethod
    def reset_first_log_message():
        RequestIDMiddleware._thread_locals.first_log_message_sent = False

    @staticmethod
    def get_request_id():
        return getattr(RequestIDMiddleware._thread_locals, 'request_id', None)

    @staticmethod
    def get_request_start_time():
        return getattr(RequestIDMiddleware._thread_locals, 'start_time', None)

    @staticmethod
    def set_request_start_time(start_time):
        RequestIDMiddleware._thread_locals.start_time = start_time

class AdminActionLoggerMiddleware():
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allows resetting the session
        #request.session['last_admin_action'] = {}
        #request.session.modified = True
        if request.method == 'POST' and request.path.startswith('/admin/'):
            if 'action' in request.POST:
                model = self.get_model_from_path(request.path)
                # request.POST is a Django QueryDict
                logger.debug('POST data: ', request.POST.dict())
                #logger.debug(f"POST data urlencoded: {pretty(request.POST.urlencode())}")
                if model:
                    action_data = {
                        'path': request.path,
                        'data': request.POST.urlencode()
                    }
                    if 'last_admin_action' not in request.session:
                        request.session['last_admin_action'] = {}
                    request.session['last_admin_action'][model] = action_data
                    request.session.modified = True
        response = self.get_response(request)
        return response

    def get_model_from_path(self, path):
        # Extracts the app_label and model_name from the path
        match = re.search(r'^/admin/(?P<app_label>\w+)/(?P<model_name>\w+)/', path)
        if match:
            app_label = match.group('app_label')
            model_name = match.group('model_name')
            try:
                apps.get_model(app_label, model_name)
                return f'{app_label}.{model_name}'
            except LookupError:
                pass
        return None

class AdjustSequenceMiddleware():
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, IntegrityError):
            # Check if the exception is due to a duplicate primary key
            match = re.search(r'duplicate key value violates unique constraint "(.*?)_pkey"', str(exception))
            if match:
                table_name = match.group(1)
                # Log the primary key error and table name
                logger.warning(f"Primary key duplicate error in table {table_name}: {exception}")

                # Get the current sequence value and max id
                with connection.cursor() as cursor:
                    sequence_name = f"{table_name}_id_seq"
                    logger.warning(f"Fetching current sequence value from {sequence_name}")
                    cursor.execute(f"SELECT nextval('{sequence_name}');")
                    current_sequence_value = cursor.fetchone()[0]

                    logger.warning(f"Fetching max(id) from {table_name}")
                    cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name};")
                    max_id = cursor.fetchone()[0]

                    logger.warning(f"Current sequence value: {current_sequence_value}, Max ID in table: {max_id}")

                    if current_sequence_value <= max_id:
                        # Log the sequence adjustment
                        logger.warning(f"Adjusting sequence {sequence_name} for table {table_name}: current_sequence_value={current_sequence_value}, max_id={max_id}")
                        # Adjust the sequence for the table
                        cursor.execute(f"SELECT setval('{sequence_name}', {max_id + 1}, false);")
                        logger.warning(f"Sequence {sequence_name} adjusted to {max_id + 1}")

                        # Log the retry attempt
                        logger.warning(f"Retrying the failed operation for table {table_name}")

                        # Retry the operation by returning None (which will let the request processing continue)
                        return self.get_response(request)
            else:
                logger.warning(f"Failed to extract table name from exception: {exception}")

        return None

class DevProxyMiddleware:
    """
    Probably not needed anymore, UNUSED
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.debug(f'Considering {request.path}')
        if request.path.startswith('/static/frontend/'):
            svelte_dev_server_url = f'http://localhost:5173{request.path}'
            logger.debug(f'Proxying to {svelte_dev_server_url}')
            try:
                response = requests.get(svelte_dev_server_url)
                headers = {key: value for key, value in response.headers.items() if key in [
                    'Content-Type', 'Content-Length', 'Last-Modified', 'Cache-Control', 'ETag']}
                return HttpResponse(response.content, status=response.status_code, headers=headers)
            except requests.exceptions.RequestException:
                return HttpResponseNotFound()
        return self.get_response(request)

class AdminSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        #logger.debug(f'Cookies: {pretty(request.COOKIES)}')
        #logger.debug(f'Original session cookie name: {settings.SESSION_COOKIE_NAME}')
        if request.path.startswith('/admin'):
            settings.SESSION_COOKIE_NAME = 'admin_session_id'
            #logger.debug(f'Detected admin session, using session cookie {settings.SESSION_COOKIE_NAME}')
        else:
            settings.SESSION_COOKIE_NAME = 'api_session_id'
            #logger.debug(f'Detected API session, using session cookie {settings.SESSION_COOKIE_NAME}')
        response = self.get_response(request)
        return response


class PatchMorselMiddleware:
    """ Patches Python's built-in Cookie Morsel to allow partioned cookies and
        set all cookies as partitioned by default
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.patch_morsel()

    def patch_morsel(self):
        # Define a patched Morsel class that includes the Partitioned attribute by default
        class PatchedMorsel(Morsel):
            def __init__(self):
                super().__init__()
                self._reserved["partitioned"] = "Partitioned"
                self._flags.add("partitioned")
                self["partitioned"] = True

        # Patch the Morsel class in the http.cookies module
        http.cookies.Morsel = PatchedMorsel

        # Instantiate PatchedMorsel to verify changes
        #patched_morsel_instance = PatchedMorsel()

    def __call__(self, request):
        response = self.get_response(request)
        return response

class QueryLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        total_queries = len(connection.queries)
        total_time = 0

        # Log queries that took longer than 10 ms
        for query in connection.queries:
            query_time = float(query['time']) * 1000  # Convert to milliseconds
            total_time += query_time
            if query_time > 10:
                logger.warn(f"Slow Query ({query_time:.2f} ms): {query['sql'][:1000]}")

                # Generate the EXPLAIN ANALYZE query
                #explain_analyze_query = f"EXPLAIN ANALYZE {query['sql']}"
                #print(f"EXPLAIN ANALYZE query:\n{explain_analyze_query}")


            else:
                #logger.debug(f"Query ({query_time:.2f} ms): {query['sql']}")
                pass

            # Generate the EXPLAIN ANALYZE query
            #explain_analyze_query = f"EXPLAIN ANALYZE {query['sql']}"
            #print(f"EXPLAIN ANALYZE query:\n{explain_analyze_query}")

        logger.info(f"Total number of queries: {total_queries}, total query time: {total_time}")

        return response

class ArtificialDelayMiddleware:
    """
    Middleware to delay requests to specific paths by a configurable amount of time.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Load configurations from settings
        self.delay_config = getattr(settings, 'ARTIFICIAL_DELAY', {})

    def __call__(self, request: HttpRequest):
        # Extract path and delay time from settings
        delay_path = self.delay_config.get('path', None)
        delay_time = self.delay_config.get('delay', 0)

        if delay_path and delay_time > 0:
            # Check if the request path matches the configured path
            if request.path.startswith(delay_path):
                # Introduce artificial delay
                logger.warn(f'Delaying requests path="{delay_path}" time={delay_time}s')
                time.sleep(delay_time)

        response = self.get_response(request)
        return response
