# Use official Python image
FROM python:3.10-slim


ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set workdir
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y netcat-openbsd gcc python3-dev libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy app code
COPY . .

# Entrypoint script to wait for DB
COPY ./docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

# Run server
CMD ["gunicorn", "task_management_system.wsgi:application", "--bind", "0.0.0.0:8000"]
