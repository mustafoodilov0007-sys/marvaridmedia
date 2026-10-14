#!/usr/bin/env bash
# Marvarid Media kino bot — Linux/macOS uchun ishga tushirish (to'xtab qolsa qayta ishga tushadi)
cd "$(dirname "$0")" || exit 1
trap 'echo; echo "⏹ To'\''xtatildi."; exit 0' INT TERM

while true; do
  python3 bot.py
  code=$?
  if [ "$code" -ge 2 ]; then
    echo "❌ Sozlamalarda xatolik — .env faylini tekshiring."
    exit "$code"
  fi
  echo "Bot to'xtadi (kod $code). 10 soniyadan so'ng qayta ishga tushadi..."
  sleep 10
done
