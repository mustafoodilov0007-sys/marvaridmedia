# Marvarid Watch — alohida servis (Railway: Root Directory = watch)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY . .

# Baza (va, sinov rejimida, videolar) /app/data ichida — Railway'da shu joyga Volume ulang
CMD ["python", "server.py"]
