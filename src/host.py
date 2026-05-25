"""
WIZ ISLAND - Host-Side Orchestration & Dashboard (host.py)

Handles Ngrok tunnel creation, real-time system monitoring dashboard,
and host-mode lifecycle management.
"""

import logging
import os
import platform
import re
import subprocess
import sys
import threading
import time

import psutil

from . import storage

logger = logging.getLogger("wiz_island.host")

# Global state
_ngrok_process = None
_tunnel_url = None
_running = False


def clear_screen():
    """Clear terminal screen cross-platform."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def prompt_storage_quota():
    """Ask the user for a storage quota in GB."""
    while True:
        try:
            raw = input("\n  Enter storage quota in GB (e.g., 10): ").strip()
            size_gb = int(raw)
            if size_gb < 1:
                print("  Please enter a value of at least 1 GB.")
                continue
            if size_gb > 500:
                print("  Maximum recommended size is 500 GB.")
                continue
            return size_gb
        except ValueError:
            print("  Invalid input. Please enter a whole number.")


def prompt_ngrok_authtoken():
    """Prompt the user for their Ngrok auth token and apply it."""
    token = input("\n  Enter your Ngrok AuthToken: ").strip()
    if not token:
        print("  [ERROR] AuthToken cannot be empty.")
        sys.exit(1)

    try:
        storage.run_command(
            f"ngrok config add-authtoken {token}",
            description="apply Ngrok authtoken",
        )
        print("  Ngrok AuthToken applied successfully.")
    except Exception as exc:
        logger.error("Failed to apply Ngrok authtoken: %s", exc)
        print(f"  [ERROR] Failed to apply AuthToken: {exc}")
        sys.exit(1)


def start_ngrok_tunnel():
    """Start an Ngrok TCP tunnel on port 22 and parse the public URL."""
    global _ngrok_process, _tunnel_url

    print("\n  Starting Ngrok TCP tunnel on port 22...")

    try:
        _ngrok_process = subprocess.Popen(
            ["ngrok", "tcp", "22", "--log", "stdout", "--log-format", "term"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        logger.error("Ngrok binary not found in PATH.")
        print("  [ERROR] Ngrok is not installed or not in PATH.")
        sys.exit(1)
    except Exception as exc:
        logger.error("Failed to start Ngrok: %s", exc)
        print(f"  [ERROR] Failed to start Ngrok: {exc}")
        sys.exit(1)

    # Parse the tunnel URL from ngrok output
    url_pattern = re.compile(r"url=(tcp://[\w\.\-]+:\d+)")
    deadline = time.time() + 30

    while time.time() < deadline:
        if _ngrok_process.poll() is not None:
            logger.error("Ngrok process exited unexpectedly.")
            print("  [ERROR] Ngrok exited unexpectedly. Check your AuthToken.")
            sys.exit(1)

        line = _ngrok_process.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue

        logger.debug("ngrok: %s", line.strip())
        match = url_pattern.search(line)
        if match:
            _tunnel_url = match.group(1)
            logger.info("Ngrok tunnel established: %s", _tunnel_url)
            return _tunnel_url

    # Fallback: try the ngrok API
    try:
        import json
        import urllib.request
        resp = urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=5)
        data = json.loads(resp.read().decode())
        for tunnel in data.get("tunnels", []):
            public_url = tunnel.get("public_url", "")
            if public_url.startswith("tcp://"):
                _tunnel_url = public_url
                logger.info("Ngrok tunnel (via API): %s", _tunnel_url)
                return _tunnel_url
    except Exception as exc:
        logger.warning("Could not query Ngrok API: %s", exc)

    print("  [ERROR] Could not determine Ngrok tunnel URL within timeout.")
    sys.exit(1)


def get_active_connections():
    """Count active SSH connections using psutil."""
    count = 0
    try:
        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == "ESTABLISHED" and conn.laddr.port == 22:
                count += 1
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    except Exception as exc:
        logger.debug("Connection count error: %s", exc)
    return count


def get_disk_usage(path):
    """Return disk usage info for the given mount path."""
    try:
        usage = psutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024 ** 3), 2),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "free_gb": round(usage.free / (1024 ** 3), 2),
            "percent": usage.percent,
        }
    except Exception as exc:
        logger.debug("Disk usage error for %s: %s", path, exc)
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}


def render_dashboard():
    """Render the real-time dashboard to the terminal."""
    global _running

    mount_path = storage.get_mount_path()
    guest_user, guest_pass = storage.get_guest_credentials()

    # Parse host and port from tunnel URL
    tunnel_display = _tunnel_url or "N/A"
    ssh_host = "N/A"
    ssh_port = "N/A"
    if _tunnel_url:
        parts = _tunnel_url.replace("tcp://", "").split(":")
        if len(parts) == 2:
            ssh_host = parts[0]
            ssh_port = parts[1]

    _running = True

    while _running:
        try:
            clear_screen()

            cpu_percent = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = get_disk_usage(mount_path)
            connections = get_active_connections()

            # Build the dashboard
            lines = [
                "",
                "  ============================================================",
                "   WIZ ISLAND - HOST DASHBOARD",
                "  ============================================================",
                "",
                f"   TUNNEL URL       : {tunnel_display}",
                f"   SSH Command      : ssh {guest_user}@{ssh_host} -p {ssh_port}",
                f"   Guest Password   : {guest_pass}",
                "",
                "  ------------------------------------------------------------",
                "   SYSTEM PERFORMANCE",
                "  ------------------------------------------------------------",
                f"   CPU Usage        : {_progress_bar(cpu_percent)} {cpu_percent:.1f}%",
                f"   RAM Usage        : {_progress_bar(mem.percent)} {mem.percent:.1f}%"
                f"  ({mem.used // (1024**2)} / {mem.total // (1024**2)} MB)",
                "",
                "  ------------------------------------------------------------",
                "   STORAGE (Sandbox)",
                "  ------------------------------------------------------------",
                f"   Total            : {disk['total_gb']} GB",
                f"   Used             : {disk['used_gb']} GB ({disk['percent']}%)",
                f"   Free             : {disk['free_gb']} GB",
                f"   Mount Path       : {mount_path}",
                "",
                "  ------------------------------------------------------------",
                "   NETWORK",
                "  ------------------------------------------------------------",
                f"   Active SSH Conns : {connections}",
                "",
                "  ============================================================",
                "   Press 'x' then Enter to activate PANIC BUTTON",
                "  ============================================================",
                "",
            ]

            print("\n".join(lines))
            time.sleep(2)

        except KeyboardInterrupt:
            _running = False
            break
        except Exception as exc:
            logger.error("Dashboard render error: %s", exc)
            time.sleep(2)


def _progress_bar(percent, width=20):
    """Create a simple text-based progress bar."""
    filled = int(width * percent / 100)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}]"


def stop_ngrok():
    """Terminate the Ngrok process."""
    global _ngrok_process, _tunnel_url
    if _ngrok_process:
        try:
            _ngrok_process.terminate()
            _ngrok_process.wait(timeout=10)
            logger.info("Ngrok process terminated.")
        except subprocess.TimeoutExpired:
            _ngrok_process.kill()
            logger.warning("Ngrok process killed forcefully.")
        except Exception as exc:
            logger.error("Error stopping Ngrok: %s", exc)
        finally:
            _ngrok_process = None
            _tunnel_url = None


def kill_guest_sessions():
    """Terminate any active SSH sessions from the guest user."""
    guest_user, _ = storage.get_guest_credentials()
    plat = storage.get_platform()

    try:
        if plat == "windows":
            # Find and kill sshd processes for the guest user
            storage.run_command(
                f'taskkill /F /FI "USERNAME eq {guest_user}" /IM sshd.exe',
                description="kill guest SSH sessions",
                check=False,
            )
        else:
            storage.run_command(
                f"pkill -u {guest_user}",
                description="kill guest SSH sessions",
                check=False,
            )
        logger.info("Terminated sessions for user '%s'.", guest_user)
    except Exception as exc:
        logger.warning("Could not kill guest sessions: %s", exc)


def panic_shutdown():
    """Execute the full panic shutdown sequence."""
    global _running
    _running = False

    print("\n")
    print("  !! PANIC BUTTON ACTIVATED !!")
    print("  Initiating emergency shutdown sequence...\n")

    print("  [1/4] Stopping Ngrok tunnel...")
    stop_ngrok()

    print("  [2/4] Terminating guest SSH sessions...")
    kill_guest_sessions()

    print("  [3/4] Unmounting virtual disks and removing guest accounts...")
    try:
        storage.teardown_storage()
    except Exception as exc:
        logger.error("Teardown error: %s", exc)
        print(f"  [WARNING] Partial teardown: {exc}")

    print("  [4/4] Cleanup complete.")
    print("\n  Machine returned to native state.")
    print("  Press Enter to exit.")
    input()


def panic_listener():
    """Background thread listening for 'x' keypress to trigger panic shutdown."""
    while _running:
        try:
            user_input = input()
            if user_input.strip().lower() == "x":
                panic_shutdown()
                return
        except EOFError:
            break
        except Exception:
            break


def run_host_mode():
    """Main entry point for Host Mode."""
    global _running

    print("\n  ============================================================")
    print("   WIZ ISLAND - HOST MODE SETUP")
    print("  ============================================================")

    # Step 1: Storage quota
    size_gb = prompt_storage_quota()
    print(f"\n  Setting up {size_gb} GB sandbox environment...\n")

    try:
        storage.setup_storage(size_gb)
    except Exception as exc:
        logger.error("Storage setup failed: %s", exc)
        print(f"\n  [ERROR] Storage setup failed: {exc}")
        print("  Please check the log for details and ensure you are running as Admin/root.")
        return

    # Step 2: Ngrok AuthToken
    prompt_ngrok_authtoken()

    # Step 3: Start tunnel
    tunnel_url = start_ngrok_tunnel()
    print(f"\n  Tunnel established: {tunnel_url}")

    # Step 4: Launch dashboard with panic listener
    listener_thread = threading.Thread(target=panic_listener, daemon=True)
    listener_thread.start()

    try:
        render_dashboard()
    except KeyboardInterrupt:
        panic_shutdown()
