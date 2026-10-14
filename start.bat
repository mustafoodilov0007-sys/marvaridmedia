@echo off
chcp 65001 >nul
title Marvarid Media - Kino Bot
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto nopython

:loop
echo.
echo  ==========================================================
echo    Marvarid Media kino bot ishga tushmoqda...
echo    To'xtatish uchun shu oynani yoping.
echo  ==========================================================
echo.
%PY% bot.py
if errorlevel 2 goto fatal
echo.
echo  Bot to'xtadi. 10 soniyadan so'ng qayta ishga tushadi...
timeout /t 10 /nobreak >nul
goto loop

:fatal
echo.
echo  [!] Sozlamalarda xatolik bor. Yuqoridagi xabarni o'qing va .env faylini tekshiring.
echo.
pause
exit /b 2

:nopython
echo.
echo  [X] Python topilmadi!
echo      https://www.python.org/downloads/ saytidan Python 3 ni yuklab o'rnating
echo      va o'rnatish oynasida "Add python.exe to PATH" belgisini qo'ying.
echo.
pause
exit /b 1
