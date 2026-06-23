import logging

from django.contrib.auth.backends import BaseBackend
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated

from .models import Person, PersonLoginUser

logger = logging.getLogger(__name__)

class TokenBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, token=None):
        logger.debug('authenticate() called with token: %s', token)

        # Handle traditional username/password authentication if needed
        if username and password:
            #TODO: Password login not supported right now
            return
            try:
                user = PersonLoginUser.objects.get(id=username)
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user
            except PersonLoginUser.DoesNotExist:
                return

        # Token login
        if token:
            try:
                person = Person.get_and_validate(token)

                # Get or create the PersonLoginUser associated with the Person
                person_login_user, created = PersonLoginUser.objects.get_or_create(person=person)

                return person_login_user
            except Person.DoesNotExist as e:
                logger.error('Person not found')
                return

    def get_user(self, user_id):
        try:
            return PersonLoginUser.objects.get(pk=user_id)
        except PersonLoginUser.DoesNotExist:
            return None


class IsOwner(IsAuthenticated):
    """
    Custom permission to only allow owners of an object to access it.
    """
    def __init__(self, owner_pk_field='pk'):
        self.owner_pk_field = owner_pk_field

    def has_permission(self, request, view):
        """
        This function checks the logged in user is requesting access to data of a different user
        via the person_pk URL parameter.
        """
        #logger.debug(f'Owner permission check: {self.owner_pk_field}={request.user.person.pk}')
        # Check if we are authenticated at all, if not, no further checks needed
        if not super().has_permission(request, view):
            return False

        # Extract the person_pk from the URL kwargs
        person_pk = view.kwargs.get('person_pk')

        # This is a tricky check. If there's no person_pk in the URL, by default,
        # we use the currently logged in person. In the next step below, we would
        # compare this again to the currently logged in person which is always true.
        if not person_pk:
            return True

        # Ensure the logged-in user's person.pk matches the person_pk in the URL
        return person_pk == request.user.person.pk

    def has_object_permission(self, request, view, obj):
        """
        Check object permissions.
        """
        #logger.debug('Check object permission', obj, self.owner_pk_field, request.user.person.pk)
        try:
            owner_pk = getattr(obj, self.owner_pk_field)
            #logger.debug('Owner PK: ', owner_pk)
        except AttributeError:
            raise NotFound(f"Owner field '{self.owner_pk_field}' not found in the object.")

        # Check if the owner's pk matches the logged-in person's pk
        return owner_pk == request.user.person.pk
