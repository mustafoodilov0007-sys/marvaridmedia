# Marvarid Media kino bot — Railway (va boshqa Docker hostinglar) uchun
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app
COPY requirements.txt .
# Pillow — ixtiyoriy (poster kichik nusxalari); o'rnatilmasa bot baribir ishlaydi
RUN pip install --no-cache-dir -r requirements.txt || true
COPY . .

# Baza va loglar /app/data ichida saqlanadi — Railway'da shu joyga Volume ulang
CMD ["python", "bot.py"]
