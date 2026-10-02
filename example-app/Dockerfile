# DEMONSTRATION ONLY. Copy to the repository root to test the adapter.
# Pin an approved base-image digest before using this pattern for a real application.
FROM python:3.12-slim
WORKDIR /app
COPY example-app/server.py /app/server.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python", "/app/server.py"]
