"""
WIZ ISLAND - Client-Side SSH Configuration Injection (client.py)

Handles parsing of the tunnel connection string, updating the local
SSH config file, and providing connection instructions for VS Code
Remote-SSH.
"""

import json
import logging
import os
import platform
import re
import socket
import time
import urllib.request
import urllib.error

logger = logging.getLogger("wiz_island.client")


def fetch_room_url(room_code, timeout=10):
    """Fetch the latest tunnel URL published by the Host to ntfy.sh.

    Returns the most recent message body (the tunnel URL) or None if
    no message is available yet.
    """
    room_code = room_code.strip()
    url = f"https://ntfy.sh/{room_code}/raw?poll=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WizIsland"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        logger.debug("ntfy poll failed: %s", exc)
        return None

    # raw endpoint returns one message per line; blank lines are keepalives
    latest = None
    for line in body.splitlines():
        line = line.strip()
        if line:
            latest = line
    return latest


def watch_room_code(room_code, username, host_platform, alias="WizIsland",
                    interval=15):
    """Foreground loop: poll ntfy.sh and auto-update SSH config on changes.

    Keeps running until interrupted. Every time the Host publishes a new
    tunnel URL (e.g. after a 60-minute Pinggy reconnect), the SSH config
    is updated automatically so the coder never has to re-enter a URL.
    """
    current_host = None
    current_port = None

    print("\n  ============================================================")
    print("   WIZ ISLAND - AUTO-CONNECT WATCHER")
    print("  ============================================================")
    print(f"   Room Code : {room_code}")
    print(f"   Alias     : {alias}")
    print()
    print("   Watching for the Host's tunnel URL. Keep this window open —")
    print("   it auto-updates your SSH config whenever the Host reconnects.")
    print("   Connect via 'ssh WizIsland' or VS Code in another window.")
    print("   Press Ctrl+C to stop watching.")
    print("  ============================================================")
    print()

    try:
        while True:
            url = fetch_room_url(room_code)
            if url:
                host, port = parse_tunnel_url(url)
                if host and port and (host != current_host or port != current_port):
                    try:
                        update_ssh_config(host, port, username=username,
                                          alias=alias)
                        current_host, current_port = host, port
                        stamp = time.strftime("%H:%M:%S")
                        print(f"  [{stamp}] Tunnel URL updated -> {host}:{port}")
                        print(f"            SSH config refreshed. Reconnect if "
                              f"your session dropped.")
                    except Exception as exc:
                        logger.error("Failed to update SSH config: %s", exc)
                        print(f"  [ERROR] Could not update SSH config: {exc}")
            else:
                logger.debug("No tunnel URL published yet for %s", room_code)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  Stopped watching. Your SSH config keeps the last known URL.")


def get_ssh_config_path():
    """Return the SSH config file path for the current platform."""
    if platform.system() == "Windows":
        return os.path.join(os.environ.get("USERPROFILE", ""), ".ssh", "config")
    else:
        return os.path.expanduser("~/.ssh/config")


def parse_tunnel_url(url_string):
    """Parse a tunnel TCP URL into (host, port).

    Accepts formats like:
        tcp://hostname.pinggy.link:12345
        hostname.pinggy.link:12345
        ssh wizguest@hostname -p 12345
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
        f"    ServerAliveInterval 30\n"
        f"    ServerAliveCountMax 5\n"
        f"    ConnectTimeout 30\n"
    )

    try:
        existing = ""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                existing = f.read()

        # Remove ALL previous WizIsland entries — with or without the marker
        # First: remove entries with the marker comment
        existing = re.sub(
            r"\n?# --- Wiz Island Connection ---\n"
            r"Host [^\n]*\n"
            r"(?:[ \t]+[^\n]*\n)*",
            "",
            existing,
        )
        # Second: remove any bare "Host WizIsland" blocks (from older versions)
        existing = re.sub(
            r"\n?Host " + re.escape(alias) + r"\s*\n"
            r"(?:[ \t]+[^\n]*\n)*",
            "",
            existing,
        )

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
        has_marker = marker_start in existing
        has_host = re.search(r"Host\s+" + re.escape(alias) + r"\s", existing)

        if not has_marker and not has_host:
            print(f"  No '{alias}' entry found in SSH config.")
            return

        # Remove entries with marker
        cleaned = re.sub(
            r"\n?# --- Wiz Island Connection ---\n"
            r"Host [^\n]*\n"
            r"(?:[ \t]+[^\n]*\n)*",
            "",
            existing,
        )
        # Remove bare Host entries (from older versions)
        cleaned = re.sub(
            r"\n?Host " + re.escape(alias) + r"\s*\n"
            r"(?:[ \t]+[^\n]*\n)*",
            "",
            cleaned,
        )

        with open(config_path, "w") as f:
            f.write(cleaned.strip() + "\n" if cleaned.strip() else "")

        print(f"  Removed '{alias}' entry from SSH config.")
        logger.info("Removed WizIsland entry from SSH config.")
    except Exception as exc:
        logger.error("Failed to clean SSH config: %s", exc)
        print(f"  [ERROR] Could not remove entry: {exc}")


def _get_vscode_settings_path():
    """Return the VS Code user settings.json path."""
    plat = platform.system()
    if plat == "Windows":
        base = os.environ.get("APPDATA", "")
        return os.path.join(base, "Code", "User", "settings.json")
    elif plat == "Darwin":
        return os.path.expanduser(
            "~/Library/Application Support/Code/User/settings.json"
        )
    else:
        return os.path.expanduser("~/.config/Code/User/settings.json")


def configure_vscode_remote_platform(alias="WizIsland", host_platform="windows"):
    """Set remote.SSH.remotePlatform in VS Code settings.

    This tells VS Code the host OS so it skips auto-detection (which
    fails when the guest user lacks WMI permissions on Windows).
    """
    settings_path = _get_vscode_settings_path()
    settings = {}

    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                content = f.read().strip()
                if content:
                    settings = json.loads(content)
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("Could not read VS Code settings: %s", exc)
            settings = {}

    remote_platform = settings.get("remote.SSH.remotePlatform", {})
    if not isinstance(remote_platform, dict):
        remote_platform = {}

    remote_platform[alias] = host_platform
    settings["remote.SSH.remotePlatform"] = remote_platform

    try:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=4)
        logger.info(
            "Set remote.SSH.remotePlatform.%s = %s in VS Code settings.",
            alias, host_platform,
        )
        return True
    except (IOError, OSError) as exc:
        logger.warning("Could not update VS Code settings: %s", exc)
        return False


def print_connection_instructions(host, port, config_path, username="wizguest",
                                  alias="WizIsland", reachable=None, password=None):
    """Print detailed connection instructions for the user."""
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
    ]
    if password:
        lines.append(f"   Password           : {password}")
    lines.extend([
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
        "   OPTION 3: VS Code Remote-SSH (Recommended for Development)",
        "     1. Install the 'Remote - SSH' extension in VS Code",
        "        (Extension ID: ms-vscode-remote.remote-ssh)",
        "     2. Press Ctrl+Shift+P (or Cmd+Shift+P on macOS)",
        "     3. Type: 'Remote-SSH: Connect to Host...'",
        f"     4. Select '{alias}' from the dropdown list",
        "     5. Enter the password when prompted",
        "     6. VS Code will install its remote server and open a window",
        "",
        "   AFTER CONNECTING VIA VS CODE:",
        "     - The Explorer panel shows the Host's sandbox filesystem",
        "     - The Terminal runs on the Host machine",
        "     - You have access to Host's CPU, RAM, GPU for builds",
        "     - Install extensions on the remote side for full IDE features",
        "",
        "  ------------------------------------------------------------",
        "   TIPS",
        "  ------------------------------------------------------------",
    ])
    if not password:
        lines.extend([
            "   - Ask the Host operator for the guest password.",
            "   - The Host dashboard shows the password to share.",
        ])
    lines.extend([
        "   - StrictHostKeyChecking is disabled for convenience.",
        "   - To remove this config later, select 'Clean SSH Config'",
        "     from the User Mode menu.",
        "",
        "   IMPORTANT: The tunnel URL changes every time the Host",
        "   restarts. If you get 'Could not resolve hostname', re-run",
        "   User Mode with the new URL from the Host dashboard.",
        "",
        "  ============================================================",
    ])
    print("\n".join(lines))


def _prompt_host_platform_and_user():
    """Shared prompt for host OS and guest username/password."""
    print("\n  What OS is the Host running?")
    print("    [1] Windows (default)")
    print("    [2] Linux")
    try:
        os_choice = input("  Select [1-2]: ").strip()
    except (EOFError, KeyboardInterrupt):
        os_choice = "1"
    if os_choice == "2":
        host_platform = "linux"
        default_username = "wizguest"
    else:
        host_platform = "windows"
        default_username = "WizGuest"

    try:
        user_choice = input(
            f"\n  Guest username [{default_username}]: "
        ).strip()
        username = user_choice if user_choice else default_username
    except (EOFError, KeyboardInterrupt):
        username = default_username

    password = None
    try:
        password = input(
            "  Guest password (press Enter to skip): "
        ).strip()
        if not password:
            password = None
    except (EOFError, KeyboardInterrupt):
        pass

    return host_platform, username, password


def run_room_code_mode():
    """Connect using a room code with automatic tunnel URL discovery."""
    print("\n  Enter the ROOM CODE shown on the Host's dashboard.")
    print("  (Looks like: wiz-x7k9m2)")
    try:
        room_code = input("\n  Room code: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if not room_code:
        print("  [ERROR] Room code cannot be empty.")
        input("  Press Enter to return to the menu...")
        return

    host_platform, username, password = _prompt_host_platform_and_user()

    # Initial fetch so the user gets connected right away
    print(f"\n  Looking up the current tunnel URL for '{room_code}'...")
    url = fetch_room_url(room_code)
    if not url:
        print("  No tunnel URL published yet. The watcher will keep trying.")
        print("  Make sure the Host is running and shares this exact room code.")
    else:
        host, port = parse_tunnel_url(url)
        if host and port:
            try:
                config_path = update_ssh_config(host, port, username=username)
                print(f"  Connected! SSH config set to {host}:{port}")
            except Exception as exc:
                print(f"  [ERROR] Failed to update SSH config: {exc}")
                input("  Press Enter to return to the menu...")
                return

            print("  Configuring VS Code Remote-SSH platform...")
            if configure_vscode_remote_platform("WizIsland", host_platform):
                print(f"  VS Code platform set to: {host_platform}")

            print("\n  Installing file-transfer commands (Wupload/Wdownload)...")
            install_client_commands()

            print_connection_instructions(
                host, port, config_path, username=username,
                reachable=test_connection(host, port), password=password,
            )
        else:
            print(f"  [WARNING] Could not parse published URL: {url}")

    # Make sure VS Code platform is set even if first fetch failed
    configure_vscode_remote_platform("WizIsland", host_platform)

    # Start the foreground watcher (auto-updates on every reconnect)
    watch_room_code(room_code, username, host_platform)
    input("\n  Press Enter to return to the menu...")


def install_client_commands(alias="WizIsland"):
    """Install convenience shell commands (Wupload/Wdownload/Wconnect).

    Writes a small helper script to ~/.wiz_island/ and sources it from
    the user's shell profile so coders get easy file-transfer commands
    without remembering scp syntax. Idempotent — safe to run repeatedly.
    """
    home = os.path.expanduser("~")
    wiz_dir = os.path.join(home, ".wiz_island")
    try:
        os.makedirs(wiz_dir, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not create %s: %s", wiz_dir, exc)
        return False

    is_windows = platform.system() == "Windows"

    if is_windows:
        cmd_file = os.path.join(wiz_dir, "commands.ps1")
        content = f"""# Wiz Island client commands (auto-generated)
function Wconnect {{ ssh {alias} @args }}
function Wupload {{
    param([Parameter(Mandatory=$true)][string]$Source, [string]$Dest = ".")
    scp -r $Source "{alias}:$Dest"
}}
function Wdownload {{
    param([Parameter(Mandatory=$true)][string]$Source, [string]$Dest = ".")
    scp -r "{alias}:$Source" $Dest
}}
function Whelp {{
    Write-Host "Wiz Island commands:" -ForegroundColor Cyan
    Write-Host "  Wconnect                    - open an SSH session to the host"
    Write-Host "  Wupload <local> [remote]    - send a file/folder to the host (default: home)"
    Write-Host "  Wdownload <remote> [local]  - get a file/folder from the host (default: current dir)"
    Write-Host "  Whelp                       - show this help"
}}
"""
        try:
            with open(cmd_file, "w") as f:
                f.write(content)
        except IOError as exc:
            logger.warning("Could not write commands.ps1: %s", exc)
            return False

        # Resolve the real PowerShell profile path and add a dot-source line
        source_line = f'. "{cmd_file}"'
        profile_paths = _get_powershell_profiles()
        installed = False
        for profile_path in profile_paths:
            try:
                os.makedirs(os.path.dirname(profile_path), exist_ok=True)
                existing = ""
                if os.path.exists(profile_path):
                    with open(profile_path, "r") as f:
                        existing = f.read()
                if source_line not in existing:
                    with open(profile_path, "a") as f:
                        f.write(f"\n# Wiz Island commands\n{source_line}\n")
                installed = True
            except OSError as exc:
                logger.debug("Could not update profile %s: %s", profile_path, exc)
        print(f"  Installed commands: Wconnect, Wupload, Wdownload, Whelp")
        print(f"  (script: {cmd_file})")
        print("  Open a NEW PowerShell window, then run 'Whelp' to see them.")
        return installed
    else:
        cmd_file = os.path.join(wiz_dir, "commands.sh")
        content = f"""# Wiz Island client commands (auto-generated)
Wconnect() {{ ssh {alias} "$@"; }}
Wupload() {{
    if [ -z "$1" ]; then echo "Usage: Wupload <local> [remote]"; return 1; fi
    scp -r "$1" "{alias}:${{2:-.}}"
}}
Wdownload() {{
    if [ -z "$1" ]; then echo "Usage: Wdownload <remote> [local]"; return 1; fi
    scp -r "{alias}:$1" "${{2:-.}}"
}}
Whelp() {{
    echo "Wiz Island commands:"
    echo "  Wconnect                    - open an SSH session to the host"
    echo "  Wupload <local> [remote]    - send a file/folder to the host (default: home)"
    echo "  Wdownload <remote> [local]  - get a file/folder from the host (default: current dir)"
    echo "  Whelp                       - show this help"
}}
"""
        try:
            with open(cmd_file, "w") as f:
                f.write(content)
        except IOError as exc:
            logger.warning("Could not write commands.sh: %s", exc)
            return False

        source_line = f'[ -f "{cmd_file}" ] && . "{cmd_file}"'
        installed = False
        for rc in (".bashrc", ".zshrc", ".profile"):
            rc_path = os.path.join(home, rc)
            if rc == ".profile" and (
                os.path.exists(os.path.join(home, ".bashrc"))
                or os.path.exists(os.path.join(home, ".zshrc"))
            ):
                continue
            try:
                existing = ""
                if os.path.exists(rc_path):
                    with open(rc_path, "r") as f:
                        existing = f.read()
                elif rc != ".profile":
                    continue
                if source_line not in existing:
                    with open(rc_path, "a") as f:
                        f.write(f"\n# Wiz Island commands\n{source_line}\n")
                installed = True
            except OSError as exc:
                logger.debug("Could not update %s: %s", rc_path, exc)
        print(f"  Installed commands: Wconnect, Wupload, Wdownload, Whelp")
        print(f"  (script: {cmd_file})")
        print("  Open a NEW terminal (or run 'source ~/.bashrc'), then 'Whelp'.")
        return installed


def _get_powershell_profiles():
    """Return likely PowerShell profile paths for the current user."""
    profiles = []
    try:
        import subprocess
        for exe in ("powershell", "pwsh"):
            try:
                out = subprocess.run(
                    [exe, "-NoProfile", "-Command", "$PROFILE.CurrentUserAllHosts"],
                    capture_output=True, text=True, timeout=20,
                )
                path = (out.stdout or "").strip()
                if path:
                    profiles.append(path)
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
    except Exception as exc:
        logger.debug("Could not resolve PowerShell profile: %s", exc)

    # Fallback to the standard Documents locations
    if not profiles:
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        profiles = [
            os.path.join(docs, "WindowsPowerShell", "profile.ps1"),
            os.path.join(docs, "PowerShell", "profile.ps1"),
        ]
    return profiles


def run_user_mode():
    """Main entry point for User Mode (client)."""
    print("\n  ============================================================")
    print("   WIZ ISLAND - USER MODE (CLIENT)")
    print("  ============================================================")
    print()
    print("   [1]  Connect via Room Code (auto-reconnect, recommended)")
    print("   [2]  Connect via Tunnel URL (manual, one-time)")
    print("   [3]  Clean/Remove WizIsland SSH Config")
    print("   [4]  Install file-transfer commands (Wupload/Wdownload)")
    print("   [0]  Back to Main Menu")
    print()

    try:
        choice = input("   Select an option [0-4]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return

    if choice == "0":
        return

    if choice == "3":
        remove_ssh_config()
        input("\n  Press Enter to return to the menu...")
        return

    if choice == "4":
        print("\n  Installing Wiz Island file-transfer commands...")
        install_client_commands()
        input("\n  Press Enter to return to the menu...")
        return

    if choice == "1":
        run_room_code_mode()
        return

    if choice != "2":
        print("  Invalid choice.")
        input("  Press Enter to return to the menu...")
        return

    # Prompt for the tunnel URL
    print("\n  Enter the connection details provided by the Host operator.")
    print("  (You can find these on the Host's dashboard screen.)")
    print()
    print("  Accepted formats:")
    print("    - tcp://hostname.pinggy.link:12345")
    print("    - hostname.pinggy.link:12345")
    print("    - ssh wizguest@hostname -p 12345")
    url_string = input("\n  Paste the tunnel connection string: ").strip()

    if not url_string:
        print("  [ERROR] Connection string cannot be empty.")
        input("  Press Enter to return to the menu...")
        return

    host, port = parse_tunnel_url(url_string)
    if not host or not port:
        print(f"  [ERROR] Invalid connection string format: '{url_string}'")
        print("  Expected format: tcp://hostname.pinggy.link:12345 or hostname:12345")
        input("  Press Enter to return to the menu...")
        return

    print(f"\n  Parsed connection: {host}:{port}")

    # Test connectivity
    print("  Testing connection...")
    reachable = test_connection(host, port)
    if reachable:
        print("  Connection test: SUCCESS - Host is reachable!")
    else:
        print("  Connection test: Host not reachable (it may not be ready yet)")
        print("  The SSH config will be saved anyway — you can try connecting later.")

    # Host platform
    print("\n  What OS is the Host running?")
    print("    [1] Windows (default)")
    print("    [2] Linux")
    try:
        os_choice = input("  Select [1-2]: ").strip()
    except (EOFError, KeyboardInterrupt):
        os_choice = "1"
    if os_choice == "2":
        host_platform = "linux"
        default_username = "wizguest"
    else:
        host_platform = "windows"
        default_username = "WizGuest"

    # Guest username
    try:
        user_choice = input(
            f"\n  Guest username [{default_username}]: "
        ).strip()
        if user_choice:
            username = user_choice
        else:
            username = default_username
    except (EOFError, KeyboardInterrupt):
        username = default_username

    # Ask for password (optional, just to display it in instructions)
    password = None
    try:
        password = input(
            "  Guest password (press Enter to skip): "
        ).strip()
        if not password:
            password = None
    except (EOFError, KeyboardInterrupt):
        pass

    print("\n  Updating SSH config...")

    try:
        config_path = update_ssh_config(host, port, username=username)
    except Exception as exc:
        print(f"  [ERROR] Failed to update SSH config: {exc}")
        input("  Press Enter to return to the menu...")
        return

    # Configure VS Code remotePlatform
    print("  Configuring VS Code Remote-SSH platform...")
    if configure_vscode_remote_platform("WizIsland", host_platform):
        print(f"  VS Code platform set to: {host_platform}")
    else:
        print(f"  Could not auto-configure VS Code. Set manually:")
        print(f'    "remote.SSH.remotePlatform": {{"WizIsland": "{host_platform}"}}')

    print("\n  Installing file-transfer commands (Wupload/Wdownload)...")
    install_client_commands()

    print_connection_instructions(
        host, port, config_path, username=username,
        reachable=reachable, password=password,
    )

    input("  Press Enter to return to the main menu...")
