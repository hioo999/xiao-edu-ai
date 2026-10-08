FROM python:3.11-slim
WORKDIR /app
COPY apps/api/pyproject.toml ./apps/api/pyproject.toml
RUN pip install --no-cache-dir \
    "argon2-cffi>=23,<26" \
    "cryptography>=43,<46" \
    "fastapi>=0.115,<1" \
    "httpx>=0.27,<1" \
    "python-dotenv>=1,<2" \
    "python-multipart>=0.0.9,<1" \
    "uvicorn[standard]>=0.34,<1"
COPY apps/api ./apps/api
COPY packages ./packages
COPY scripts ./scripts
RUN mkdir -p /data /backups && chown -R 10001:10001 /app /data /backups
ENV PYTHONPATH=/app
USER 10001
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
