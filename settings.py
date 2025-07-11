
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
        'level': 'INFO',
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

    'djultra.middleware.AdminActionLoggerMiddleware', # Run after SessionMiddleware

    # Logs slow queries and number of queries (so far only usefull in dev env).
    'djultra.middleware.QueryLoggingMiddleware',

    # Test slow API responses
    #'Relonee.core.middleware.ArtificialDelayMiddleware', 
]

###################
## STATIC ASSETS ##
###################

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

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
            "https://sign.relonee.com",
            UNSAFE_INLINE,
        ],
        "frame-src": [
            SELF,
            FRONTEND_URL,
            CSP_EXTRA_HOST,
            "https://www.recaptcha.net",
            "https://sign.relonee.com",
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
            "http://localhost:3000",
            "https://localhost:3000",
            #"https://sign.relonee.com",
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

