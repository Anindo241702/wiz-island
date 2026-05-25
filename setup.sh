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
BOLD='\033[1m'
NC='\033[0m' # No Color

# --- Logging Function ---
log_info() {
    echo -e "${GREEN}[WizIsland]${NC} $1"
}
log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}
log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  WIZ ISLAND - Linux Bootstrapper  v1.0.0${NC}"
echo -e "${CYAN}============================================================${NC}"
echo
echo -e "  Detected: $(uname -s) $(uname -r)"
echo -e "  Architecture: $(uname -m)"
echo -e "  Date: $(date)"
echo

# --- Check for sudo privileges ---
if [ "$EUID" -ne 0 ]; then
    log_warn "This script requires sudo privileges."
    log_info "Re-running with sudo..."
    exec sudo bash "$0" "$@"
fi

log_info "Running as root."

# --- Detect package manager ---
if command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt-get"
    PKG_UPDATE="apt-get update -qq"
    PKG_INSTALL="apt-get install -y"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
    PKG_UPDATE="dnf check-update || true"
    PKG_INSTALL="dnf install -y"
elif command -v yum &> /dev/null; then
    PKG_MANAGER="yum"
    PKG_UPDATE="yum check-update || true"
    PKG_INSTALL="yum install -y"
else
    log_error "No supported package manager found (apt-get, dnf, yum)."
    exit 1
fi

log_info "Using package manager: $PKG_MANAGER"

# --- Update package lists ---
log_info "Updating package lists..."
$PKG_UPDATE 2>/dev/null

# --- Install Python3 if missing ---
if ! command -v python3 &> /dev/null; then
    log_info "Installing Python3..."
    $PKG_INSTALL python3 python3-venv
    if [ $? -ne 0 ]; then
        log_error "Failed to install Python3."
        exit 1
    fi
    log_info "Python3 installed."
else
    log_info "Python3 is already installed: $(python3 --version)"
fi

# --- Install pip if missing ---
if ! command -v pip3 &> /dev/null; then
    log_info "Installing pip3..."
    $PKG_INSTALL python3-pip
    if [ $? -ne 0 ]; then
        log_warn "Failed to install pip3 via package manager. Trying get-pip.py..."
        python3 -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '/tmp/get-pip.py')"
        python3 /tmp/get-pip.py
        rm -f /tmp/get-pip.py
    fi
else
    log_info "pip3 is already installed."
fi

# --- Install OpenSSH Server if missing ---
if ! command -v sshd &> /dev/null; then
    log_info "Installing OpenSSH Server..."
    $PKG_INSTALL openssh-server
    if [ $? -ne 0 ]; then
        log_error "Failed to install OpenSSH Server."
        exit 1
    fi
    log_info "OpenSSH Server installed."
else
    log_info "OpenSSH Server is already installed."
fi

# --- Start and enable SSH ---
log_info "Enabling and starting SSH service..."
if command -v systemctl &> /dev/null; then
    systemctl enable ssh 2>/dev/null || systemctl enable sshd 2>/dev/null || true
    systemctl start ssh 2>/dev/null || systemctl start sshd 2>/dev/null || true
elif command -v service &> /dev/null; then
    service ssh start 2>/dev/null || service sshd start 2>/dev/null || true
fi
log_info "SSH service configured."

# --- Configure firewall (ufw) if available ---
if command -v ufw &> /dev/null; then
    log_info "Configuring firewall (ufw)..."
    ufw allow 22/tcp 2>/dev/null || true
    log_info "Firewall rule for SSH port 22 configured."
else
    log_info "ufw not found, skipping firewall configuration."
fi

# --- Install Ngrok if missing ---
if ! command -v ngrok &> /dev/null; then
    log_info "Installing Ngrok..."
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)  NGROK_ARCH="amd64" ;;
        aarch64) NGROK_ARCH="arm64" ;;
        armv7l)  NGROK_ARCH="arm" ;;
        i686)    NGROK_ARCH="386" ;;
        *)
            log_error "Unsupported architecture: $ARCH"
            log_info "Please install Ngrok manually from https://ngrok.com/download"
            exit 1
            ;;
    esac

    # Try the official Ngrok v3 install method first
    if command -v curl &> /dev/null; then
        log_info "Downloading Ngrok for ${NGROK_ARCH} (v3)..."
        curl -s https://ngrok-agent.s3.amazonaws.com/ngrok-v3-stable-linux-${NGROK_ARCH}.tgz -o /tmp/ngrok.tgz
        if [ $? -eq 0 ] && [ -f /tmp/ngrok.tgz ]; then
            tar -xzf /tmp/ngrok.tgz -C /usr/local/bin 2>/dev/null
            if [ $? -eq 0 ]; then
                chmod +x /usr/local/bin/ngrok
                rm -f /tmp/ngrok.tgz
                log_info "Ngrok v3 installed successfully."
            else
                log_warn "Failed to extract Ngrok v3, trying v2..."
            fi
        fi
    fi

    # Fallback to v2 if v3 failed
    if ! command -v ngrok &> /dev/null; then
        NGROK_URL="https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v2-stable-linux-${NGROK_ARCH}.tgz"
        log_info "Downloading Ngrok v2 for ${NGROK_ARCH}..."
        if command -v wget &> /dev/null; then
            wget -qO /tmp/ngrok.tgz "$NGROK_URL"
        elif command -v curl &> /dev/null; then
            curl -sL -o /tmp/ngrok.tgz "$NGROK_URL"
        else
            log_error "Neither wget nor curl is available. Cannot download Ngrok."
            log_info "Please install Ngrok manually from https://ngrok.com/download"
            exit 1
        fi

        if [ $? -ne 0 ]; then
            log_error "Failed to download Ngrok."
            exit 1
        fi
        tar -xzf /tmp/ngrok.tgz -C /usr/local/bin
        chmod +x /usr/local/bin/ngrok
        rm -f /tmp/ngrok.tgz
        log_info "Ngrok v2 installed successfully."
    fi
else
    log_info "Ngrok is already installed: $(ngrok version 2>/dev/null || echo 'version unknown')"
fi

# --- Install Python dependencies ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
log_info "Installing Python dependencies..."
pip3 install -r "${SCRIPT_DIR}/requirements.txt" 2>/dev/null || python3 -m pip install -r "${SCRIPT_DIR}/requirements.txt"
if [ $? -ne 0 ]; then
    log_error "Failed to install Python dependencies."
    log_info "Try: pip3 install psutil"
    exit 1
fi

echo
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  All dependencies installed successfully!${NC}"
echo -e "${CYAN}  Launching Wiz Island...${NC}"
echo -e "${CYAN}============================================================${NC}"
echo

# --- Launch the Python CLI ---
python3 "${SCRIPT_DIR}/src/main.py"
