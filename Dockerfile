FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 CHRONOS_HOST=0.0.0.0
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt gunicorn
COPY . .
RUN mkdir -p /var/data && useradd --create-home --uid 10001 chronos && chown -R chronos:chronos /app /var/data
USER chronos
EXPOSE 8000
CMD ["gunicorn","--bind","0.0.0.0:8000","--workers","1","--threads","4","--timeout","120","app:app"]
