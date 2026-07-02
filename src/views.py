from django.conf import settings
from django.shortcuts import render


def index(request):
    # Render the SPA shell, exposing djultra's frontend config (API base URL and
    # reCAPTCHA site key; the CSP nonce comes from the middleware) to the page. Ships
    # a default index.html; a site overrides it by providing its own template of the
    # same name in an app searched before djultra.
    context = {
        'frontend_api_url': settings.FRONTEND_API_URL,
        'recaptcha_site_key': settings.RECAPTCHA_SITE_KEY,
    }
    return render(request, 'index.html', context)
