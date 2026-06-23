from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/token-login2/", views.TokenLoginView2.as_view(), name="api_token_login2"),
    path("api/ping/", views.Ping.as_view(), name="api_ping"),
    path("api/signout/", views.SignOutView.as_view(), name="api_sign_out"),
    path("api/signin-request/", views.SigninRequestView.as_view(), name="api_signin_request"),
]
