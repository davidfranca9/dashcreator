#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
python manage.py shell <<'PY'
from django.contrib.auth import get_user_model
from studio.services import get_or_create_workspace_for_user

User = get_user_model()
username = __import__("os").environ["DJANGO_SUPERUSER_USERNAME"]
email = __import__("os").environ["DJANGO_SUPERUSER_EMAIL"]
password = __import__("os").environ["DJANGO_SUPERUSER_PASSWORD"]

user, created = User.objects.get_or_create(
    username=username,
    defaults={"email": email, "is_staff": True, "is_superuser": True},
)
if created:
    user.set_password(password)
    user.save()
elif not user.check_password(password):
    user.set_password(password)
    user.save(update_fields=["password"])

get_or_create_workspace_for_user(user)
PY
fi

exec gunicorn ugc_saas.wsgi:application --bind 0.0.0.0:8000 --workers 3
