FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONPATH=/srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY mcp_server mcp_server
COPY migrations migrations
COPY alembic.ini wsgi.py ./

CMD ["sh", "-c", "alembic upgrade head && gunicorn -b 0.0.0.0:${PORT:-13102} --access-logfile - --error-logfile - --log-level ${LOG_LEVEL:-info} wsgi:app"]
