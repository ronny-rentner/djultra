# Django tricks

Adding meta options to Django models:
```
    # Allow Django models to define `serializer_defaults` attribute as a model._meta option
    import django.db.models.options as options
    options.DEFAULT_NAMES = (*options.DEFAULT_NAMES, 'serializer_defaults')      
```

# djultra Feature Overview

`djultra` is a reusable Django extension layer for project scaffolding, admin automation, model helpers, DRF serializers, logging, middleware, and development commands.

## Core Model Helpers

- `BaseModel`: abstract model with `created_at`, `updated_at`, `get_admin_url()`, `admin_link()`, and `to_dict()`.
- `BaseQuerySet.delete()`: calls each instance’s `delete()` before running bulk deletion.
- `admin_action()`: decorator for marking model methods as generated Django admin actions.

## Admin System

- Auto-registers models from `INSTALLED_ULTRA_APPS` when they define an inner `Admin` class.
- Builds dynamic `ModelAdmin` classes with `BaseModelAdmin` and `AutoFieldsetsMixin`.
- Converts decorated model methods into admin actions with success, warning, and failure reporting.
- Adds admin action logging and repeat-last-action support through session state and custom admin templates.
- Improves admin defaults by including `id`, linking early list columns, sorting actions, making `editable=False` fields readonly, and grouping fields by shared prefixes.

## Fields

- `CountryField`: normalizes country input through `django-countries`, with optional custom mappings.
- `DecimalField`: parses German and English decimal formats.
- `CharField`: provides default `max_length`, blank/null/default handling, and light text cleanup.
- `DateField`: parses messy date formats and localized month abbreviations.
- `GenderField`: normalizes common gender strings into compact choices.
- `IntegerField`: provides default blank/null handling.
- `DotDict`: nested dictionary wrapper with dot-style access.

## Serializers

- `CustomJSONEncoder` and `CustomJSONSerializer`: handle dates, datetimes, decimals, and Django models.
- `DynamicFieldsModelSerializer`: runtime-configurable DRF serializer with selected fields, dynamic method/property fields, exclusions, and relation serialization.
- `ModelMethodField`: exposes model methods and properties as serializer fields.
- `NoPagination`: returns full querysets without pagination wrapping.

## Middleware

- Request ID tracking with thread-local access and CSP nonce integration.
- Separate admin/API session cookie names.
- Admin action POST tracking for repeat-action UI.
- Query count and slow-query logging.
- Cookie `Partitioned` support through a `Morsel` patch.
- Artificial delay middleware for testing slow endpoints.
- Dev proxy and sequence-adjustment middleware exist as experimental helpers.

## Settings & Development Workflow

- `djultra.settings`: Rich logging, static/media paths, Django Vite paths, CSP defaults, middleware insertion, and dev flags.
- `dev` management command: runs the Django dev server with a `django-tasks` DB worker and fastmanage daemon.
- `fastmanage_*` commands: socket-backed path for faster Django management commands.
- `ConfigLoader`: reads environment variables first, then an optional config file, with type casting from defaults.

## Current Cleanup Notes

- `djultra.settings` still contains project-specific assumptions such as frontend paths, Vite/static layout, `sign.relonee.com` CSP entries, and localhost dev hosts.
