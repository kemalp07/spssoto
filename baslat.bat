@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
title StatAI Baslat
cd /d "%~dp0"

set FRONT_PORT=3000

echo.
echo  ========================================
echo   StatAI - Akademik Analiz Araci
echo  ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi.
    pause
    exit /b 1
)

echo [1/5] Bagimliliklar kontrol ediliyor...
python -m pip install -r "%~dp0requirements.txt" -q
if errorlevel 1 (
    echo [HATA] Paketler yuklenemedi.
    pause
    exit /b 1
)

echo [2/5] Eski sunucular kapatiliyor...
powershell -NoProfile -Command ^
  "foreach ($p in 8765,8766,8777,%FRONT_PORT%) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
timeout /t 2 /nobreak >nul

set STAT_PORT=8765
call :port_busy !STAT_PORT!
if not errorlevel 1 (
    echo        Port 8765 dolu, 8766 deneniyor...
    set STAT_PORT=8766
    call :port_busy !STAT_PORT!
    if not errorlevel 1 (
        echo        Port 8766 dolu, 8777 deneniyor...
        set STAT_PORT=8777
    )
)

echo window.STATAI_API = "http://localhost:%STAT_PORT%";> "%~dp0config.js"

echo [3/5] Backend baslatiliyor (http://localhost:%STAT_PORT%)...
start "StatAI Backend" cmd /k "cd /d ""%~dp0backend"" && python -m uvicorn main:app --host 127.0.0.1 --port %STAT_PORT%"

echo [4/5] Frontend baslatiliyor (http://localhost:%FRONT_PORT%)...
start "StatAI Frontend" cmd /k "cd /d ""%~dp0"" && python -m http.server %FRONT_PORT%"

echo [5/5] Backend hazir olana kadar bekleniyor (max 40 sn)...
set /a TRIES=0
:WAIT_BACKEND
set /a TRIES+=1
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:%STAT_PORT%/' -UseBasicParsing -TimeoutSec 3 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    if !TRIES! lss 20 (
        echo        Bekleniyor... !TRIES!/20
        timeout /t 2 /nobreak >nul
        goto WAIT_BACKEND
    )
    echo.
    echo [UYARI] Backend yanit vermedi.
    echo         "StatAI Backend" penceresindeki hatayi okuyun.
    goto DONE
)
echo        Backend hazir!

:DONE
echo.
echo Tarayici aciliyor: http://localhost:%FRONT_PORT%/index.html
start "" "http://localhost:%FRONT_PORT%/index.html"

echo.
echo  ========================================
echo   StatAI calisiyor
echo  ========================================
echo   Frontend: http://localhost:%FRONT_PORT%/index.html
echo   Backend:  http://localhost:%STAT_PORT%
echo.
echo   Kapatmak icin su pencereleri kapat:
echo   - StatAI Backend
echo   - StatAI Frontend
echo  ========================================
echo.
pause
exit /b 0

:port_busy
netstat -ano | findstr ":%1 " | findstr "LISTENING" >nul
exit /b %errorlevel%
