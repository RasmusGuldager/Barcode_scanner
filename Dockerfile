FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app
COPY migrations migrations

ENV FLASK_APP=app \
    DATA_DIR=/app/data

EXPOSE 5000

# Apply any new migrations, then start the server.
CMD ["sh", "-c", "flask db upgrade && exec gunicorn --bind 0.0.0.0:5000 --workers 2 'app:create_app()'"]
