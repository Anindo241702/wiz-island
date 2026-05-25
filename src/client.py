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
import socket

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
        ssh wizguest@0.tcp.ngrok.io -p 12345
    """
    url_string = url_string.strip()

    # Handle "ssh user@host -p port" format
    ssh_match = re.match(r"ssh\s+\S+@([\w\.\-]+)\s+-p\s+(\d+)", url_string)
    if ssh_match:
        return ssh_match.group(1), int(ssh_match.group(2))

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


def test_connection(host, port, timeout=5):
    """Test TCP connectivity to the remote host:port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except socket.gaierror:
        logger.warning("DNS resolution failed for %s", host)
        return False
    except Exception as exc:
        logger.debug("Connection test error: %s", exc)
        return False


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


def update_ssh_config(host, port, username="wizguest", alias="WizIsland"):
    """Append or update the SSH config entry for WizIsland."""
    config_path = get_ssh_config_path()
    ensure_ssh_directory()

    # Platform-aware UserKnownHostsFile path
    if platform.system() == "Windows":
        known_hosts_null = "NUL"
    else:
        known_hosts_null = "/dev/null"

    entry = (
        f"\n# --- Wiz Island Connection ---\n"
        f"Host {alias}\n"
        f"    HostName {host}\n"
        f"    Port {port}\n"
        f"    User {username}\n"
        f"    StrictHostKeyChecking no\n"
        f"    UserKnownHostsFile {known_hosts_null}\n"
    )

    try:
        existing = ""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                existing = f.read()

        # Remove any previous WizIsland entry
        marker_start = "# --- Wiz Island Connection ---"
        if marker_start in existing:
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


def remove_ssh_config(alias="WizIsland"):
    """Remove the WizIsland entry from the SSH config."""
    config_path = get_ssh_config_path()
    if not os.path.exists(config_path):
        print("  No SSH config file found.")
        return

    try:
        with open(config_path, "r") as f:
            existing = f.read()

        marker_start = "# --- Wiz Island Connection ---"
        if marker_start not in existing:
            print(f"  No '{alias}' entry found in SSH config.")
            return

        parts = existing.split(marker_start)
        before = parts[0]
        after_block = parts[1]
        next_host = re.search(r"\n(?=Host\s)", after_block)
        if next_host:
            remaining = after_block[next_host.start():]
        else:
            remaining = ""
        cleaned = before.rstrip() + remaining

        with open(config_path, "w") as f:
            f.write(cleaned if cleaned.strip() else "")

        print(f"  Removed '{alias}' entry from SSH config.")
        logger.info("Removed WizIsland entry from SSH config.")
    except Exception as exc:
        logger.error("Failed to clean SSH config: %s", exc)
        print(f"  [ERROR] Could not remove entry: {exc}")


def print_connection_instructions(host, port, config_path, username="wizguest",
                                  alias="WizIsland", reachable=None):
    """Print detailed connection instructions for the user."""
    # Connection status indicator
    if reachable is True:
        status = "REACHABLE"
    elif reachable is False:
        status = "UNREACHABLE (host may not be ready yet)"
    else:
        status = "NOT TESTED"

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
        f"   Username           : {username}",
        f"   Connection Status  : {status}",
        "",
        "  ------------------------------------------------------------",
        "   HOW TO CONNECT",
        "  ------------------------------------------------------------",
        "",
        "   OPTION 1: Terminal SSH (Quickest)",
        f"     $ ssh {alias}",
        "",
        "   OPTION 2: Terminal SSH (Manual)",
        f"     $ ssh {username}@{host} -p {port}",
        "",
        "   OPTION 3: VS Code Remote-SSH",
        "     1. Install the 'Remote - SSH' extension in VS Code",
        "        (Extension ID: ms-vscode-remote.remote-ssh)",
        "     2. Press Ctrl+Shift+P (or Cmd+Shift+P on macOS)",
        "     3. Type: 'Remote-SSH: Connect to Host...'",
        f"     4. Select '{alias}' from the dropdown list",
        "     5. Enter the password when prompted",
        "",
        "  ------------------------------------------------------------",
        "   TIPS",
        "  ------------------------------------------------------------",
        "   - The guest password is provided by the Host operator.",
        "   - Ask the Host for the password before connecting.",
        "   - StrictHostKeyChecking is disabled for convenience.",
        "   - To remove this config later, select 'Clean SSH Config'",
        "     from the User Mode menu.",
        "",
        "  ============================================================",
    ]
    print("\n".join(lines))


def run_user_mode():
    """Main entry point for User Mode (client)."""
    print("\n  ============================================================")
    print("   WIZ ISLAND - USER MODE (CLIENT)")
    print("  ============================================================")
    print()
    print("   [1]  Connect to a Host")
    print("   [2]  Clean/Remove WizIsland SSH Config")
    print("   [0]  Back to Main Menu")
    print()

    try:
        choice = input("   Select an option [0-2]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "0":
        return

    if choice == "2":
        remove_ssh_config()
        input("\n  Press Enter to return to the menu...")
        return

    if choice != "1":
        print("  Invalid choice.")
        input("  Press Enter to return to the menu...")
        return

    # Prompt for the Ngrok URL
    print("\n  Accepted formats:")
    print("    - tcp://0.tcp.ngrok.io:12345")
    print("    - 0.tcp.ngrok.io:12345")
    print("    - ssh wizguest@0.tcp.ngrok.io -p 12345")
    url_string = input("\n  Paste the Ngrok connection string: ").strip()

    if not url_string:
        print("  [ERROR] Connection string cannot be empty.")
        input("  Press Enter to return to the menu...")
        return

    host, port = parse_ngrok_url(url_string)
    if not host or not port:
        print(f"  [ERROR] Invalid connection string format: '{url_string}'")
        print("  Expected format: tcp://0.tcp.ngrok.io:12345 or 0.tcp.ngrok.io:12345")
        input("  Press Enter to return to the menu...")
        return

    print(f"\n  Parsed connection: {host}:{port}")

    # Test connectivity
    print("  Testing connection...")
    reachable = test_connection(host, port)
    if reachable:
        print("  Connection test: SUCCESS")
    else:
        print("  Connection test: Host not reachable (it may not be ready yet)")
        print("  The SSH config will be saved anyway — you can try connecting later.")

    # Detect platform-appropriate username
    username = "wizguest"  # Linux default
    try:
        user_choice = input(
            f"\n  Guest username [{username}]: "
        ).strip()
        if user_choice:
            username = user_choice
    except (EOFError, KeyboardInterrupt):
        pass

    print("  Updating SSH config...")

    try:
        config_path = update_ssh_config(host, port, username=username)
    except Exception as exc:
        print(f"  [ERROR] Failed to update SSH config: {exc}")
        input("  Press Enter to return to the menu...")
        return

    print_connection_instructions(host, port, config_path, username=username, reachable=reachable)

    input("  Press Enter to return to the main menu...")
