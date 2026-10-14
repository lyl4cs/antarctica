FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml .
COPY services ./services
COPY core ./core
RUN pip install --no-cache-dir ".[ai]"
CMD exec uvicorn services.api.main:app --host 0.0.0.0 --port ${PORT:-8080}
