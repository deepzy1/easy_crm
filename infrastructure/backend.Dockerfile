FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && useradd --create-home easycrm
COPY --chown=easycrm:easycrm backend/app/ ./app/
COPY --chown=easycrm:easycrm backend/alembic/ ./alembic/
COPY --chown=easycrm:easycrm backend/alembic.ini ./
USER easycrm
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
