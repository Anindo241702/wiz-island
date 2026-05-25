@echo off
REM ============================================================
REM  WIZ ISLAND - Windows Admin Auto-Installer (setup.bat)
REM  This bootstrapper checks for admin privileges, installs
REM  dependencies via winget, and launches the Python CLI.
REM ============================================================

:: --- Check for Administrative Privileges ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] Requesting Administrative privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   WIZ ISLAND - Windows Bootstrapper
echo ============================================================
echo.

:: --- Install Python if missing ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] Python not found. Installing via winget...
    winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Python. Please install manually.
        pause
        exit /b 1
    )
    echo [WizIsland] Python installed successfully.
    :: Refresh PATH for the current session
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
) else (
    echo [WizIsland] Python is already installed.
)

:: --- Install OpenSSH Server if missing ---
sc query sshd >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] OpenSSH Server not found. Installing...
    powershell -Command "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install OpenSSH Server.
        pause
        exit /b 1
    )
    echo [WizIsland] OpenSSH Server installed successfully.
) else (
    echo [WizIsland] OpenSSH Server is already installed.
)

:: --- Start and enable OpenSSH Server ---
echo [WizIsland] Configuring OpenSSH Server service...
sc config sshd start= auto >nul 2>&1
net start sshd >nul 2>&1

:: --- Install Ngrok if missing ---
where ngrok >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] Ngrok not found. Installing via winget...
    winget install -e --id Ngrok.Ngrok --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Ngrok. Please install manually.
        pause
        exit /b 1
    )
    echo [WizIsland] Ngrok installed successfully.
) else (
    echo [WizIsland] Ngrok is already installed.
)

:: --- Install Python dependencies ---
echo [WizIsland] Installing Python dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   All dependencies installed. Launching Wiz Island...
echo ============================================================
echo.

:: --- Launch the Python CLI ---
python "%~dp0src\main.py"

pause
