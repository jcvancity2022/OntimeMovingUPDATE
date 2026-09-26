FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_ENV=production
EXPOSE 8000

# Run migrations, then start the app under gunicorn. Postgres in production;
# db.create_all() in app startup is a no-op once migrations have run.
CMD ["sh", "-c", "python -m alembic upgrade head && gunicorn -w 4 -b 0.0.0.0:8000 --access-logfile - app:app"]
