FROM python:3.12.14-slim-bookworm

# Manager talks to the Docker Engine API over the mounted socket.
# DECISION: this service stays on the Compose network only and requires a
# shared token. It is the only process that touches the Docker socket.
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
