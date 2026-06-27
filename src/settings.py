# Injected into the including project's settings via ultraimport
# (inject=globals()), so it runs with that module's namespace: it expects
# BASE_DIR and MIDDLEWARE to be defined before the injection (MIDDLEWARE
# gets wrapped with djultra middleware). Everything else fills gaps only:
# a value the project already defined wins (if_not_in_ns), otherwise env
# and config file are consulted, and the defaults aim at local dev —
# production is the special case and overrides via env vars.

import re

from django.core.exceptions import ImproperlyConfigured

for name in ('BASE_DIR', 'MIDDLEWARE'):
    if name not in globals():
        raise ImproperlyConfigured(f"djultra settings expect '{name}' to be defined in the project settings before the app-settings injection")

if 'config' not in globals():
    from djultra.utils.config_loader import ConfigLoader
    config = ConfigLoader()
    config.config_file = config('CONFIG_FILE', default='/dev/null')

# Django debug mode; also selects the dev branches below (vite dev server,
# static dirs) and full debug logging
DEBUG = config('DEBUG', default=True, if_not_in_ns=globals())

# Console log level for production; only effective when DEBUG is off —
# with DEBUG on, everything logs at DEBUG level regardless
LOG_LEVEL = config('LOG_LEVEL', default='ERROR', if_not_in_ns=globals())

# Origin the frontend dev server runs on; feeds CORS, CSRF trust and CSP
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173', if_not_in_ns=globals())

# Base URL the SPA calls back to for the API; passed into the index template
FRONTEND_API_URL = config('FRONTEND_API_URL', default='http://localhost:8000/api', if_not_in_ns=globals())

#############
## LOGGING ##
#############

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    # https://docs.djangoproject.com/en/5.2/topics/logging/
    # A logger is the entry point into the logging system.
    # Each logger is a named bucket to which messages can be written for processing.
    'loggers': {
        'django': {
            #'handlers': ['console'],
            'level': 'DEBUG',
            #'propagate': False,
        },
        'django.utils.autoreload': {
            'level': 'INFO',
        },
        'django.db.backends': {
            'level': 'INFO',
            #'level': 'DEBUG',
        },
        'django.template': {
            #'level': 'DEBUG',
            'level': 'INFO',
        },
        #'Relonee': {
        #    'handlers': ['console'],
        #    'level': 'DEBUG',
        #    'propagate': False,
        #},
        #'cities_light': {
        #    'handlers':['console'],
        #    'propagate': True,
        #    'level':'DEBUG',
        #},
    },
    
    # Parent root logger (in case no more specific logger is defined)
    'root': {
        'handlers': ['console'],
        #'level': 'INFO',
        'level': 'DEBUG',
    },

    "formatters": {
        "rich": {
            "datefmt": "%X",
            "format": "%(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "djultra.logging.CustomRichHandler",
            "formatter": "rich",
            "level": "DEBUG" if DEBUG else LOG_LEVEL,
            "rich_tracebacks": True,
            "tracebacks_show_locals": False,
            # Has to be a part of a directory or path name
            "tracebacks_suppress": ['venv', '/usr/lib'],
            #"tracebacks_width": 100,
            "markup": False,
        }
    },
}


MIDDLEWARE = [
    # Patches Python's built-in Cookie Morsel to allow
    # partioned cookies and set all cookies as partitioned
    # by default
    'djultra.middleware.PatchMorselMiddleware',
    'djultra.middleware.RequestIDMiddleware',

    # Allows having a Django Admin session in parallel to an API session
    'djultra.middleware.AdminSessionMiddleware',

    *MIDDLEWARE,

    # Self-heals lagging postgres id sequences on duplicate-pkey errors and
    # retries; innermost, so the retried response still passes through the
    # response phase of all other middleware
    'djultra.middleware.AdjustSequenceMiddleware',

    'djultra.middleware.AdminActionLoggerMiddleware', # Run after SessionMiddleware

    # Logs slow queries and number of queries (so far only usefull in dev env).
    'djultra.middleware.QueryLoggingMiddleware',

    # Test slow API responses
    #'djultra.middleware.ArtificialDelayMiddleware',
]

##############
## REST API ##
##############

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 100,
}

#TODO: debug is not necessarily dev environment
# Adjust renderers based on the environment
if not DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = (
        'rest_framework.renderers.JSONRenderer',
    )
else:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    )

AUTHENTICATION_BACKENDS = [
    'djultra.authentication.TokenBackend',
    # For Django Admin
    'django.contrib.auth.backends.ModelBackend',
]

# reCAPTCHA keys default to Google's universal test keys, which always validate
# (the widget shows a "for testing only" banner) so the forms work out of the
# box. Override with real keys via env / CONFIG_FILE in production.
# Secret for server-side reCAPTCHA verification (sign-in + contact flows)
RECAPTCHA_SECRET_KEY = config('RECAPTCHA_SECRET_KEY', default='6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe', if_not_in_ns=globals())

# Public site key for the reCAPTCHA widget; passed into the index template
RECAPTCHA_SITE_KEY = config('RECAPTCHA_SITE_KEY', default='6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI', if_not_in_ns=globals())

########################
## SESSIONS & SECURITY ##
########################

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'None'

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'None'

CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default=[FRONTEND_URL])

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = 'SAMEORIGIN'

###########
## EMAIL ##
###########

EMAIL_BACKEND = config('EMAIL_BACKEND', default='djultra.services.email.Backend', if_not_in_ns=globals())
EMAIL_HOST = config('EMAIL_HOST', default='localhost', if_not_in_ns=globals())
EMAIL_PORT = config('EMAIL_PORT', default=25, if_not_in_ns=globals())
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='', if_not_in_ns=globals())
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='', if_not_in_ns=globals())
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, if_not_in_ns=globals())

# Also print sent emails to the console; defaults to DEBUG (Relonee did this in dev)
EMAIL_PRINT_TO_CONSOLE = config('EMAIL_PRINT_TO_CONSOLE', default=DEBUG, if_not_in_ns=globals())

DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='webmaster@localhost', if_not_in_ns=globals())

##################
## CORS HEADERS ##
##################

# CORS_ALLOWED_ORIGINS — the browser origins (scheme://host:port) allowed to call
# this backend's API from JavaScript. It matters ONLY when the page making the
# request is served from a DIFFERENT origin than the API; same-origin requests skip
# CORS entirely.
#
# Why both localhost AND 127.0.0.1 below: browsers treat them as different origins
# even though they're the same machine. So opening the app at http://127.0.0.1:8000
# while the API URL names http://localhost:8000 (or vice versa) is a cross-origin
# call, and the page's origin has to be listed.
#
# To reach the dev server over the LAN (it binds 0.0.0.0, so it answers on every
# interface), add the exact origin you open in the browser — for example:
#
#     CORS_ALLOWED_ORIGINS += [
#         'http://192.168.1.50:8000',     # this machine's LAN IP
#         'http://mybox.fritz.box:8000',  # this machine's LAN hostname
#     ]
#
# Rules of thumb:
#   * Entries are EXACT strings — scheme, host and port must all match what's in
#     the address bar. No wildcards here (that's CORS_ALLOWED_ORIGIN_REGEXES).
#   * Add the same host to ALLOWED_HOSTS too, or Django rejects it with
#     DisallowedHost before CORS even runs.
#   * Prefer setting these per-environment via env / CONFIG_FILE. In PRODUCTION,
#     list only the real site origin(s) — the loopback entries below are dev-only.
CORS_ALLOWED_ORIGINS = [FRONTEND_URL]

if DEBUG:
    # Loopback origins for the Django-served SPA during local dev. Browsers treat
    # `localhost` and `127.0.0.1` as different origins, so both are listed. Kept
    # out of production: a credentialed CORS grant to localhost is needless
    # attack surface where the app is served from a real domain.
    CORS_ALLOWED_ORIGINS += [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]

# Allow specific HTTP methods
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# Allow specific headers
CORS_ALLOW_HEADERS = [
    "auth",
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "cookie",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

# Allow credentials (cookies, authorization headers)
CORS_ALLOW_CREDENTIALS = True

###################
## STATIC ASSETS ##
###################

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

DJANGO_VITE_DEV_MODE = DEBUG

STATIC_URL = '/static/'

STATIC_ROOT = BASE_DIR / 'static/collected'

if DEBUG:

    STATICFILES_DIRS = (
        BASE_DIR / 'static/src',
        BASE_DIR / 'static/frontend',
        #BASE_DIR / 'frontend',  # Directory for additional static files during development
        #BASE_DIR / 'frontend/public',  # Directory for additional static files during development
        ('src/assets', BASE_DIR / 'frontend/src/assets'),
    )

    DJANGO_VITE_ASSETS_PATH = BASE_DIR / "static" / "frontend"
    DJANGO_VITE_MANIFEST_PATH = BASE_DIR / "static/frontend/manifest.json"

else:

    DJANGO_VITE_ASSETS_PATH = STATIC_ROOT
    DJANGO_VITE_MANIFEST_PATH = STATIC_ROOT / 'manifest.json'



MEDIA_URL  = 'media/'
MEDIA_ROOT = BASE_DIR / "media"
TEMP_ROOT = MEDIA_ROOT / "temp"

# http://whitenoise.evans.io/en/stable/django.html#WHITENOISE_IMMUTABLE_FILE_TEST
def immutable_file_test(path: str, url: str) -> bool:
    if "." not in url:
        return False
    ext = url.rsplit(".", 1)[1].lower()
    return ext in {"jpg", "svg", "png", "woff", "woff2", "txt"}

WHITENOISE_IMMUTABLE_FILE_TEST = immutable_file_test

# Enable Gzip compression
#WHITENOISE_USE_FINDERS = True

# Enable Brotli compression (optional but recommended)
#WHITENOISE_USE_BROTLI = True
#STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
#STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

#WHITENOISE_MAX_AGE = 0



###################################
## CSP - Content Security Policy ##
###################################

from csp.constants import SELF, NONCE, NONE, UNSAFE_INLINE, STRICT_DYNAMIC

# TODO: Why?
#if not DEBUG:
#    CSP_EXTRA_HOST = "http://localhost:8000"
#else:
#    CSP_EXTRA_HOST = ""
CSP_EXTRA_HOST = config('CSP_EXTRA_HOST', default="", if_not_in_ns=globals())

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [
            SELF,
            FRONTEND_URL,
            NONCE,
            CSP_EXTRA_HOST,
        ],
        #"script-src": [
        #    SELF,
            #"https://www.recaptcha.net",
        #    NONCE,
        #],
        #"script-src-elem": [
        #    SELF,
        #    FRONTEND_URL,
        #    CSP_EXTRA_HOST,
        #    "https://www.recaptcha.net",
        #    # For pdfjs
        #    "https://cdnjs.cloudflare.com",
        #    NONCE,
        #],
        "style-src": [
            SELF,
            FRONTEND_URL,
            CSP_EXTRA_HOST,
            UNSAFE_INLINE,
        ],
        "frame-src": [
            SELF,
            FRONTEND_URL,
            CSP_EXTRA_HOST,
            "https://www.recaptcha.net",
            'blob:',
        ],
        "img-src": [
            SELF,
            FRONTEND_URL,
            CSP_EXTRA_HOST,
            "blob:",
            "data:",
        ],
        "connect-src": [
            SELF,
            #TODO: Needed only for vite on dev
            re.sub(r'^https?', 'ws', FRONTEND_URL),
            FRONTEND_URL,
            "https://www.recaptcha.net",
        ],
        "worker-src": [
            SELF,
            NONCE,
            'blob:',
        ],
        "object-src": [ NONE, ],
        "base-uri": [ SELF, ],
    },
}

# Dev only: the SPA may be opened at a loopback host (e.g. http://127.0.0.1:8000)
# while the API URL names the other (http://localhost:8000) — a cross-origin
# connection that 'self' doesn't cover. Add the same loopback origins as
# CORS_ALLOWED_ORIGINS so the page is allowed to reach the API. In production the
# page and API share the real origin, covered by 'self'.
if DEBUG:
    CONTENT_SECURITY_POLICY["DIRECTIVES"]["connect-src"] += [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]



##############
## DEV MODE ##
##############

# Fastmanage daemon

# DJU_DEV_FASTMANAGE_ENABLE = True

# DJU_DEV_FASTMANAGE_DAEMON_SOCKET = None


# Django tasks DB worker

# DJU_DEV_DB_WORKER_ENABLE = True


