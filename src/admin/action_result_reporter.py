from django.contrib import messages
from django.utils.safestring import mark_safe
from django.utils.html import escape
import logging

logger = logging.getLogger(__name__)

class ActionResultReporter:
    def __init__(self):
        """
        Initialize the reporter with default settings for tracking results.
        """
        self.success_records = []
        self.warning_records = []
        self.failed_records = []

    def add_success(self, record):
        """
        Record a successful operation for a given record.
        """
        self.success_records.append(record)
        logger.info(f"Successfully processed record: {record}")

    def add_warning(self, record, failed_fields):
        """
        Record a warning for a given record with details of failed fields.
        """
        self.warning_records.append((record, failed_fields))
        logger.warning(f"Processed with warnings: {record} - Failed fields: {failed_fields}")

    def add_failure(self, record, error):
        """
        Record a failed operation for a given record with the error.
        """
        self.failed_records.append((record, repr(error)))
        logger.error(f"Failed to process record: {record} - Error: {error}")

    def generate_message(self, request, action_label="Action"):
        """
        Generate a consolidated message summarizing successes, warnings, and failures.
        :param request: Django request object for adding messages.
        :param action_label: A descriptive label for the action performed.
        """
        action_label = f"<strong>{action_label.capitalize()}</strong>"

        # Success message
        if self.success_records:
            success_message = self._format_message(len(self.success_records), f"{action_label} was successful")
            if len(self.success_records) == 1:
                success_message += f": {self.success_records[0]}."
            self._add_message(request, mark_safe(success_message), messages.SUCCESS)

        # Warning message
        if self.warning_records:
            warning_message = self._format_message(len(self.warning_records), f"{action_label} completed with warnings")
            warning_message += ":<br />"
            for record, failed_fields in self.warning_records:
                warning_message += f'{record}: '
                if len(failed_fields) > 1:
                    warning_message += '<br />'
                for field, value, reason in failed_fields:
                    warning_message += f'Field <em>{field}</em>: {escape(", ".join(reason))}<br />'
            self._add_message(request, mark_safe(warning_message), messages.WARNING)

        # Failure message
        if self.failed_records:
            failure_message = self._format_message(len(self.failed_records), f"{action_label} failed")
            failure_message += ":<br />"
            for record, error in self.failed_records:
                failure_message += f'{record}: {escape(error)}<br />'
            self._add_message(request, mark_safe(failure_message), messages.ERROR)

    def _add_message(self, request, message, level):
        """
        Helper method to add messages to Django's messaging framework.
        """
        request._messages.add(level, message)

    def _format_message(self, count, base_message):
        """
        Helper method to format grammatically correct messages based on count.
        :param count: Number of items.
        :param base_message: Base message (e.g., "Action succeeded").
        :return: Formatted message string.
        """
        if count == 1:
            return f"{base_message} for <strong>1 record</strong>"
        else:
            return f"{base_message} for <strong>{count} records</strong>"
