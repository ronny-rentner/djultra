import logging

from django.db import models
from rest_framework import serializers

from djultra import fields

from . import Base

logger = logging.getLogger(__name__)

class ContactMessage(Base):
    name = fields.AdvancedCharField(max_length=255, blank=False)
    email = models.EmailField(blank=False)
    message = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = fields.AdvancedCharField(max_length=255, blank=True)
    STATUS_CHOICES = [
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ]
    status = fields.AdvancedCharField(max_length=20, choices=STATUS_CHOICES, default='new')

    def __str__(self):
        return f"Message from {self.name} - {self.email}"

class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'message']

    def create(self, validated_data):
        request = self.context.get('request')

        # Check X-Forwarded-For header first
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()  # First IP in the list is the client's IP
        else:
            ip_address = request.META.get('REMOTE_ADDR')  # Fall back to REMOTE_ADDR

        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Add ip_address and user_agent to validated_data
        validated_data['ip_address'] = ip_address
        validated_data['user_agent'] = user_agent

        return super().create(validated_data)
