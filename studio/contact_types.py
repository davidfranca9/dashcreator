from __future__ import annotations

import re
import unicodedata


DEFAULT_CONTACT_TYPE_CHOICES = [
    ("", "Selecione"),
    ("Instagram DM", "Instagram DM"),
    ("WhatsApp", "WhatsApp"),
    ("Email", "Email"),
    ("Ligação", "Ligação"),
    ("Reunião", "Reunião"),
    ("Social media", "Social media"),
    ("Marketing", "Marketing"),
    ("Follow-up", "Follow-up"),
    ("Outro", "Outro"),
]

(
    _CONTACT_TYPE_EMPTY,
    CONTACT_TYPE_INSTAGRAM_DM,
    CONTACT_TYPE_WHATSAPP,
    CONTACT_TYPE_EMAIL,
    CONTACT_TYPE_CALL,
    CONTACT_TYPE_MEETING,
    CONTACT_TYPE_SOCIAL_MEDIA,
    CONTACT_TYPE_MARKETING,
    CONTACT_TYPE_FOLLOW_UP,
    CONTACT_TYPE_OTHER,
) = [value for value, _ in DEFAULT_CONTACT_TYPE_CHOICES]

EMAIL_CONTACT_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _contact_type_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_value.casefold())


CONTACT_TYPE_VALUE_MAP = {
    _contact_type_key(value): value
    for value in (
        CONTACT_TYPE_INSTAGRAM_DM,
        CONTACT_TYPE_WHATSAPP,
        CONTACT_TYPE_EMAIL,
        CONTACT_TYPE_CALL,
        CONTACT_TYPE_MEETING,
        CONTACT_TYPE_SOCIAL_MEDIA,
        CONTACT_TYPE_MARKETING,
        CONTACT_TYPE_FOLLOW_UP,
        CONTACT_TYPE_OTHER,
    )
}
CONTACT_TYPE_ALIAS_MAP = {
    "instagram": CONTACT_TYPE_INSTAGRAM_DM,
    "instagramdm": CONTACT_TYPE_INSTAGRAM_DM,
    "instadm": CONTACT_TYPE_INSTAGRAM_DM,
    "dm": CONTACT_TYPE_INSTAGRAM_DM,
    "whatsapp": CONTACT_TYPE_WHATSAPP,
    "zap": CONTACT_TYPE_WHATSAPP,
    "wpp": CONTACT_TYPE_WHATSAPP,
    "email": CONTACT_TYPE_EMAIL,
    "mail": CONTACT_TYPE_EMAIL,
    "ligacao": CONTACT_TYPE_CALL,
    "call": CONTACT_TYPE_CALL,
    "telefone": CONTACT_TYPE_CALL,
    "phone": CONTACT_TYPE_CALL,
    "reuniao": CONTACT_TYPE_MEETING,
    "meeting": CONTACT_TYPE_MEETING,
    "socialmedia": CONTACT_TYPE_SOCIAL_MEDIA,
    "marketing": CONTACT_TYPE_MARKETING,
    "followup": CONTACT_TYPE_FOLLOW_UP,
    "outro": CONTACT_TYPE_OTHER,
    "other": CONTACT_TYPE_OTHER,
}


def normalize_contact_type(raw_value: str) -> str:
    normalized_key = _contact_type_key(raw_value)
    if not normalized_key:
        return ""
    return CONTACT_TYPE_ALIAS_MAP.get(normalized_key) or CONTACT_TYPE_VALUE_MAP.get(normalized_key, "")


def infer_contact_type(
    raw_contact_type: str = "",
    *,
    email: str = "",
    instagram: str = "",
    whatsapp: str = "",
) -> str:
    normalized = normalize_contact_type(raw_contact_type)
    if normalized:
        return normalized

    raw_value = (raw_contact_type or "").strip()
    raw_key = _contact_type_key(raw_value)
    digit_count = len(re.sub(r"\D", "", raw_value))

    if raw_value and EMAIL_CONTACT_RE.match(raw_value):
        return CONTACT_TYPE_EMAIL
    if raw_value and (raw_value.startswith("@") or "insta" in raw_key):
        return CONTACT_TYPE_INSTAGRAM_DM
    if raw_value and ("whats" in raw_key or digit_count >= 8):
        return CONTACT_TYPE_WHATSAPP

    if email:
        return CONTACT_TYPE_EMAIL
    if instagram:
        return CONTACT_TYPE_INSTAGRAM_DM
    if whatsapp:
        return CONTACT_TYPE_WHATSAPP
    if raw_value:
        return CONTACT_TYPE_OTHER
    return ""
