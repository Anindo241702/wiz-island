#!/usr/bin/env bash
# ============================================================
#  WIZ ISLAND - Linux (Ubuntu/Debian) Auto-Installer (setup.sh)
#  This bootstrapper checks for sudo privileges, installs
#  dependencies via apt-get, and launches the Python CLI.
# ============================================================

set -e

# --- Color Codes ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  WIZ ISLAND - Linux Bootstrapper${NC}"
echo -e "${CYAN}============================================================${NC}"
echo

# --- Check for sudo privileges ---
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[WizIsland] This script requires sudo privileges.${NC}"
    echo -e "${YELLOW}[WizIsland] Re-running with sudo...${NC}"
    exec sudo bash "$0" "$@"
fi

# --- Update package lists ---
echo -e "${GREEN}[WizIsland] Updating package lists...${NC}"
apt-get update -qq

# --- Install Python3 if missing ---
if ! command -v python3 &> /dev/null; then
    echo -e "${GREEN}[WizIsland] Installing Python3...${NC}"
    apt-get install -y python3 python3-venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to install Python3.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}[WizIsland] Python3 is already installed.${NC}"
fi

# --- Install pip if missing ---
if ! command -v pip3 &> /dev/null; then
    echo -e "${GREEN}[WizIsland] Installing pip3...${NC}"
    apt-get install -y python3-pip
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to install pip3.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}[WizIsland] pip3 is already installed.${NC}"
fi

# --- Install OpenSSH Server if missing ---
if ! dpkg -l | grep -q openssh-server; then
    echo -e "${GREEN}[WizIsland] Installing OpenSSH Server...${NC}"
    apt-get install -y openssh-server
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to install OpenSSH Server.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}[WizIsland] OpenSSH Server is already installed.${NC}"
fi

# --- Start and enable SSH ---
echo -e "${GREEN}[WizIsland] Enabling and starting SSH service...${NC}"
systemctl enable ssh 2>/dev/null || true
systemctl start ssh 2>/dev/null || true

# --- Install Ngrok if missing ---
if ! command -v ngrok &> /dev/null; then
    echo -e "${GREEN}[WizIsland] Installing Ngrok...${NC}"
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  NGROK_ARCH="amd64" ;;
        aarch64) NGROK_ARCH="arm64" ;;
        armv7l)  NGROK_ARCH="arm" ;;
        *)
            echo -e "${RED}[ERROR] Unsupported architecture: $ARCH${NC}"
            exit 1
            ;;
    esac

    NGROK_URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v2-stable-linux-${NGROK_ARCH}.tgz"
    echo -e "${GREEN}[WizIsland] Downloading Ngrok for ${NGROK_ARCH}...${NC}"
    wget -qO /tmp/ngrok.tgz "$NGROK_URL"
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR] Failed to download Ngrok.${NC}"
        exit 1
    fi
    tar -xzf /tmp/ngrok.tgz -C /usr/local/bin
    chmod +x /usr/local/bin/ngrok
    rm -f /tmp/ngrok.tgz
    echo -e "${GREEN}[WizIsland] Ngrok installed successfully.${NC}"
else
    echo -e "${GREEN}[WizIsland] Ngrok is already installed.${NC}"
fi

# --- Install Python dependencies ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo -e "${GREEN}[WizIsland] Installing Python dependencies...${NC}"
pip3 install -r "${SCRIPT_DIR}/requirements.txt"
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to install Python dependencies.${NC}"
    exit 1
fi

echo
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  All dependencies installed. Launching Wiz Island...${NC}"
echo -e "${CYAN}============================================================${NC}"
echo

# --- Launch the Python CLI ---
python3 "${SCRIPT_DIR}/src/main.py"
