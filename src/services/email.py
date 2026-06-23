# core/services/email.py
import logging

import django.core.mail
from django.core.mail.backends import base, smtp, console
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django_tasks import task

logger = logging.getLogger(__name__)

@task()
def send_email_task(subject, html_content, plain_content, recipient_list, from_email):
    """Task that uses the service's internal sending method"""
    Email.send_email(
        subject=subject,
        html_content=html_content,
        plain_content=plain_content,
        recipient_list=recipient_list,
        from_email=from_email
    )

class Email:
    @classmethod
    def send_templated_email(cls, subject, template_name, context, recipient_list, from_email=None, async_mode=True):
        if not from_email:
            from_email = settings.DEFAULT_FROM_EMAIL

        # Render email content
        html_content = render_to_string(template_name, context)
        plain_content = strip_tags(html_content)

        if async_mode:
            # Enqueue task with render results in async mode
            send_email_task.enqueue(
                subject=subject,
                html_content=html_content,
                plain_content=plain_content,
                recipient_list=recipient_list,
                from_email=from_email
            )
        else:
            # Send directly
            cls.send_email(subject, plain_content, from_email, recipient_list, html_message=html_content)

    @classmethod
    def send_email(cls, subject, html_content, plain_content, recipient_list, from_email):
        """Internal method for sending pre-rendered emails"""
        try:
            result = django.core.mail.send_mail(
                subject,
                plain_content,
                from_email,
                recipient_list,
                html_message=html_content,
                fail_silently=False,
            )

            if result == 1:
                logger.info(f"Email successfully sent to {recipient_list}")
            else:
                logger.error(f"Failed to send email to {recipient_list}")
            return result

        except Exception as e:
            logger.exception(f"Unexpected error while sending email to {recipient_list}: {e}")
            raise

send_templated_email = Email.send_templated_email


class Backend(base.BaseEmailBackend):
    """
    Sends via SMTP and, when settings.EMAIL_PRINT_TO_CONSOLE is on, also prints
    the messages to the console (Relonee toggled this by hand; here it is a setting).
    """
    def __init__(self, *args, **kwargs):
        self.smtp_backend = smtp.EmailBackend(*args, **kwargs)
        self.console_backend = console.EmailBackend(*args, **kwargs) if settings.EMAIL_PRINT_TO_CONSOLE else None

    def send_messages(self, email_messages):
        smtp_count = self.smtp_backend.send_messages(email_messages)
        if self.console_backend:
            self.console_backend.send_messages(email_messages)
        return smtp_count
