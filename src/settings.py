# Injected into the including project's settings via ultraimport
# (inject=globals()), so it runs with that module's namespace: it expects
# DEBUG, LOG_LEVEL, BASE_DIR, FRONTEND_URL and `config` to be defined
# before the injection, and it wraps the project's MIDDLEWARE list with
# djultra middleware. Project-specific overrides of anything defined here
# belong below the injection loop in the project's settings.

import re

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

##################
## CORS HEADERS ##
##################

# Alternatively, specify allowed origins
CORS_ALLOWED_ORIGINS = []

CORS_ALLOWED_ORIGINS.append(FRONTEND_URL)

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
CSP_EXTRA_HOST = ""

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



##############
## DEV MODE ##
##############

# Fastmanage daemon

# DJU_DEV_FASTMANAGE_ENABLE = True

# DJU_DEV_FASTMANAGE_DAEMON_SOCKET = None


# Django tasks DB worker

# DJU_DEV_DB_WORKER_ENABLE = True


