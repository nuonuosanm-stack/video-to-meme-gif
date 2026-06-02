FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gif_toolkit ./gif_toolkit
COPY static ./static
COPY README.md LICENSE CHANGELOG.md ./

EXPOSE 8503

CMD ["uvicorn", "gif_toolkit.app:app", "--host", "0.0.0.0", "--port", "8503"]

