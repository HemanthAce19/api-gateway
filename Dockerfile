FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
COPY gateway ./gateway
COPY demo_service ./demo_service
COPY routes.yaml ./
RUN pip install --no-cache-dir . && useradd --create-home app
USER app

EXPOSE 8000
CMD ["uvicorn", "gateway.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
