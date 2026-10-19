# One Big Backend — Module 2 (grants), production image.
# Serves with gunicorn. The Flask dev server was removed from app.py on purpose.
FROM python:3.12-slim

WORKDIR /srv/obb

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py db.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Fly.io injects PORT; SQLite lives on the mounted /data volume.
ENV PORT=5058 \
    OBB_DB=/data/obb.db \
    OBB_COOKIE_SECURE=1

EXPOSE 5058
VOLUME /data

# DB schema is created idempotently at app import; seed demo data only
# explicitly: docker run ... python seed.py
CMD ["sh", "-c", "exec gunicorn --workers 2 --bind 0.0.0.0:${PORT} app:app"]
