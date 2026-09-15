import json

from django.conf import settings
from django.shortcuts import render


def index(request):
    # Render the SPA shell, exposing djultra's frontend config (API base URL and
    # reCAPTCHA site key; the CSP nonce comes from the middleware) to the page. Ships
    # a default index.html; a site overrides it by providing its own template of the
    # same name in an app searched before djultra.
    context = {
        'project_name': settings.PROJECT_NAME,
        'frontend_api_url': settings.FRONTEND_API_URL,
        'recaptcha_site_key': settings.RECAPTCHA_SITE_KEY,
        # A site's own window.config keys, from FRONTEND_CONFIG; the values become JS
        # literals here, since the template has no filter for that
        'frontend_config': {key: json.dumps(value) for key, value in settings.FRONTEND_CONFIG.items()},
    }
    return render(request, 'index.html', context)
