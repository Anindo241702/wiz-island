"""
WIZ ISLAND - Client-Side SSH Configuration Injection (client.py)

Handles parsing of the Ngrok connection string, updating the local
SSH config file, and providing connection instructions for VS Code
Remote-SSH.
"""

import logging
import os
import platform
import re
import sys

logger = logging.getLogger("wiz_island.client")


def get_ssh_config_path():
    """Return the SSH config file path for the current platform."""
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("USERPROFILE", ""), ".ssh", "config")
    else:
        return os.path.expanduser("~/.ssh/config")


def parse_ngrok_url(url_string):
    """Parse the Ngrok TCP URL into (host, port).

    Accepts formats like:
        tcp://0.tcp.ngrok.io:12345
        0.tcp.ngrok.io:12345
    """
    url_string = url_string.strip()

    # Strip tcp:// prefix if present
    if url_string.startswith("tcp://"):
        url_string = url_string[6:]

    # Match host:port pattern
    match = re.match(r"^([\w\.\-]+):(\d+)$", url_string)
    if not match:
        return None, None

    host = match.group(1)
    port = int(match.group(2))
    return host, port


def ensure_ssh_directory():
    """Ensure the .ssh directory exists with proper permissions."""
    ssh_dir = os.path.dirname(get_ssh_config_path())
    try:
        os.makedirs(ssh_dir, exist_ok=True)
        if platform.system() != "Windows":
            os.chmod(ssh_dir, 0o700)
        logger.info("SSH directory ensured: %s", ssh_dir)
    except OSError as exc:
        logger.error("Failed to create SSH directory %s: %s", ssh_dir, exc)
        raise


def update_ssh_config(host, port, alias="WizIsland"):
    """Append or update the SSH config entry for WizIsland."""
    config_path = get_ssh_config_path()
    ensure_ssh_directory()

    entry = (
        f"\n# --- Wiz Island Connection ---\n"
        f"Host {alias}\n"
        f"    HostName {host}\n"
        f"    Port {port}\n"
        f"    User wizguest\n"
        f"    StrictHostKeyChecking no\n"
        f"    UserKnownHostsFile /dev/null\n"
    )

    try:
        existing = ""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                existing = f.read()

        # Remove any previous WizIsland entry
        marker_start = "# --- Wiz Island Connection ---"
        if marker_start in existing:
            # Find the block and remove it
            parts = existing.split(marker_start)
            before = parts[0]
            after_block = parts[1]
            # Find the next "Host " line or end of file
            next_host = re.search(r"\n(?=Host\s)", after_block)
            if next_host:
                remaining = after_block[next_host.start():]
            else:
                remaining = ""
            existing = before.rstrip() + remaining

        # Append new entry
        with open(config_path, "w") as f:
            content = existing.rstrip() + "\n" + entry
            f.write(content)

        # Set file permissions on Linux/macOS
        if platform.system() != "Windows":
            os.chmod(config_path, 0o600)

        logger.info("SSH config updated: %s -> %s:%d", alias, host, port)
        return config_path

    except IOError as exc:
        logger.error("Failed to write SSH config: %s", exc)
        raise
    except Exception as exc:
        logger.error("Unexpected error updating SSH config: %s", exc)
        raise


def print_connection_instructions(host, port, config_path, alias="WizIsland"):
    """Print detailed connection instructions for the user."""
    lines = [
        "",
        "  ============================================================",
        "   WIZ ISLAND - CONNECTION CONFIGURED",
        "  ============================================================",
        "",
        f"   SSH Config Updated : {config_path}",
        f"   Connection Alias   : {alias}",
        f"   Target Host        : {host}",
        f"   Target Port        : {port}",
        f"   Username           : wizguest",
        "",
        "  ------------------------------------------------------------",
        "   HOW TO CONNECT",
        "  ------------------------------------------------------------",
        "",
        "   OPTION 1: Terminal SSH",
        f"     $ ssh {alias}",
        "     (or)",
        f"     $ ssh wizguest@{host} -p {port}",
        "",
        "   OPTION 2: VS Code Remote-SSH",
        "     1. Install the 'Remote - SSH' extension in VS Code.",
        "     2. Press Ctrl+Shift+P (or Cmd+Shift+P on macOS).",
        "     3. Type: 'Remote-SSH: Connect to Host...'",
        f"     4. Select '{alias}' from the dropdown list.",
        "     5. Enter the password when prompted.",
        "",
        "   OPTION 3: VS Code Command Palette (Direct)",
        "     1. Press Ctrl+Shift+P",
        "     2. Type: 'Remote-SSH: Connect to Host...'",
        f"     3. Enter: ssh wizguest@{host} -p {port}",
        "",
        "  ============================================================",
        "   NOTE: StrictHostKeyChecking is disabled for this host.",
        "   The connection uses the guest password provided by the Host.",
        "  ============================================================",
        "",
    ]
    print("\n".join(lines))


def run_user_mode():
    """Main entry point for User Mode (client)."""
    print("\n  ============================================================")
    print("   WIZ ISLAND - USER MODE (CLIENT)")
    print("  ============================================================")

    # Prompt for the Ngrok URL
    url_string = input("\n  Paste the Ngrok connection string: ").strip()

    if not url_string:
        print("  [ERROR] Connection string cannot be empty.")
        return

    host, port = parse_ngrok_url(url_string)
    if not host or not port:
        print(f"  [ERROR] Invalid Ngrok URL format: '{url_string}'")
        print("  Expected format: tcp://0.tcp.ngrok.io:12345 or 0.tcp.ngrok.io:12345")
        return

    print(f"\n  Parsed connection: {host}:{port}")
    print("  Updating SSH config...")

    try:
        config_path = update_ssh_config(host, port)
    except Exception as exc:
        print(f"  [ERROR] Failed to update SSH config: {exc}")
        return

    print_connection_instructions(host, port, config_path)

    input("  Press Enter to return to the main menu...")
