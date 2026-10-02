# Official Python linux/amd64 manifest, verified against Docker Hub on 2026-10-02.
# Re-pin through review when updating the runtime; never substitute an unverified digest.
FROM python:3.12-slim-bookworm@sha256:9901e0a8d75037d8242ed43155cbcb2d1f61be1356383d8054afb59fd50e39c4
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080
COPY --chown=10001:10001 gus_app/ /app/gus_app/
USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["python", "-m", "gus_app.server"]
