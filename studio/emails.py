from __future__ import annotations

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse


def send_signup_confirmation_email(user, request) -> None:
    context = {
        "user": user,
        "login_url": request.build_absolute_uri(reverse("login")),
    }
    subject = render_to_string("registration/signup_confirmation_subject.txt", context).strip()
    body = render_to_string("registration/signup_confirmation_email.txt", context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
