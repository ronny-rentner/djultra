import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from rest_framework import serializers

from djultra import fields
import djultra.services.email
from djultra.middleware import RequestIDMiddleware

from . import Base

logger = logging.getLogger(__name__)

class Person(Base):
    class Meta:
        serializer_defaults = {
            'fields': [
                'id',
                'first_name',
                'last_name',
                'full_name',
                'email',
                'birthday',
                'birthplace',
                'status',
            ]
        }
    class Status(models.TextChoices):
        NEW      = 'new',      'New'
        ACTIVE   = 'active',   'Active'
        DISABLED = 'disabled', 'Disabled'
        DELETED  = 'deleted',  'Deleted'

    # Status field using the inner class for choices
    status = fields.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.NEW,
    )

    first_name = fields.CharField()
    last_name = fields.CharField()
    full_name = fields.CharField(editable=False)
    email = models.EmailField(max_length=255, unique=True, null=False, blank=False)
    birthday = fields.AdvancedDateField(null=True, blank=True)
    birthplace = fields.CharField()
    invitation_token = models.UUIDField(editable=False, unique=True, null=True)
    invitation_token_created_at = models.DateTimeField(editable=False, null=True, blank=True)
    signin_token = models.UUIDField(editable=False, unique=True, null=True)
    signin_token_created_at = models.DateTimeField(editable=False, null=True, blank=True)
    terms_accepted_at = models.DateTimeField(editable=False, null=True, blank=True)

    # TODO: Test if we still need this as we have the LoginUser
    # Needed for auth in DRF
    is_active = True

    @property
    def name(self):
        if self.first_name and self.last_name:
            return f'{self.first_name} {self.last_name}'.strip()

        if self.last_name:
            return self.last_name.strip()

        if self.first_name:
            return self.first_name.strip()

        return '(no name set)'

    @property
    def is_authenticated(self):
        request = RequestIDMiddleware.get_request()
        if request:
            person_id = request.session.get('_auth_person_id')
            return person_id == str(self.id)
        return False

    @classmethod
    def get_and_validate(cls, token):
        person = None
        try:
            person = cls.objects.get(signin_token=token)
        except Exception:
            pass
        if not person:
            person = cls.objects.get(invitation_token=token)
            if person.invitation_token_created_at < timezone.now() - timedelta(days=7):
                raise ValidationError("The token has expired.")
        logger.debug(f'Token validated for person={person}')
        return person

    def save(self, *args, **kwargs):
        self.full_name = f"{self.first_name} {self.last_name}".strip()
        super().save(*args, **kwargs)

    @property
    def request(self):
        return RequestIDMiddleware.get_request()

    def signin(self, token, request=None):
        if not request:
            request = RequestIDMiddleware.get_request()
        if not request:
            return False

        logger.debug(f'Signin with token={token}')
        #logger.debug(f'Received token type: {type(token)}')
        if not token:
            return False

        # Authenticate the user using the custom TokenBackend
        user = authenticate(request, token=token)

        logger.debug('Auth user after authentication: ', user)

        if user:
            # Log the user in by setting the session
            login(request, user)
            return True
        else:
            logger.warn('Authentication failed for token=%s', token)

        return False

    def send_invitation_email(self, request):
        self.invitation_token = uuid.uuid4()
        self.invitation_token_created_at = timezone.now()
        self.save()

        invitation_link = f"{settings.FRONTEND_URL_EMAILS}/signin?token={self.invitation_token}"
        full_link = request.build_absolute_uri(invitation_link)

        context = {
            'project_name': settings.PROJECT_NAME,
            'frontend_url': settings.FRONTEND_URL_EMAILS,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'invitation_link': full_link
        }

        return djultra.services.email.send_templated_email(
            subject=f"Invitation to {settings.PROJECT_NAME}",
            template_name="emails/invitation.html",
            context=context,
            recipient_list=[self.email]
        )

    def generate_signin_token(self):
        #TODO: Handle time out of signin token
        self.signin_token = uuid.uuid4()
        self.signin_token_created_at = timezone.now()
        self.save(update_fields=["signin_token", "signin_token_created_at"])

    @property
    def signin_link(self):
        #TODO: Handle time out of signin token
        if not self.signin_token:
            self.generate_signin_token()

        return f"{settings.FRONTEND_URL_EMAILS}/signin?token={self.signin_token}"

    def send_signin_email(self, request):
        self.generate_signin_token()
        full_link = request.build_absolute_uri(self.signin_link)

        context = {
            'project_name': settings.PROJECT_NAME,
            'frontend_url': settings.FRONTEND_URL_EMAILS,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'signin_link': full_link
        }

        return djultra.services.email.send_templated_email(
            subject=f"Sign in to {settings.PROJECT_NAME}",
            template_name="emails/signin.html",
            context=context,
            recipient_list=[self.email]
        )

    def __str__(self):
        if not self.first_name and not self.last_name:
            return f'{self.pk} - Person'
        return f'{self.pk} - {self.first_name} {self.last_name}'

class PersonAcceptTermsSerializer(serializers.Serializer):
    accept = serializers.BooleanField()

    def validate_accept(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the terms to proceed.")
        return value

class PersonLoginUser(AbstractBaseUser):
    person = models.OneToOneField(Person, on_delete=models.CASCADE, related_name='login_user')

    def save(self, *args, **kwargs):
        # Check if username is empty and set a default
        #if not self.username:
        #    self.username = f"person_{self.person.pk}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.person.full_name} (Login User)"

