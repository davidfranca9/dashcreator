from __future__ import annotations

import logging
import unicodedata
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


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


def _arquivo_do_nome(nome: str) -> str:
    """Nome do arquivo do ingresso a partir do nome da pessoa, sem acento nem espaço."""
    limpo = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode()
    partes = [p for p in limpo.lower().split() if p.isalnum()]
    return "-".join(partes[:3]) or "participante"


def send_creator_day_ticket_email(purchase, product) -> None:
    """Confirmação do Creator Day com o texto da Layfe e o ingresso personalizado
    (PNG com o nome de quem comprou), anexado e também dentro do e-mail."""
    from .ingresso import codigo_do_ingresso, gerar_ingresso

    codigo = codigo_do_ingresso(purchase)
    contexto = {"purchase": purchase, "product": product, "codigo": codigo, "cid_ingresso": "ingresso"}
    assunto = render_to_string("checkout/ingresso_subject.txt", contexto).strip()
    texto = render_to_string("checkout/ingresso_email.txt", contexto)
    email = EmailMultiAlternatives(assunto, texto, settings.DEFAULT_FROM_EMAIL, [purchase.customer_email])

    try:
        png = gerar_ingresso(purchase.customer_name, codigo)
    except Exception:  # o e-mail da compra não pode falhar por causa da imagem
        logger.exception("Falha ao montar o ingresso (purchase=%s)", purchase.pk)
        email.send(fail_silently=False)
        return

    arquivo = f"ingresso-creator-day-{_arquivo_do_nome(purchase.customer_name)}.png"
    corpo_html = render_to_string("checkout/ingresso_email.html", contexto)
    email.attach_alternative(corpo_html, "text/html")
    imagem = MIMEImage(png, "png")
    imagem.add_header("Content-ID", "<ingresso>")
    imagem.add_header("Content-Disposition", "inline", filename=arquivo)
    email.attach(imagem)
    email.attach(arquivo, png, "image/png")
    email.send(fail_silently=False)


def send_ticket_email(purchase, product) -> None:
    """Confirma a compra de um ingresso de evento. Não tem código de acesso:
    o email é a confirmação da compra, com data e local do produto."""
    context = {
        "purchase": purchase,
        "product": product,
    }
    if getattr(product, "personalized_ticket", False) and settings.CREATOR_DAY_EMAIL_INGRESSO:
        send_creator_day_ticket_email(purchase, product)
        return
    prefixo = getattr(product, "email_template", "ticket") or "ticket"
    subject = render_to_string(f"checkout/{prefixo}_subject.txt", context).strip()
    body = render_to_string(f"checkout/{prefixo}_email.txt", context)
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [purchase.customer_email],
        fail_silently=False,
    )
