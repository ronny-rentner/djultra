# Django tricks

Adding meta options to Django models:
```
    # Allow Django models to define `serializer_defaults` attribute as a model._meta option
    import django.db.models.options as options
    options.DEFAULT_NAMES = (*options.DEFAULT_NAMES, 'serializer_defaults')      
```

# djultra Feature Overview

`djultra` is a reusable Django extension layer for project scaffolding, admin automation, model helpers, DRF serializers, logging, middleware, and development commands.

## Conventions

djultra preserves the package structure it was extracted from: a module lives in its sub-package (`djultra/services/email.py`, `djultra/models/base.py`), never flattened to a top-level module. Call functions through their module path rather than importing the bare name — it reads better and shows where the function lives and how the code is structured:

```python
from djultra import services

services.email.send_templated_email(subject=..., template_name=..., context=..., recipient_list=...)
# not: from djultra.services.email import send_templated_email; send_templated_email(...)
```

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

## Frontend Shell

- `djultra.views.index`: renders the SPA shell, exposing djultra's frontend config to
  the page — `apiBaseUrl` (`FRONTEND_API_URL`), `recaptchaKey` (`RECAPTCHA_SITE_KEY`),
  and the CSP `nonce`. Point a project's SPA catch-all route at it.
- `templates/index.html`: the default shell `index` renders; a site overrides it by
  shipping its own `index.html` in an app searched before djultra.

## Settings & Development Workflow

- `djultra.settings`: Rich logging, static/media paths, Django Vite paths, CSP defaults, middleware insertion, and dev flags.
- `dev` management command: improved development server with local task and fastmanage workers.
- Fastmanage: optional socket-backed acceleration for repeated `manage.py` / `django-admin` invocations.
- `ConfigLoader`: resolves a value from an optional namespace (`if_not_in_ns`), then environment variables, then an optional config file, with type casting derived from the default.

## Settings Injection

A project loads `djultra.settings` (and the settings of any other ultra app)
into its own `settings.py` via ultraimport, which executes the fragment
inside the project's namespace:

```python
for app in INSTALLED_ULTRA_APPS:
    path = ultraimport.search_module_path(app)
    settings_file_path = f"{path}/settings.py"
    if os.path.exists(settings_file_path):
        ultraimport(settings_file_path, '*', inject=globals(), add_to_ns=True)
```

The fragment expects the project to define `BASE_DIR` and `MIDDLEWARE`
before the injection (it raises `ImproperlyConfigured` otherwise) and wraps
the project's `MIDDLEWARE` list with djultra middleware. Everything else
fills gaps only — each value resolves in this order:

1. an assignment the project already made (`if_not_in_ns=globals()`)
2. an environment variable of the same name
3. the `[DEFAULT]` section of the config file (`CONFIG_FILE`)
4. the built-in default

Defaults aim at the local dev environment; the live production site is the
special case and overrides via environment variables or the config file.

| Variable | Default | Meaning |
| -------- | ------- | ------- |
| `DEBUG` | `True` | Django debug mode; selects the dev branches (vite dev server, static dirs, full debug logging) |
| `LOG_LEVEL` | `ERROR` | console log level for production; ignored while `DEBUG` is on — everything logs at DEBUG level then |
| `FRONTEND_URL` | `http://localhost:5173` | origin of the frontend dev server; feeds CORS, CSRF trust and CSP |
| `FRONTEND_API_URL` | `http://localhost:8000/api` | base URL the SPA calls for the API; passed into the index template |
| `CSP_EXTRA_HOST` | `''` | extra host allowed by the CSP directives for deployment-specific cases |
| `CSRF_TRUSTED_ORIGINS` | `[FRONTEND_URL]` | origins trusted for CSRF |
| `CONFIG_FILE` | `/dev/null` | path of the INI config file read by `ConfigLoader` |
| `RECAPTCHA_SECRET_KEY` | `''` | server-side reCAPTCHA secret used by the sign-in flow |
| `RECAPTCHA_SITE_KEY` | `''` | public reCAPTCHA site key; passed into the index template |
| `EMAIL_BACKEND` | `djultra.services.email.Backend` | SMTP backend that can also echo mail to the console |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` / `EMAIL_USE_TLS` | `localhost` / `25` / `''` / `''` / `False` | standard Django SMTP settings |
| `EMAIL_PRINT_TO_CONSOLE` | `DEBUG` | also print sent mail to the console |
| `DEFAULT_FROM_EMAIL` | `webmaster@localhost` | default From address for outgoing mail |

Project-specific overrides of injected values belong below the injection
loop in the project's settings.

## Configuration

`ConfigLoader` is the single mechanism behind every `config()` call in
settings. A lookup like `config('DEBUG', default=True)` resolves in this
order:

1. an existing assignment in a namespace, when the call passes
   `if_not_in_ns=globals()` — internal use by the settings injection above
2. the environment variable of the same name
3. the `[DEFAULT]` section of the INI file that `CONFIG_FILE` points to
4. the `default` argument

Values from env and INI arrive as strings and are cast based on the type
of the default: booleans accept `true/1/yes/on`, lists are comma-separated
(`ALLOWED_HOSTS=example.com,www.example.com`), ints and floats convert.

### Per-environment config files

Each environment can ship an INI with its non-secret values and select it
via `CONFIG_FILE`:

```ini
; prod_django.ini — committed, baked into the image
[DEFAULT]
DEBUG               = False
ALLOWED_HOSTS       = example.com,www.example.com
FRONTEND_URL        = https://example.com
FRONTEND_API_URL    = https://example.com/api
LOG_LEVEL           = DEBUG
```

Secrets (database credentials, `SECRET_KEY`) and the `CONFIG_FILE` pointer
itself stay in environment variables — for docker, an uncommitted
`<env>.env` file loaded via `env_file`, selected by an `ENV` variable:

```bash
# prod.env — NOT committed, contains secrets
ENV=prod
DB_PASSWORD=...
SECRET_KEY=...
CONFIG_FILE=./docker/prod_django.ini
```

Environment variables always override the INI, so any value can be changed
ad hoc without touching a file:

```console
$ DEBUG=false LOG_LEVEL=WARNING python manage.py dev
```

With neither env vars nor a config file present, the defaults apply — and
they are chosen to run a local dev environment with zero configuration.

## Development Server

`djultra` adds an improved development server for Django projects that need more than the built-in `runserver`.

Run it like `runserver`:

```console
$ python manage.py dev
$ python manage.py dev 127.0.0.1:8000
$ python manage.py dev 0.0.0.0:8000
```

It keeps Django’s familiar local development server behavior: foreground process, host/port argument, autoreload, system checks, migration checks, and the normal WSGI development server. On top of that, `dev` starts the backend services that belong to the local development runtime:

- `django-tasks` database worker for local background jobs
- fastmanage daemon for faster repeated `manage.py` / `django-admin` invocations
- named processes that are easy to inspect with `ps`
- reload-aware helper processes that are recreated with the active dev server
- shutdown handling for the helper processes when the dev server exits

This gives one Django entry point for the local backend stack: web server, task worker, and fastmanage.

The processes are intentionally named:

```console
$ ps ux | grep django
ronny      43940  0.0  0.1  50168 39024 pts/6    S+   07:14   0:00 /home/ronny/Projects/django-svelte-starter/backend/venv/bin/python /home/ronny/Projects/django-svelte-starter/cli/cli.py run
ronny      43942  0.1  0.2  95200 78096 pts/6    S+   07:14   0:00 django-main
ronny      43945  0.2  0.2 173324 84756 pts/6    Sl+  07:14   0:00 django-dev-server
ronny      43947  0.0  0.1  95204 63456 ?        Ss   07:14   0:00 django-fastmanage-daemon
ronny      43948  0.1  0.2  95600 71352 ?        Ss   07:14   0:00 django-tasks-db-worker
```

`django-main` is the controlling Django process for the development server lifecycle. It participates in Django’s autoreload flow, so helper processes are not left behind when code changes trigger a reload.

`django-dev-server` is the active Django development server for the current reload generation. It owns the local backend runtime for that generation: it starts the fastmanage daemon and task worker, then shuts them down before it exits.

`django-fastmanage-daemon` listens for fastmanage-enabled management commands.

`django-tasks-db-worker` processes queued tasks from the `django-tasks` database backend.

## Fastmanage

Django administrative tasks are normally invoked through `python manage.py <command>` or `django-admin <command>`. Each invocation starts a fresh Python process, imports the project, initializes Django, resolves the command, and then runs it. Fastmanage keeps the command semantics the same, but avoids part of that cold-start cost during development.

Fastmanage has two parts: a daemon process and a client patch.

The daemon is a long-lived process that listens on `fastmanage.sock` in the project directory. In the common development flow, `djultra` starts it from the `dev` command. That `dev` command is still based on Django’s normal runserver command, but before serving requests it forks child processes for development helpers such as the `django-tasks` database worker and the fastmanage daemon. The daemon does not conceptually depend on runserver; `dev` is the integrated launcher for the full local development setup.

The client side is enabled explicitly by the project. Installing `djultra` does not change `manage.py` behavior. To opt in, import the patch before calling Django’s command runner:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import djultra.management.commands.fastmanage_patch
from django.core.management import execute_from_command_line
```

That import replaces Django’s `ManagementUtility` in the current process. When `manage.py` or a project CLI runs a command, the patched utility checks for `fastmanage.sock`. If the socket is missing or cannot be opened, it delegates to Django’s normal `ManagementUtility`, so commands still work without the daemon.

When the socket is available, the client sends the caller’s environment and quoted `argv` to the daemon. It also passes stdin, stdout, and stderr file descriptors with Unix `SCM_RIGHTS`. Command output is not proxied through the socket; the worker writes to the caller’s original stdout and stderr.

For each request, the daemon forks a worker. The worker updates `os.environ`, changes to the caller’s `PWD`, restores `sys.argv`, disables recursive socket routing with `use_socket=False`, and then runs Django’s normal management command machinery.

The socket acts as the request, completion, and exit-status channel. Workers send a plain ASCII integer status over the socket before closing it, and the client exits with that status. Workers exit with `os._exit()` so inherited daemon shutdown handlers do not run inside command workers; because `os._exit()` skips Python’s implicit stream flushing, the worker flushes stdout and stderr before sending the status and closing the socket.

## Current Cleanup Notes

- `djultra.settings` still assumes the standard project layout: `frontend/src/assets`, `static/src`, `static/frontend`, and `static/collected` under `BASE_DIR`.
