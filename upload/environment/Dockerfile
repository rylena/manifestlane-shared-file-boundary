FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY manifestlane /app/manifestlane
COPY SERVICE_NOTES.md /app/SERVICE_NOTES.md

ENV FLASK_ENV=production
ENV MANIFESTLANE_DB=/app/instance/manifestlane.sqlite
ENV MANIFESTLANE_STORAGE=/app/instance/files

EXPOSE 8080

CMD ["python", "-m", "manifestlane.app"]
