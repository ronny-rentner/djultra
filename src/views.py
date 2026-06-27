import logging

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .models import Person, ContactMessageSerializer

logger = logging.getLogger(__name__)


class GenericAPIThrottle(UserRateThrottle):
    rate = '2/minute'


def index(request):
    context = {
        'frontend_api_url': settings.FRONTEND_API_URL,
        'recaptcha_site_key': settings.RECAPTCHA_SITE_KEY,
    }
    return render(request, 'index.html', context)


class TokenLoginView2(APIView):
    permission_classes = []

    def get(self, request):
        return self.post(request)

    def post(self, request):
        token = request.data.get('token', '') if request.method == 'POST' else request.GET.get('token', '')
        logger.debug(f'Received token: {token}')
        if not token:
            return Response({"error": "Token is required."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, token=token)
        logger.debug('Auth user after authentication: ', user)

        if user:
            login(request, user)
            session_id = request.session.session_key
            return Response({
                "detail": "Login successful.",
                "session_key": settings.SESSION_COOKIE_NAME,
                "session_id": session_id,
            }, status=status.HTTP_200_OK)

        logger.warn('Authentication failed for token ', token)
        return Response({'detail': 'Invalid token or authentication failed.'}, status=status.HTTP_401_UNAUTHORIZED)


class SignOutView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return self.post(request)

    def post(self, request):
        logout(request)
        return Response({"detail": "Logout successful."}, status=status.HTTP_200_OK)


class Ping(APIView):
    permission_classes = []

    def get(self, request):
        logger.warn('Auth ping: ', request.user, request.user.is_authenticated)
        if request.user.is_authenticated:
            return Response({"detail": "Authenticated"}, status=status.HTTP_200_OK)
        return Response({"detail": "Not authenticated"}, status=status.HTTP_200_OK)


class SigninRequestView(APIView):
    throttle_classes = [GenericAPIThrottle]
    permission_classes = []

    def post(self, request, *args, **kwargs):
        logger.debug('Signin request form posted')

        # Verify reCAPTCHA
        recaptcha_response = request.data.get('recaptcha', None)
        email = request.data.get('email', None)
        if not recaptcha_response:
            return Response({"error": "reCAPTCHA token is missing"}, status=status.HTTP_400_BAD_REQUEST)

        recaptcha_verify_url = 'https://www.google.com/recaptcha/api/siteverify'
        recaptcha_data = {
            'secret': settings.RECAPTCHA_SECRET_KEY,
            'response': recaptcha_response
        }
        recaptcha_response = requests.post(recaptcha_verify_url, data=recaptcha_data)
        recaptcha_result = recaptcha_response.json()

        if not recaptcha_result.get('success'):
            logger.error('Recaptcha error: ', recaptcha_result)
            return Response({"error": "Invalid reCAPTCHA. Please try again."}, status=status.HTTP_400_BAD_REQUEST)

        logger.debug('Re-captcha verified')

        try:
            person = Person.objects.get(email=email)
        except Person.DoesNotExist:
            # Same response either way, so the endpoint can't be used to probe which emails exist
            logger.info('Signin request for unknown email')
            return Response({"detail": "Signin message has been sent!"}, status=status.HTTP_201_CREATED)

        person.send_signin_email(request)
        return Response({"detail": "Signin message has been sent!"}, status=status.HTTP_201_CREATED)


class ContactMessageView(APIView):
    throttle_classes = [GenericAPIThrottle]
    permission_classes = []

    def post(self, request, *args, **kwargs):
        logger.debug('Contact form posted')
        # Verify reCAPTCHA
        recaptcha_response = request.data.get('recaptcha', None)
        if not recaptcha_response:
            return Response({"error": "reCAPTCHA token is missing"}, status=status.HTTP_400_BAD_REQUEST)

        recaptcha_verify_url = 'https://www.google.com/recaptcha/api/siteverify'
        recaptcha_data = {
            'secret': settings.RECAPTCHA_SECRET_KEY,
            'response': recaptcha_response
        }
        logger.debug(f'Recaptcha check, got {len(recaptcha_response)} bytes')
        recaptcha_response = requests.post(recaptcha_verify_url, data=recaptcha_data)
        recaptcha_result = recaptcha_response.json()

        if not recaptcha_result.get('success'):
            logger.error('Recaptcha error: ', recaptcha_result)
            return Response({"error": "Could not verify. Please try again."}, status=status.HTTP_400_BAD_REQUEST)

        logger.debug('Re-captcha verified')

        # Serialize and save the message
        serializer = ContactMessageSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            logger.debug('Contact form saved')
            return Response({"detail": "Your message has been sent!"}, status=status.HTTP_201_CREATED)

        #TODO: What's the error key here? Has to be 'error': ...
        #return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
