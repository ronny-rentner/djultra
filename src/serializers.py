import json
import logging
from datetime import date, datetime
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.core.signing import JSONSerializer
from django.db.models import Model
from rest_framework import pagination, serializers

#from django_countries.fields import Country


logger = logging.getLogger(__name__)

class CustomJSONEncoder(DjangoJSONEncoder):
    """Custom JSON Encoder to handle additional types, including Django models."""

    def default(self, obj):
        logger.debug('CUSTOM JSON: ', type(obj), obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()  # Convert date/datetime to ISO 8601 format
        if isinstance(obj, Decimal):
            return format(obj, 'f').rstrip('0').rstrip('.')
        if isinstance(obj, Model):
            if hasattr(obj, "to_json") and callable(obj.to_json):
                return obj.to_json()  # Call the model's `to_json` method
            return str(obj)  # Fallback to string representation
        return super().default(obj)


class CustomJSONSerializer(JSONSerializer):
    """
    Custom JSON Serializer that uses the CustomJSONEncoder.
    User for serializing Session objects (configured in settings.py).
    """

    def dumps(self, obj):
        #ret = super().dumps(obj)
        #logger.debug('dumps: ', obj)
        #return ret
        #return json.dumps(obj, cls=DjangoJSONEncoder)
        return json.dumps(obj, separators=(",", ":"), cls=CustomJSONEncoder).encode("utf8")

    def loads(self, data):
        #logger.debug('loads: ', data)
        # Use standard json.loads, with optional custom decoding if necessary
        return json.loads(data)

def create_custom_subclass(base_class, model, name_suffix):
    """
    Dynamically creates a subclass of base_class with a unique name and correct Meta class.
    """
    Meta = type('Meta', (), {
        'model': model,
        'fields': '__all__',
    })

    # Generate a unique class name by appending a suffix
    subclass_name = f"{base_class.__name__}_{name_suffix}"

    # Dynamically create a subclass with a unique name and Meta class
    return type(subclass_name, (base_class,), {'Meta': Meta, '__module__': __name__})

class ModelMethodField(serializers.Field):
    """
    A custom field that calls a specified method on the model instance.
    Dynamically determines the field type based on the return value.
    """
    def __init__(self, method_name=None, **kwargs):
        self.method_name = method_name
        kwargs['source'] = '*'  # Bypass attribute lookup; we’ll handle this
        kwargs['read_only'] = True
        super().__init__(**kwargs)

    def bind(self, field_name, parent):
        """
        Set a default method name if none is provided, like `get_{field_name}`.
        """
        if self.method_name is None:
            self.method_name = f'{field_name}'
        super().bind(field_name, parent)

    def get_field_value(self, obj, field_name):
        #logger.debug('get_field_value()', field_name, __class__, __name__)
        if '.' not in field_name:
            return getattr(obj, field_name, None)
        parts = field_name.split('.')
        for part in parts:
            #logger.debug('PART: ', part)
            try:
                obj = getattr(obj, part, None)
                #logger.debug('OBJ: ', obj, type(obj))
                if obj is None:
                    break
            except ValueError:
                logger.warn(f'Cannot fetch "{part}" from "{field_name}"')
                break
        #logger.debug('RESULT: ', obj)
        return obj

    def to_representation(self, instance):
        """
        Call the specified or default method on the model instance.
        """

        # Allow 'get_{method_name}' for fetching the data if it exists
        if not hasattr(instance, self.method_name) and '.' not in self.method_name:
            potential_method_name = f'get_{self.method_name}'
            if hasattr(instance, potential_method_name):
                self.method_name = potential_method_name
            else:
                logger.warn(f'Cannot find attribute: name={self.method_name} instance={type(instance)}')

        # Retrieve the method on the model instance
        method = getattr(instance, self.method_name, None)
        value = None
        if callable(method):
            value = method()
        else:
            # method actually is just a property or attribute
            try:
                value = self.get_field_value(instance, self.method_name)
            except Exception as e:
                logger.error('Failed getting field value', e)
            #value = self.method_name

        #logger.debug('ModelMethodField', type(value), type(instance), instance.__class__.__name__, self.method_name, method, value)

        # Dynamically serialize the value based on its type.
        # The order of checks is important, bool must come first.
        if isinstance(value, bool):
            return serializers.BooleanField().to_representation(value)
        elif isinstance(value, tuple):
            child_field = serializers.IntegerField() if all(isinstance(v, int) for v in value) else serializers.CharField()
            return serializers.ListField(child=child_field).to_representation(value)
        elif isinstance(value, list):
            child_field = serializers.IntegerField() if all(isinstance(v, int) for v in value) else serializers.CharField()
            return serializers.ListField(child=child_field).to_representation(value)
        elif isinstance(value, int):
            return serializers.IntegerField().to_representation(value)
        elif isinstance(value, str):
            return serializers.CharField().to_representation(value)
        elif isinstance(value, bool):
            return serializers.BoolField().to_representation(value)
        # Add more types as needed

        # This is strange. It seems if value is an object that evaluates to None,
        # some part in DRF serializer will fail and it only works if we return plain None
        if not value:
            return None

        # Return as-is for unsupported types
        return value

class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):

        self._late_init = False

        context = kwargs.get('context', {})
        defaults = {}

        def get_param(name, default):
            if context:
                return context.get(name, defaults.get(name, default))
            else:
                return kwargs.pop(name, defaults.get(name, default))

        model = get_param('model', None)

        if not model and not context and len(args) > 0 and isinstance(args[0], Model):
            model = type(args[0])

        if model:
            self.Meta.model = model
            if hasattr(model._meta, 'serializer_defaults'):
                defaults = self.Meta.model._meta.serializer_defaults

        #logger.debug('Serializer defaults: ', defaults, model, args, kwargs)
        self._fields = get_param('fields', [])
        self._dynamic = get_param('dynamic', [])
        self._exclude = get_param('exclude', [])
        self._relations = get_param('relations', {})
        self.methods = get_param('methods', {})


        super().__init__(*args, **kwargs)

    def late_init(self):
        """
        Called lazily when only trying to get a representation. This ensures
        that Django's app and model registry is already initialized and we can
        loop over model fields.
        """
        # Do not run a second time
        if self._late_init:
            return
        self._late_init = True


        if self._fields == '__all__':
            for field_name in self._exclude:
                self.fields.pop(field_name, None)
        else:
            allowed = set(self._fields)
            allowed.update(self._dynamic)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name, None)

        for field in self._dynamic:
            # Check if the field is a tuple (field_name, method_name)
            #logger.warn('DYNAMIC: ', field)
            if isinstance(field, tuple):
                field_name, method_name = field
            else:
                field_name = method_name = field

            # Assign the custom ModelMethodField with the resolved method name
            self.fields[field_name] = ModelMethodField(method_name=method_name)

            # Handle related fields by creating a custom subclass for each relation
            for field_name, relation_info in self._relations.items():
                RelatedSerializerClass = create_custom_subclass(
                    base_class=DynamicFieldsModelSerializer,
                    model=relation_info['model'],
                    name_suffix=field_name
                )
                # Instantiate the serializer with the provided context
                self.fields[field_name] = RelatedSerializerClass(
                    many=True,
                    read_only=True,
                    context=relation_info
                )


    def to_representation(self, instance):

        self.late_init()

        # Get the default representation
        rep = super().to_representation(instance)

        #logger.debug(f'Generating API representation for instance={instance}:', rep)

        # self._context gives us the local context instead of self.context which gives
        # the root serializer context
        for field_name, relation_info in self._context.get('relations', {}).items():
            # Skip normal relations (i.e., no 'method' key)
            if 'method' not in relation_info:
                continue

            # Call the method to get the result
            method_name = relation_info['method']
            method = getattr(instance, method_name, None)
            if callable(method):
                value = method()  # This is the data we want to serialize

                # Here we manually assign the data (the value) to the field serializer
                #self.fields[field_name].data = value  # This will not actually work, but shows intent
                rep[field_name] = self.fields[field_name].to_representation(value)  # Pass value for serialization

                #logger.debug('TO REP FIELD', field_name, rep[field_name], self.fields[field_name], value)
                #logger.warn('CALLABLE: ', field_name, method_name)
            else:
                #logger.warn('NOT CALLABLE: ', field_name, method_name)
                logger.warn(f'Serializer method not callable: field={field_name} method={method_name} instance={instance}')


        return {key.replace('.', '_'): value for key, value in rep.items()}

    class Meta:
        fields = '__all__'
        # Handled manually
        #exclude = None

class NoPagination(pagination.BasePagination):
    def paginate_queryset(self, queryset, request, view=None):
        return queryset

    def get_paginated_response(self, data):
        return Response({
            'count': len(data),
            'results': data  # The actual data
        })
