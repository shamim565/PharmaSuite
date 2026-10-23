from django.urls import path

from apps.accounts.views import (
    LoginView,
    LogoutView,
    MeMfaDisableView,
    MeMfaEnableView,
    MeMfaSetupView,
    MeView,
    MfaLoginView,
    RefreshView,
    SessionListView,
    SessionRevokeAllView,
    SessionRevokeView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("login/mfa/", MfaLoginView.as_view(), name="auth-login-mfa"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("sessions/", SessionListView.as_view(), name="auth-sessions"),
    path("sessions/<uuid:sid>/", SessionRevokeView.as_view(), name="auth-session-revoke"),
    path("sessions/revoke-all/", SessionRevokeAllView.as_view(), name="auth-sessions-revoke-all"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/2fa/setup/", MeMfaSetupView.as_view(), name="auth-me-2fa-setup"),
    path("me/2fa/enable/", MeMfaEnableView.as_view(), name="auth-me-2fa-enable"),
    path("me/2fa/disable/", MeMfaDisableView.as_view(), name="auth-me-2fa-disable"),
]
