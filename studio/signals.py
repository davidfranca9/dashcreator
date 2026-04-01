from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.sessions.models import Session
from django.dispatch import receiver

from .models import ActiveUserSession


MULTI_SESSION_USERNAMES = {"layfeamorim"}


def allows_multiple_active_sessions(user) -> bool:
    return bool(user and getattr(user, "username", "").casefold() in MULTI_SESSION_USERNAMES)


@receiver(user_logged_in)
def enforce_single_active_session(sender, request, user, **kwargs):
    if not request.session.session_key:
        request.session.save()

    if allows_multiple_active_sessions(user):
        ActiveUserSession.objects.filter(user=user).delete()
        return

    current_session_key = request.session.session_key
    active_session, _ = ActiveUserSession.objects.get_or_create(user=user, defaults={"session_key": current_session_key})

    if active_session.session_key != current_session_key:
        Session.objects.filter(session_key=active_session.session_key).delete()
        active_session.session_key = current_session_key
        active_session.save(update_fields=["session_key", "updated_at"])


@receiver(user_logged_out)
def clear_active_session(sender, request, user, **kwargs):
    if user is None or not request.session.session_key:
        return

    ActiveUserSession.objects.filter(user=user, session_key=request.session.session_key).delete()
