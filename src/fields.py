import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models

import django_countries
import django_countries.fields

from djultra import serializers

logger = logging.getLogger(__name__)


class CountryField(django_countries.fields.CountryField):
    def __init__(self, *args, mapping=None, form_blank=None, db_null=None, **kwargs):
        defaults = {
            'blank': True if form_blank is None else form_blank,
            'null': True if db_null is None else db_null,
        }
        defaults.update(kwargs)
        self.mapping = mapping or {}
        super().__init__(*args, **defaults)

    def clean(self, value, model_instance):
        if isinstance(value, str):
            value = self.mapping.get(value.strip().upper(), value.strip().upper())
            try:
                value = django_countries.countries.alpha2(value)
            except KeyError:
                pass

        return super().clean(value, model_instance)


class DecimalField(models.DecimalField):
    def __init__(self, *args, form_blank=None, db_null=None, **kwargs):
        defaults = {
            'blank': True if form_blank is None else form_blank,
            'null': True if db_null is None else db_null,
        }
        defaults.update(kwargs)  # Merge user-provided kwargs with defaults
        super().__init__(*args, **defaults)

    # def value_to_string(self, obj):
    #     logger.warn('VALUE_TO_STRING DecimalField: ', obj)
    #     val = self.value_from_object(obj)
    #     if val:
    #         return format(Decimal(val), 'f').rstrip('0').rstrip('.')
    #     return val

    def to_python(self, value):
        # Handle the case where value is already a Decimal
        if isinstance(value, Decimal):
            return value

        # Handle the German and English number format
        if isinstance(value, str):
            #logger.debug('Parsing number from string')
            # Regex patterns
            value = value.strip('.,\'"“” ')

            german_format_pattern = re.compile(r'^\d{1,3}(\.\d{3})*(,\d{1,2})?$')
            english_format_pattern = re.compile(r'^\d{1,3}(,\d{3})*(\.\d{1,2})?$')

            if german_format_pattern.match(value):
                #logger.debug('German format detected')
                try:
                    value = value.replace('.', '').replace(',', '.')
                    return Decimal(value)
                except InvalidOperation:
                    raise ValidationError(f"Invalid decimal value: {value}")
            elif english_format_pattern.match(value):
                try:
                    value = value.replace(',', '')
                    return Decimal(value)
                except InvalidOperation:
                    raise ValidationError(f"Invalid decimal value: {value}")

        # Call the superclass method to ensure proper handling
        return super().to_python(value)

AdvancedDecimalField = DecimalField

class TextField(models.TextField):
    pass

class TextChoices(models.TextChoices):
    pass

class AdvancedCharField(models.CharField):
    def __init__(self, *args, **kwargs):
        defaults = {
            'max_length': 255,
            'blank': True,
            'null': False,
            'default': '',
        }
        defaults.update(kwargs)  # Merge user-provided kwargs with defaults
        super().__init__(*args, **defaults)

    def remove_quotes_and_parentheses(self, s):
        # Check for and remove leading quotes or parentheses
        # TODO: Not sure if it is correct to just cut those off
        if (s.startswith("'") and s.endswith("'")):
            s = s[1:]
            s = s[:-1]
        if (s.startswith("(") and s.endswith(")")):
            s = s[1:]
            s = s[:-1]
        if (s.startswith('"') and s.endswith('"')):
            s = s[1:]
            s = s[:-1]
        s = s.replace('\n', ' ')
        return s

    def clean(self, value, model_instance):
        # Ensure the value is a string and replace new lines with spaces
        if isinstance(value, str):
            value = self.remove_quotes_and_parentheses(value)
        return super().clean(value, model_instance)

# TODO: Replace AdvancedCharField with Charfield below
class CharField(models.CharField):
    def __init__(self, *args, form_blank=None, db_null=None, **kwargs):
        if 'blank' in kwargs:
            pass
            #TODO: enable the warning
            #logger.warn("Use `form_blank` instead of `blank` to control form behavior.")
            #raise TypeError("Use `form_blank` instead of `blank` to control form behavior.")

        if 'null' in kwargs:
            pass
            #TODO: enable the warning
            #logger.warn("Use `db_null` instead of `null` to control database behavior.")
            #raise TypeError("Use `db_null` instead of `null` to control database behavior.")

        defaults = {
            'max_length': 255,
            'blank': True if form_blank is None else form_blank,
            'null': True if db_null is None else db_null,
            'default': '',
        }
        defaults.update(kwargs)
        super().__init__(*args, **defaults)

    def remove_quotes_and_parentheses(self, s):
        # Check for and remove leading quotes or parentheses
        # TODO: Not sure if it is correct to just cut those off
        if (s.startswith("'") and s.endswith("'")):
            s = s[1:]
            s = s[:-1]
        if (s.startswith("(") and s.endswith(")")):
            s = s[1:]
            s = s[:-1]
        if (s.startswith('"') and s.endswith('"')):
            s = s[1:]
            s = s[:-1]
        s = s.replace('\n', ' ')
        return s

    def clean(self, value, model_instance):
        # Ensure the value is a string and replace new lines with spaces
        if isinstance(value, str):
            value = self.remove_quotes_and_parentheses(value)
        return super().clean(value, model_instance)


class CleanValueDescriptor:
    def __init__(self, field):
        self.field = field

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return instance.__dict__.get(self.field.name)

    def __set__(self, instance, value):
        parsed = self.field.to_python(value)
        instance.__dict__[self.field.name] = parsed


class DateField(models.DateField):
    descriptor_class = CleanValueDescriptor

    def __init__(self, *args, form_blank=None, db_null=None, **kwargs):
        defaults = {
            'max_length': 255,
            'blank': True if form_blank is None else form_blank,
            'null': True if db_null is None else db_null,
        }
        defaults.update(kwargs)  # Merge user-provided kwargs with defaults
        super().__init__(*args, **defaults)

    def contribute_to_class(self, cls, name):
        super().contribute_to_class(cls, name)
        setattr(cls, name, self.descriptor_class(self))

    def to_python(self, value):
        if value is None or isinstance(value, date):
            return value

        formats = [
            '%d %b %y',     # "14 FEB 24" or "14 FÉV 24"
            '%d %B %y',
            '%d %b %Y',
            '%d %B %Y',
            '%B %d %Y',     # "JULY 6 1997"
            '%Y-%m-%d',     # "2018-10-25"
            '%d.%m.%Y',     # "25.10.2019"
            '%d/%m/%Y',
            '%d/%m/%y',
            '%y%m%d',
            '%Y-%m',
            '%y-%m',
            '%Y',           # "2018"
        ]

        # Special handling for the '16 OF DECEMBER 20 19' format
        value = re.sub(r'(\b19\b|\b20\b) (\d{2})$', r'\1\2', value)

        # Special handling for month in '18 ABR/APR 2027' format
        pattern = r' (?P<local_month>[A-ZÇĞİÖŞÜ]{3})/(?P<english_month>[A-ZÇĞİÖŞÜ]{3}) '
        value = re.sub(pattern, r' \2 ', value, flags=re.UNICODE)

        # Convert value to uppercase and remove special characters except slashes and dashes
        value = re.sub(r'[^\w\s./-]|\.$', ' ', value).upper()
        value = re.sub(r'\s\s+', ' ', value).strip()

        # Remove suffixes from day values like '1ST' and '2ND', etc.
        value = re.sub(r'\b(\d+)(?:ST|ND|RD|TH)\b', r'\1', value)

        months = {
            #'JAN': 'JAN',
            'FÉV': 'FEB',
            #'MAR': 'MAR',
            'AVR': 'APR',
            'MAI': 'MAY',
            'JUI': 'JUN',
            #'JUL': 'JUL',
            'AOÛ': 'AUG',
            #'SEP': 'SEP',
            #'OCT': 'OCT',
            #'NOV': 'NOV',
            'DÉC': 'DEC',
        }

        for key, value_month in months.items():
            value = value.replace(key, value_month)

        # Regex to replace the duplicate month abbreviations
        value = re.sub(r'\b(\w+)\b/\b\1\b', r'\1', value)

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        raise ValidationError(f"Date format for '{value}' not recognized")

    #def from_db_value(self, value, expression, connection):
    #    if value is None:
    #        return value
    #    return value

    #def get_prep_value(self, value):
    #    value = self.to_python(value)
    #    return super().get_prep_value(value)

AdvancedDateField = DateField

class GenderField(models.CharField):
    UNKNOWN = 'U'
    MALE = 'M'
    FEMALE = 'F'
    OTHER = 'O'

    GENDER_CHOICES = [
        (UNKNOWN, 'Unknown'),
        (MALE, 'Male'),
        (FEMALE, 'Female'),
        (OTHER, 'Other'),
    ]

    def __init__(self, *args, form_blank=None, db_null=None, **kwargs):
        defaults = {
            'max_length': 1,
            'blank': True if form_blank is None else form_blank,
            'null': True if db_null is None else db_null,
            'choices': self.GENDER_CHOICES,
            'default': self.UNKNOWN,
        }
        defaults.update(kwargs)  # Merge user-provided kwargs with defaults
        super().__init__(*args, **defaults)

    def to_python(self, value):
        if value is None:
            return value
        value = value.strip().lower()
        values = value.split('/')
        for value in values:
            if value in ['m', 'male', 'man', 'boy']:
                return self.MALE
            elif value in ['f', 'female', 'woman', 'girl']:
                return self.FEMALE

        return self.UNKNOWN

    #def get_prep_value(self, value):
    #    if value is None:
    #        return value
    #    return super().get_prep_value(value.upper())  # Ensure the value is in the correct format for the database


class IntegerField(models.IntegerField):
    def __init__(self, *args, form_blank=None, db_null=None, **kwargs):
        if 'blank' in kwargs:
            pass
            #TODO: enable the warning
            #logger.warn("Use `form_blank` instead of `blank` to control form behavior.")
            #raise TypeError("Use `form_blank` instead of `blank` to control form behavior.")

        if 'null' in kwargs:
            pass
            #TODO: enable the warning
            #logger.warn("Use `db_null` instead of `null` to control database behavior.")
            #raise TypeError("Use `db_null` instead of `null` to control database behavior.")

        defaults = {
            'blank': True if form_blank is None else form_blank,
            'null': True if db_null is None else db_null,
        }
        defaults.update(kwargs)
        super().__init__(*args, **defaults)

class DotDict(dict):
    """A dictionary subclass supporting dot notation access with deep conversion of nested structures."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._convert_nested()

    def _convert_nested(self):
        """Recursively converts nested dictionaries to DotDict instances, including those in lists."""
        for key, value in self.items():
            self[key] = self._convert_value(value)

    def _convert_value(self, value):
        """Convert a value to DotDict if it's a dict, or recursively process lists/tuples containing dicts."""
        if isinstance(value, dict) and not isinstance(value, DotDict):
            return DotDict(value)
        elif isinstance(value, list):
            return [self._convert_value(item) for item in value]
        elif isinstance(value, tuple):
            return tuple(self._convert_value(item) for item in value)
        return value

    def __getattr__(self, attr):
        if attr in self:
            return self[attr]
        raise AttributeError(f"'DotDict' object has no attribute '{attr}'")

    def __setattr__(self, attr, value):
        self[attr] = self._convert_value(value)

    def __delattr__(self, attr):
        if attr in self:
            del self[attr]
        else:
            raise AttributeError(f"'DotDict' object has no attribute '{attr}'")

    def __setitem__(self, key, value):
        super().__setitem__(key, self._convert_value(value))

class JSONField(models.JSONField):
    def __init__(self, *args, default=dict, form_blank=None, db_null=None, encoder=None, **kwargs):
        if 'blank' in kwargs:
            pass
            #TODO: enable the warning
            #logger.warn("Use `form_blank` instead of `blank` to control form behavior.")
            #raise TypeError("Use `form_blank` instead of `blank` to control form behavior.")

        if 'null' in kwargs:
            pass
            #TODO: enable the warning
            #logger.warn("Use `db_null` instead of `null` to control database behavior.")
            #raise TypeError("Use `db_null` instead of `null` to control database behavior.")

        if default == {} and isinstance(default, dict):
            default = DotDict(default)

        defaults = {
            'default': default,
            'blank': True if form_blank is None else form_blank,
            'null': True if db_null is None else db_null,
            'encoder': serializers.CustomJSONEncoder,
        }
        defaults.update(kwargs)
        super().__init__(*args, **defaults)

    def from_db_value(self, value, expression, connection):
        """Converts JSON from the database into a DotDict."""
        if value is None:
            return None
        if isinstance(value, str):
            value = json.loads(value)  # Convert JSON string to dict
        return DotDict(value) if isinstance(value, dict) else value
