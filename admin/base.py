import logging
from collections import Counter, defaultdict
from copy import copy
from functools import wraps

from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.http import QueryDict
from django.urls import reverse
from django.utils.html import format_html

logger = logging.getLogger(__name__)

class AutocompleteSelectWithPlaceholder(admin.options.AutocompleteSelect):
    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        if 'data-placeholder' in base_attrs:
            attrs['data-placeholder'] = base_attrs['data-placeholder']
        else:
            attrs['data-placeholder'] = 'Select'

        return attrs

admin.options.AutocompleteSelect = AutocompleteSelectWithPlaceholder

def admin_action(*args, **kwargs):
    """Wrapper for registering admin actions and add a log message"""
    def decorator(func):
        @wraps(func)
        def wrapper(modeladmin, request, queryset):
            logger.info(f"Executing admin action '{func.__name__}' with queryset: {queryset}")
            response = func(modeladmin, request, queryset)

            # Log the action for each object in the queryset
            for obj in queryset:
                admin.models.LogEntry.objects.log_action(
                    user_id=request.user.id,
                    content_type_id=ContentType.objects.get_for_model(obj).pk,
                    object_id=obj.pk,
                    object_repr=str(obj),
                    action_flag=admin.models.CHANGE,
                    change_message=f"Custom admin action '{func.__name__}' performed."
                )

            return response

        # Apply Django's original @admin.action decorator
        original_action_decorator = admin.action(*args, **kwargs)
        return original_action_decorator(wrapper)

    return decorator

admin_action = admin_action


class AutoFieldsetsMixin:
    """
    Automatically puts model fields with common prefix
    into fieldsets in Django Admin change views.
    """

    prefix_separator = "_"
    min_group_size = 3

    def get_fieldsets(self, request, obj=None):
        # Step 1: Build prefix frequency map
        field_names = [
            f.name for f in self.model._meta.get_fields()
            if getattr(f, "editable", False) and not f.auto_created
        ]

        prefix_counts = Counter()
        field_to_prefix = {}

        for name in field_names:
            parts = name.split(self.prefix_separator)
            for i in range(1, len(parts)):
                prefix = self.prefix_separator.join(parts[:i])
                prefix_counts[prefix] += 1

        # Step 2: Assign longest valid prefix to each field
        for name in field_names:
            parts = name.split(self.prefix_separator)
            longest_valid = None
            for i in range(len(parts), 0, -1):
                prefix = self.prefix_separator.join(parts[:i])
                if prefix_counts[prefix] >= self.min_group_size:
                    longest_valid = prefix
                    break
            field_to_prefix[name] = longest_valid

        # Step 3: Group fields by prefix
        grouped = defaultdict(list)
        for name in field_names:
            key = field_to_prefix[name]
            grouped[key].append(name)

        # Step 4: Preserve field order in output
        fieldsets = []
        general_fields = []
        used = set()

        for name in self.model._meta.fields:
            fname = name.name
            if fname not in field_names or fname in used:
                continue
            group = field_to_prefix[fname]
            if group and grouped[group][0] == fname:
                fieldsets.append((
                    group.replace(self.prefix_separator, " ").capitalize(),
                    {'fields': grouped[group]}
                ))
                used.update(grouped[group])
            elif not group:
                general_fields.append(fname)
                used.add(fname)

        if general_fields:
            fieldsets.insert(0, ("General", {'fields': general_fields}))

        return fieldsets

class BaseModelAdmin(admin.ModelAdmin):
    change_list_template = "admin/repeat_last_action_change_list.html"

    filter_input_length = {}

    actions = list(admin.ModelAdmin.actions)
    #actions = ['translate_selected_objects']

    formfield_overrides = {
        models.DateField: {
            'widget': admin.widgets.AdminDateWidget(attrs={'placeholder': 'yyyy-mm-dd'}),
        },
    }

    # Step 1: Override get_readonly_fields to include all `editable=False` fields automatically
    def get_readonly_fields(self, request, obj=None):
        """
        Returns unordered list of readonly fields.
        """
        readonly_fields = list(super().get_readonly_fields(request, obj))
        # Add all fields that have `editable=False`
        for field in self.model._meta.fields:
            if not field.editable and field.name not in readonly_fields:
                readonly_fields.append(field.name)
        readonly_fields.append('id')
        #logger.debug('Readonly fields: ', readonly_fields)
        return readonly_fields

    def get_exclude(self, request, obj=None):
        excluded_fields = list(super().get_exclude(request, obj) or [])
        #logger.debug('Excluded fields: ', excluded_fields)
        return excluded_fields


    def get_fields(self, request, obj=None):
        """
        Returns ordered list of all fields shown in Django Admin model change view.
        """
        # Retrieve all field names from the model
        if self.fields:
            return self.fields

        # Get excluded fields
        excluded_fields = self.get_exclude(request, obj) or []

        all_fields = []

        # Existing record being edited
        if obj:
            all_fields = [field.name for field in self.model._meta.get_fields() if not field.auto_created]
            if 'id' not in all_fields:
                all_fields.insert(0, 'id')
            # Ensure all readonly fields are included
            for field in self.get_readonly_fields(request, obj):
                if field not in all_fields:
                    all_fields.append(field)

        # New record being created
        else:
            all_fields = [field.name for field in self.model._meta.get_fields() if not field.auto_created and field.editable]

        all_fields = [field for field in all_fields if field not in excluded_fields]

        return all_fields

    def get_actions(self, request):
        actions = super().get_actions(request)

        def get_action_description(action_tuple):
            """ Helper function to get action description """
            return action_tuple[2] if len(action_tuple) > 2 else action_tuple[0].__name__

        # Sort actions by their description
        sorted_actions = sorted(actions.items(), key=lambda item: get_action_description(item[1]))
        return dict(sorted_actions)

    @admin_action(description="Translate fields to German")
    def translate_selected_objects(self, request, queryset):
        for obj in queryset:
            obj.translate_fields()
        self.message_user(request, "Selected objects have been translated")

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        last_action = request.session.get('last_admin_action', {})

        # Extract the current model
        model = f'{self.model._meta.app_label}.{self.model._meta.model_name}'

        #logger.debug(f"changelist_view called for {model} with last_action:\n{pretty(last_action[model])}")

        # Filter the last action based on the current model
        if model in last_action:
            last_action_copy = copy(last_action[model])
            if isinstance(last_action_copy['data'], str):
                # We need to work with a copy or else we are modifying the session
                last_action_copy['data'] = QueryDict(last_action_copy['data']).lists()
            extra_context['last_action'] = last_action_copy

        #logger.debug(f"changelist_view called for {model} with extra_context:\n{pretty(extra_context)}")

        return super().changelist_view(request, extra_context=extra_context)

    def get_change_link(self, record):
        url = reverse(f'admin:{record._meta.app_label}_{record._meta.model_name}_change', args=[record.pk])
        return  format_html('<a href="{}">{}</a>', url, record)

    def get_list_display(self, request):
        list_display = super().get_list_display(request)

        # Ensure list_display is a list
        if isinstance(list_display, tuple):
            list_display = list(list_display)

        field_names = [field.name for field in self.model._meta.get_fields()]

        if 'id' not in list_display and 'id' in field_names:
            list_display.insert(0, 'id')  # Insert 'id' at the beginning

        return list_display

    def get_list_display_links(self, request, list_display):
        # Dynamically add links to the first and second columns if they exist in list_display
        if len(list_display) >= 2:
            return (list_display[0], list_display[1])
        if len(list_display) == 1:
            return (list_display[0],)
        return ()
