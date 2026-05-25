@echo off
REM ============================================================
REM  WIZ ISLAND - Windows Admin Auto-Installer (setup.bat)
REM  This bootstrapper checks for admin privileges, installs
REM  dependencies via winget, and launches the Python CLI.
REM ============================================================

title Wiz Island - Setup

:: --- Check for Administrative Privileges ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] Requesting Administrative privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ============================================================
echo   WIZ ISLAND - Windows Bootstrapper  v1.1.0
echo ============================================================
echo.
echo   Detected: Windows %OS%
echo   Running as: Administrator
echo   Date: %date% %time%
echo.

:: --- Install Python if missing ---
echo [WizIsland] Checking for Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] Python not found. Installing via winget...
    winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install Python via winget.
        echo [INFO]  Please install Python 3.10+ manually from https://python.org
        pause
        exit /b 1
    )
    echo [WizIsland] Python installed successfully.
    :: Refresh PATH for the current session
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
    :: Also try Python312 path
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [WizIsland] %%i is already installed.
)

:: --- Verify Python is accessible ---
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is still not found in PATH after installation.
    echo [INFO]  Please restart your terminal and try again, or add Python to PATH manually.
    pause
    exit /b 1
)

:: --- Install OpenSSH Server if missing ---
echo [WizIsland] Checking for OpenSSH Server...
sc query sshd >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] OpenSSH Server not found. Installing...
    powershell -Command "Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install OpenSSH Server.
        echo [INFO]  You can install it manually via Settings ^> Apps ^> Optional Features
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

:: --- Ensure password authentication is enabled for SSH ---
echo [WizIsland] Checking SSH password authentication...
if exist "C:\ProgramData\ssh\sshd_config" (
    findstr /i "^PasswordAuthentication no" "C:\ProgramData\ssh\sshd_config" >nul 2>&1
    if %errorlevel% equ 0 (
        echo [WizIsland] Enabling SSH password authentication...
        powershell -Command "(Get-Content 'C:\ProgramData\ssh\sshd_config') -replace '^PasswordAuthentication no','PasswordAuthentication yes' | Set-Content 'C:\ProgramData\ssh\sshd_config'"
        net stop sshd >nul 2>&1
        timeout /t 2 /nobreak >nul 2>&1
        net start sshd >nul 2>&1
    ) else (
        echo [WizIsland] SSH password authentication is already enabled.
    )
)

:: --- Configure Windows Firewall for SSH ---
echo [WizIsland] Checking firewall rules...
netsh advfirewall firewall show rule name="WizIsland SSH" >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] Adding firewall rule for SSH port 22...
    netsh advfirewall firewall add rule name="WizIsland SSH" dir=in action=allow protocol=TCP localport=22 profile=any enable=yes >nul 2>&1
    if %errorlevel% neq 0 (
        echo [WARNING] Could not add firewall rule. SSH may not be reachable externally.
    ) else (
        echo [WizIsland] Firewall rule added successfully.
    )
) else (
    echo [WizIsland] Firewall rule already configured.
)

:: --- Ensure OpenSSH Client is available (needed for Pinggy tunnel) ---
echo [WizIsland] Checking for SSH client...
where ssh >nul 2>&1
if %errorlevel% neq 0 (
    echo [WizIsland] SSH client not found. Installing...
    powershell -Command "Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0"
    if %errorlevel% neq 0 (
        echo [WARNING] Could not install SSH client automatically.
        echo [INFO]    Install via: Settings ^> Apps ^> Optional Features ^> OpenSSH Client
    ) else (
        echo [WizIsland] SSH client installed successfully.
    )
) else (
    echo [WizIsland] SSH client is available.
)

:: --- Install Python dependencies ---
echo [WizIsland] Installing Python dependencies...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    echo [INFO]  Make sure pip is working: python -m pip --version
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   All dependencies installed successfully!
echo   Launching Wiz Island...
echo ============================================================
echo.

:: --- Launch the Python CLI ---
python "%~dp0src\main.py"

pause
