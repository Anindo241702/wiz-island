"""
WIZ ISLAND - Host-Side Orchestration & Dashboard (host.py)

Handles Ngrok tunnel creation, real-time system monitoring dashboard,
and host-mode lifecycle management.
"""

import json
import logging
import os
import platform
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request

import psutil

from . import storage

logger = logging.getLogger("wiz_island.host")

# Global state
_ngrok_process = None
_tunnel_url = None
_running = False
_start_time = None
_lock = threading.Lock()


def clear_screen():
    """Clear terminal screen cross-platform."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def _format_uptime(seconds):
    """Format seconds into a human-readable uptime string."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def prompt_storage_quota():
    """Ask the user for a storage quota in GB."""
    while True:
        try:
            raw = input("\n  Enter storage quota in GB (e.g., 10): ").strip()
            if not raw:
                print("  Please enter a value.")
                continue
            size_gb = int(raw)
            if size_gb < 1:
                print("  Please enter a value of at least 1 GB.")
                continue
            if size_gb > 500:
                confirm = input(
                    f"  {size_gb} GB is very large. Are you sure? (yes/no): "
                ).strip().lower()
                if confirm not in ("yes", "y"):
                    continue
            return size_gb
        except ValueError:
            print("  Invalid input. Please enter a whole number.")
        except (EOFError, KeyboardInterrupt):
            print("\n  Cancelled.")
            return None


def prompt_ngrok_authtoken():
    """Prompt the user for their Ngrok auth token and apply it."""
    print("\n  You can get your AuthToken from: https://dashboard.ngrok.com/get-started/your-authtoken")
    token = input("  Enter your Ngrok AuthToken: ").strip()
    if not token:
        print("  [ERROR] AuthToken cannot be empty.")
        return False

    try:
        storage.run_command(
            f"ngrok config add-authtoken {token}",
            description="apply Ngrok authtoken",
        )
        print("  Ngrok AuthToken applied successfully.")
        return True
    except Exception as exc:
        logger.error("Failed to apply Ngrok authtoken: %s", exc)
        print(f"  [ERROR] Failed to apply AuthToken: {exc}")
        return False


def _show_ngrok_error(stdout_text, stderr_text):
    """Display ngrok error output and helpful suggestions."""
    all_output = ((stdout_text or "") + "\n" + (stderr_text or "")).strip()

    if all_output:
        print()
        print("  --- Ngrok Output ---")
        for line in all_output.split("\n"):
            line = line.strip()
            if line:
                print(f"  {line}")
        print("  ---------------------")
        print()

    lower_output = all_output.lower()
    if "invalid" in lower_output and "authtoken" in lower_output:
        print("  Your AuthToken appears to be invalid.")
        print("  Get a new one from: https://dashboard.ngrok.com/get-started/your-authtoken")
    elif "err_ngrok_108" in lower_output or "already running" in lower_output:
        print("  Another Ngrok tunnel is already running (free tier allows only 1).")
        print("  Close any other Ngrok sessions first.")
    elif "upgrade" in lower_output or "paid" in lower_output or "subscription" in lower_output:
        print("  Your Ngrok plan may not support TCP tunnels.")
        print("  TCP tunnels require a paid Ngrok plan (Personal or higher).")
        print("  Upgrade at: https://dashboard.ngrok.com/billing/subscription")
    elif "err_ngrok_4018" in lower_output:
        print("  Ngrok requires a verified account with an AuthToken.")
        print("  Sign up: https://dashboard.ngrok.com/signup")
        print("  Install: https://dashboard.ngrok.com/get-started/your-authtoken")
    elif not all_output:
        print("  Possible causes:")
        print("    - Invalid or expired AuthToken")
        print("    - Another Ngrok tunnel already running (free tier: 1 max)")
        print("    - TCP tunnels require a paid Ngrok plan")
        print("    - Network/firewall blocking Ngrok")
        print("  AuthToken: https://dashboard.ngrok.com/get-started/your-authtoken")
        print("  Upgrade:   https://dashboard.ngrok.com/billing/subscription")
    else:
        print("  Possible causes:")
        print("    - Invalid or expired AuthToken")
        print("    - Another Ngrok tunnel already running (free tier: 1 max)")
        print("    - TCP tunnels require a paid Ngrok plan")
        print("    - Network/firewall blocking Ngrok")


def start_ngrok_tunnel():
    """Start an Ngrok TCP tunnel on port 22 and detect the public URL.

    Starts ngrok as a background process, then polls the ngrok local API
    at 127.0.0.1:4040 to discover the tunnel URL. This approach is more
    reliable across platforms than parsing stdout.
    """
    global _ngrok_process, _tunnel_url

    print("\n  Starting Ngrok TCP tunnel on port 22...")

    try:
        _ngrok_process = subprocess.Popen(
            ["ngrok", "tcp", "22"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        logger.error("Ngrok binary not found in PATH.")
        print("  [ERROR] Ngrok is not installed or not in PATH.")
        print("  Please ensure Ngrok is installed and accessible.")
        return None
    except Exception as exc:
        logger.error("Failed to start Ngrok: %s", exc)
        print(f"  [ERROR] Failed to start Ngrok: {exc}")
        return None

    # Give ngrok a moment to start or fail
    time.sleep(3)

    # Check if ngrok exited immediately (auth error, plan limit, etc.)
    if _ngrok_process.poll() is not None:
        stdout_text = _ngrok_process.stdout.read() if _ngrok_process.stdout else ""
        stderr_text = _ngrok_process.stderr.read() if _ngrok_process.stderr else ""
        logger.error("Ngrok exited. stdout: %s | stderr: %s", stdout_text, stderr_text)
        print("  [ERROR] Ngrok exited unexpectedly.")
        _show_ngrok_error(stdout_text, stderr_text)
        return None

    # Poll the ngrok local API for the tunnel URL
    print("  Waiting for tunnel to establish...")
    for attempt in range(15):
        # Check if process died while waiting
        if _ngrok_process.poll() is not None:
            stdout_text = _ngrok_process.stdout.read() if _ngrok_process.stdout else ""
            stderr_text = _ngrok_process.stderr.read() if _ngrok_process.stderr else ""
            logger.error("Ngrok died during polling. stdout: %s | stderr: %s",
                         stdout_text, stderr_text)
            print("  [ERROR] Ngrok process terminated.")
            _show_ngrok_error(stdout_text, stderr_text)
            return None

        try:
            resp = urllib.request.urlopen(
                "http://127.0.0.1:4040/api/tunnels", timeout=5
            )
            data = json.loads(resp.read().decode())
            for tunnel in data.get("tunnels", []):
                public_url = tunnel.get("public_url", "")
                if public_url.startswith("tcp://"):
                    _tunnel_url = public_url
                    logger.info("Ngrok tunnel established: %s", _tunnel_url)
                    return _tunnel_url
        except Exception as exc:
            logger.debug("Ngrok API attempt %d: %s", attempt + 1, exc)

        time.sleep(2)

    print("  [ERROR] Could not determine Ngrok tunnel URL after 30 seconds.")
    print("  Please check your Ngrok AuthToken and internet connection.")
    return None


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


def get_network_io():
    """Return network I/O counters."""
    try:
        counters = psutil.net_io_counters()
        return {
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
        }
    except Exception as exc:
        logger.debug("Network IO error: %s", exc)
        return {"bytes_sent": 0, "bytes_recv": 0}


def _format_bytes(num_bytes):
    """Format bytes into human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def _get_gpu_info():
    """Detect GPU information if available."""
    # Try NVIDIA GPU via nvidia-smi
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 2:
                return f"{parts[0]} ({parts[1]}% utilization)"
            return parts[0]
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # Try to detect via platform-specific methods
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and l.strip() != "Name"]
                if lines:
                    return lines[0]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
    else:
        try:
            result = subprocess.run(
                ["lspci"], capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "VGA" in line or "3D" in line or "Display" in line:
                        name = line.split(": ", 1)[-1] if ": " in line else line
                        return name.strip()[:60]
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass

    return "Not detected"


def render_dashboard():
    """Render the real-time dashboard to the terminal."""
    global _running, _start_time

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
    _start_time = time.time()
    prev_net = get_network_io()
    prev_time = time.time()

    while _running:
        try:
            clear_screen()

            cpu_percent = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count(logical=True)
            mem = psutil.virtual_memory()
            disk = get_disk_usage(mount_path)
            connections = get_active_connections()
            uptime = _format_uptime(time.time() - _start_time)

            # Calculate network rates
            curr_net = get_network_io()
            curr_time = time.time()
            elapsed = max(curr_time - prev_time, 0.1)
            send_rate = (curr_net["bytes_sent"] - prev_net["bytes_sent"]) / elapsed
            recv_rate = (curr_net["bytes_recv"] - prev_net["bytes_recv"]) / elapsed
            prev_net = curr_net
            prev_time = curr_time

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
                f"   Uptime           : {uptime}",
                "",
                "  ------------------------------------------------------------",
                "   SYSTEM PERFORMANCE",
                "  ------------------------------------------------------------",
                f"   CPU Usage        : {_progress_bar(cpu_percent)} {cpu_percent:.1f}%"
                f"  ({cpu_count} cores)",
                f"   RAM Usage        : {_progress_bar(mem.percent)} {mem.percent:.1f}%"
                f"  ({mem.used // (1024**2)} / {mem.total // (1024**2)} MB)",
                f"   RAM Available    : {_format_bytes(mem.available)}",
                f"   GPU             : {_get_gpu_info()}",
                "",
                "  ------------------------------------------------------------",
                "   STORAGE (Sandbox)",
                "  ------------------------------------------------------------",
                f"   Total            : {disk['total_gb']} GB",
                f"   Used             : {_progress_bar(disk['percent'])} "
                f"{disk['used_gb']} GB ({disk['percent']}%)",
                f"   Free             : {disk['free_gb']} GB",
                f"   Mount Path       : {mount_path}",
                "",
                "  ------------------------------------------------------------",
                "   NETWORK",
                "  ------------------------------------------------------------",
                f"   Active SSH Conns : {connections}",
                f"   Upload Rate      : {_format_bytes(send_rate)}/s",
                f"   Download Rate    : {_format_bytes(recv_rate)}/s",
                f"   Total Sent       : {_format_bytes(curr_net['bytes_sent'])}",
                f"   Total Received   : {_format_bytes(curr_net['bytes_recv'])}",
                "",
                "  ============================================================",
                "   Press 'x' then Enter to activate PANIC BUTTON (Ctrl+C also works)",
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
    with _lock:
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
    print("  ============================================================")
    print("   !! PANIC BUTTON ACTIVATED !!")
    print("  ============================================================")
    print("  Initiating emergency shutdown sequence...\n")

    print("  [1/4] Stopping Ngrok tunnel...")
    stop_ngrok()
    print("         Done.")

    print("  [2/4] Terminating guest SSH sessions...")
    kill_guest_sessions()
    print("         Done.")

    print("  [3/4] Unmounting virtual disks and removing guest accounts...")
    try:
        storage.teardown_storage()
    except Exception as exc:
        logger.error("Teardown error: %s", exc)
        print(f"  [WARNING] Partial teardown: {exc}")
    print("         Done.")

    print("  [4/4] Cleanup complete.")
    print("\n  ============================================================")
    print("   Machine returned to native state.")
    print("  ============================================================")

    if _start_time:
        print(f"  Session was active for: {_format_uptime(time.time() - _start_time)}")

    print("\n  Press Enter to exit.")

    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass


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


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM gracefully."""
    logger.info("Received signal %d, initiating panic shutdown.", signum)
    panic_shutdown()
    sys.exit(0)


def run_host_mode():
    """Main entry point for Host Mode."""
    global _running

    # Install signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    print("\n  ============================================================")
    print("   WIZ ISLAND - HOST MODE SETUP")
    print("  ============================================================")

    # Step 1: Storage quota
    size_gb = prompt_storage_quota()
    if size_gb is None:
        return
    print(f"\n  Setting up {size_gb} GB sandbox environment...\n")

    try:
        storage.setup_storage(size_gb)
    except Exception as exc:
        logger.error("Storage setup failed: %s", exc)
        print(f"\n  [ERROR] Storage setup failed: {exc}")
        print("  Please check the log for details and ensure you are running as Admin/root.")
        input("\n  Press Enter to return to the menu...")
        return

    # Step 2: Ngrok AuthToken
    if not prompt_ngrok_authtoken():
        input("\n  Press Enter to return to the menu...")
        return

    # Step 3: Start tunnel
    tunnel_url = start_ngrok_tunnel()
    if not tunnel_url:
        print("  [ERROR] Could not establish Ngrok tunnel.")
        input("\n  Press Enter to return to the menu...")
        return

    # Display connection details prominently for sharing
    guest_user, guest_pass = storage.get_guest_credentials()
    print()
    print("  ============================================================")
    print("   TUNNEL ESTABLISHED - SHARE THESE WITH YOUR GUEST")
    print("  ============================================================")
    print(f"   Tunnel URL     : {tunnel_url}")
    print(f"   SSH Command    : ssh {guest_user}@"
          f"{tunnel_url.replace('tcp://', '').split(':')[0]} "
          f"-p {tunnel_url.replace('tcp://', '').split(':')[1]}")
    print(f"   Guest Username : {guest_user}")
    print(f"   Guest Password : {guest_pass}")
    print("  ============================================================")
    print()
    print("  Copy the above details and send them to your guest.")
    print("  The guest should run Wiz Island in User Mode and paste")
    print("  the connection string, or connect via VS Code Remote-SSH.")
    print()
    input("  Press Enter to launch the live dashboard...")
    print()

    # Step 4: Launch dashboard with panic listener
    listener_thread = threading.Thread(target=panic_listener, daemon=True)
    listener_thread.start()

    try:
        render_dashboard()
    except KeyboardInterrupt:
        panic_shutdown()
