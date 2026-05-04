release: python manage.py migrate && python manage.py collectstatic --noinput && python manage.py create_default_admin
web: gunicorn chatproject.wsgi:application --bind 0.0.0.0:$PORT
