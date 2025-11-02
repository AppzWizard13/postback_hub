#!/bin/sh
if [ "$DATABASE" = "postgres" ]; then
    echo "Waiting for PostgreSQL at $POSTGRES_HOST:$POSTGRES_PORT..."

    # Debug environment variables
    echo "Using POSTGRES_HOST=$POSTGRES_HOST"
    echo "Using POSTGRES_PORT=$POSTGRES_PORT"

    # Wait until PostgreSQL server is available
    while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
      echo "PostgreSQL is unavailable - sleeping"
      sleep 0.5
    done

    echo "PostgreSQL started"
fi

echo "Applying database migrations"
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "Creating admin user if not exists"
python manage.py create_admin

echo "Collecting static files"
python manage.py collectstatic --noinput

exec "$@"
