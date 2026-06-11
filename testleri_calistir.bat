@echo off
setlocal
chcp 65001 >nul
title StatAI Testler
cd /d "%~dp0"

echo.
echo  ========================================
echo   StatAI - Otomatik Testler
echo  ========================================
echo.
echo  Tum testler calistiriliyor (sonuna kadar)...
echo  Her satirda: [siradaki/toplam] durum ^& gecen sure
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi. PATH'e ekleyin veya Python yukleyin.
    pause
    exit /b 1
)

python -m pytest %*
set RC=%ERRORLEVEL%

echo.
if %RC% neq 0 (
    echo  [HATA] Testler basarisiz. Cikis kodu: %RC%
) else (
    echo  [OK] Tum testler gecti.
)
echo.
echo  Tek dosya:  python -m pytest tests/test_formatting.py -q
echo  Verbose:    python -m pytest -v
echo.
pause
exit /b %RC%
