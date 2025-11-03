FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements_front.txt .
RUN pip install -r requirements_front.txt

COPY . .
RUN python -m compileall . && python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn","-c","gunicorn.conf.py","ryoma_site.wsgi:application"]
