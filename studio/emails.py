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


def send_access_code_email(purchase, access_code) -> None:
    """Avisa o comprador que o pagamento foi aprovado e entrega o código
    de acesso para concluir o cadastro."""
    signup_url = f"{settings.CHECKOUT_BASE_URL.rstrip('/')}{reverse('signup')}"
    context = {
        "purchase": purchase,
        "access_code": access_code,
        "signup_url": signup_url,
    }
    subject = render_to_string("checkout/access_code_subject.txt", context).strip()
    body = render_to_string("checkout/access_code_email.txt", context)
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [purchase.customer_email],
        fail_silently=False,
    )
