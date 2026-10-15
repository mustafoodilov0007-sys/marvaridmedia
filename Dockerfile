# Marvarid Media kino bot — Railway (va boshqa Docker hostinglar) uchun
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app
COPY . .

# Baza va loglar /app/data ichida saqlanadi — Railway'da shu joyga Volume ulang
CMD ["python", "bot.py"]
