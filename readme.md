# Django tricks

Adding meta options to Django models:
```
    # Allow Django models to define `serializer_defaults` attribute as a model._meta option
    import django.db.models.options as options
    options.DEFAULT_NAMES = (*options.DEFAULT_NAMES, 'serializer_defaults')      
```
