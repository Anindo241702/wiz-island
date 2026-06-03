"""
WIZ ISLAND - Host-Side Orchestration & Dashboard (host.py)

Handles Pinggy tunnel creation, real-time system monitoring dashboard,
and host-mode lifecycle management.
"""

import logging
import os
import platform
import random
import re
import signal
import string
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

import psutil

from . import storage

logger = logging.getLogger("wiz_island.host")

# Global state
_tunnel_process = None
_tunnel_url = None
_running = False
_start_time = None
_max_coders = 0
_room_code = None
_lock = threading.Lock()


def _generate_room_code():
    """Generate a short random room code for ntfy.sh coordination."""
    chars = string.ascii_lowercase + string.digits
    return "wiz-" + "".join(random.choices(chars, k=6))


def _publish_tunnel_url(url):
    """Publish the current tunnel URL to ntfy.sh so clients can auto-discover it."""
    global _room_code
    if not _room_code:
        return
    try:
        topic = f"https://ntfy.sh/{_room_code}"
        req = urllib.request.Request(
            topic,
            data=url.encode("utf-8"),
            headers={"Title": "WizIsland Tunnel URL"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        logger.info("Published tunnel URL to ntfy.sh/%s", _room_code)
    except Exception as exc:
        logger.warning("Could not publish to ntfy.sh: %s", exc)


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


def _ensure_tunnel_key():
    """Generate a temporary SSH key for Pinggy if one doesn't exist.

    Pinggy accepts any SSH key — this avoids interactive password prompts.
    The key is stored alongside the project so it persists between sessions.
    """
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_path = os.path.join(script_dir, ".pinggy_key")

    if os.path.exists(key_path):
        return key_path

    try:
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", key_path, "-N", "", "-q"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Generated Pinggy tunnel key at %s", key_path)
    except FileNotFoundError:
        logger.warning("ssh-keygen not found, trying RSA fallback.")
        try:
            subprocess.run(
                ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", key_path,
                 "-N", "", "-q"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.error("Cannot generate SSH key: %s", exc)
            return None
    except Exception as exc:
        logger.error("Cannot generate SSH key: %s", exc)
        return None

    return key_path


def start_pinggy_tunnel():
    """Start a Pinggy TCP tunnel on port 22 and parse the public URL.

    Uses SSH to create a reverse TCP tunnel via pinggy.io. No account
    or auth token required — works out of the box on free tier.
    """
    global _tunnel_process, _tunnel_url

    print("\n  Starting Pinggy TCP tunnel on port 22...")
    print("  (Free tunnel via pinggy.io — no account required)")

    # Generate a key so SSH authenticates without a password prompt
    key_path = _ensure_tunnel_key()

    ssh_cmd = [
        "ssh",
        "-p", "443",
        "-R", "0:localhost:22",
        "-T",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=60",
    ]

    if key_path and os.path.exists(key_path):
        ssh_cmd += ["-i", key_path]

    ssh_cmd.append("tcp@a.pinggy.io")

    try:
        _tunnel_process = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
        )
    except FileNotFoundError:
        logger.error("SSH client not found in PATH.")
        print("  [ERROR] SSH client (ssh) is not installed or not in PATH.")
        print("  OpenSSH Client is required for the Pinggy tunnel.")
        if platform.system() == "Windows":
            print("  Install: Settings > Apps > Optional Features > OpenSSH Client")
        else:
            print("  Install: sudo apt-get install openssh-client")
        return None
    except Exception as exc:
        logger.error("Failed to start Pinggy tunnel: %s", exc)
        print(f"  [ERROR] Failed to start tunnel: {exc}")
        return None

    url_pattern = re.compile(r"(tcp://[\w\.\-]+:\d+)")
    collected_output = []

    def _read_output():
        """Read stdout character-by-character to handle partial lines."""
        buf = ""
        try:
            while True:
                ch = _tunnel_process.stdout.read(1)
                if not ch:
                    if buf:
                        collected_output.append(buf)
                    break
                buf += ch
                if ch == "\n":
                    collected_output.append(buf.strip())
                    buf = ""
        except Exception:
            if buf:
                collected_output.append(buf)

    reader = threading.Thread(target=_read_output, daemon=True)
    reader.start()

    print("  Waiting for tunnel to establish...")
    deadline = time.time() + 30
    checked_idx = 0

    while time.time() < deadline:
        while checked_idx < len(collected_output):
            line = collected_output[checked_idx]
            checked_idx += 1
            logger.debug("pinggy: %s", line)
            match = url_pattern.search(line)
            if match:
                _tunnel_url = match.group(1)
                logger.info("Pinggy tunnel established: %s", _tunnel_url)
                _publish_tunnel_url(_tunnel_url)
                return _tunnel_url

        if _tunnel_process.poll() is not None:
            reader.join(timeout=3)
            while checked_idx < len(collected_output):
                line = collected_output[checked_idx]
                checked_idx += 1
                match = url_pattern.search(line)
                if match:
                    _tunnel_url = match.group(1)
                    logger.info("Pinggy tunnel established: %s", _tunnel_url)
                    _publish_tunnel_url(_tunnel_url)
                    return _tunnel_url

            all_output = "\n".join(collected_output)
            logger.error("Pinggy tunnel exited. Output: %s", all_output)
            print("  [ERROR] Tunnel process exited unexpectedly.")
            if all_output.strip():
                print()
                print("  --- Tunnel Output ---")
                for out_line in all_output.strip().split("\n"):
                    out_line = out_line.strip()
                    if out_line:
                        print(f"  {out_line}")
                print("  ----------------------")
                print()
            print("  Possible causes:")
            print("    - No internet connection")
            print("    - SSH client not working properly")
            print("    - Firewall blocking outbound SSH on port 443")
            return None

        time.sleep(0.5)

    print("  [ERROR] Could not detect tunnel URL within 30 seconds.")
    print("  Please check your internet connection.")
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


def _move_cursor_home():
    """Move cursor to top-left of terminal without clearing the screen."""
    if platform.system() == "Windows":
        try:
            import ctypes
            handle = ctypes.windll.kernel32.GetStdHandle(-11)
            ctypes.windll.kernel32.SetConsoleCursorPosition(handle, 0)
        except Exception:
            os.system("cls")
    else:
        sys.stdout.write("\033[H")
        sys.stdout.flush()


def _reconnect_tunnel():
    """Attempt to restart the Pinggy tunnel and return the new URL."""
    global _tunnel_process, _tunnel_url
    logger.info("Attempting tunnel reconnect...")
    with _lock:
        if _tunnel_process:
            try:
                _tunnel_process.terminate()
                _tunnel_process.wait(timeout=5)
            except Exception:
                try:
                    _tunnel_process.kill()
                except Exception:
                    pass
            _tunnel_process = None
            _tunnel_url = None

    new_url = start_pinggy_tunnel()
    if new_url:
        logger.info("Tunnel reconnected: %s", new_url)
    else:
        logger.error("Tunnel reconnect failed.")
    return new_url


def render_dashboard():
    """Render the real-time dashboard to the terminal."""
    global _running, _start_time, _tunnel_url

    mount_path = storage.get_mount_path()
    guest_user, guest_pass = storage.get_guest_credentials()

    _running = True
    _start_time = time.time()
    prev_net = get_network_io()
    prev_time = time.time()
    _reconnect_count = 0
    _tunnel_status = "CONNECTED"

    # Initial clear, then use cursor repositioning for flicker-free updates
    clear_screen()

    # Determine dashboard line count for padding
    dash_width = 62

    while _running:
        try:
            # Check tunnel health and auto-reconnect if needed
            if _tunnel_process and _tunnel_process.poll() is not None:
                _tunnel_status = "RECONNECTING..."
                logger.warning("Tunnel process died, auto-reconnecting...")
                clear_screen()
                new_url = _reconnect_tunnel()
                if new_url:
                    _tunnel_status = "CONNECTED (reconnected)"
                    _reconnect_count += 1
                    clear_screen()
                else:
                    _tunnel_status = "DISCONNECTED - reconnect failed"
                    # Wait before retrying
                    time.sleep(5)
                    continue

            # Parse current tunnel URL
            tunnel_display = _tunnel_url or "N/A"
            ssh_host = "N/A"
            ssh_port = "N/A"
            if _tunnel_url:
                parts = _tunnel_url.replace("tcp://", "").split(":")
                if len(parts) == 2:
                    ssh_host = parts[0]
                    ssh_port = parts[1]

            _move_cursor_home()

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

            # Connection status
            if _max_coders > 0:
                conn_display = f"{connections} / {_max_coders} max"
            else:
                conn_display = str(connections)

            # Tunnel status display
            tunnel_stat = _tunnel_status
            if _reconnect_count > 0:
                tunnel_stat += f" (reconnects: {_reconnect_count})"

            # Build the dashboard — pad each line to overwrite previous content
            def pad(s):
                return s.ljust(dash_width)

            lines = [
                pad(""),
                pad("  ============================================================"),
                pad("   WIZ ISLAND - HOST DASHBOARD"),
                pad("  ============================================================"),
                pad(""),
                pad(f"   TUNNEL STATUS    : {tunnel_stat}"),
                pad(f"   ROOM CODE        : {_room_code or 'N/A'}  (share this once)"),
                pad(f"   TUNNEL URL       : {tunnel_display}"),
                pad(f"   SSH Command      : ssh {guest_user}@{ssh_host} -p {ssh_port}"),
                pad(f"   Guest Password   : {guest_pass}"),
                pad(f"   Uptime           : {uptime}"),
                pad(""),
                pad("  ------------------------------------------------------------"),
                pad("   CODERS CONNECTED"),
                pad("  ------------------------------------------------------------"),
                pad(f"   Active Sessions  : {conn_display}"),
                pad(""),
                pad("  ------------------------------------------------------------"),
                pad("   SYSTEM PERFORMANCE"),
                pad("  ------------------------------------------------------------"),
                pad(f"   CPU Usage        : {_progress_bar(cpu_percent)} {cpu_percent:.1f}%"
                    f"  ({cpu_count} cores)"),
                pad(f"   RAM Usage        : {_progress_bar(mem.percent)} {mem.percent:.1f}%"
                    f"  ({mem.used // (1024**2)} / {mem.total // (1024**2)} MB)"),
                pad(f"   RAM Available    : {_format_bytes(mem.available)}"),
                pad(f"   GPU              : {_get_gpu_info()}"),
                pad(""),
                pad("  ------------------------------------------------------------"),
                pad("   STORAGE (Sandbox)"),
                pad("  ------------------------------------------------------------"),
                pad(f"   Total            : {disk['total_gb']} GB"),
                pad(f"   Used             : {_progress_bar(disk['percent'])} "
                    f"{disk['used_gb']} GB ({disk['percent']}%)"),
                pad(f"   Free             : {disk['free_gb']} GB"),
                pad(f"   Mount Path       : {mount_path}"),
                pad(""),
                pad("  ------------------------------------------------------------"),
                pad("   NETWORK"),
                pad("  ------------------------------------------------------------"),
                pad(f"   Upload Rate      : {_format_bytes(send_rate)}/s"),
                pad(f"   Download Rate    : {_format_bytes(recv_rate)}/s"),
                pad(f"   Total Sent       : {_format_bytes(curr_net['bytes_sent'])}"),
                pad(f"   Total Received   : {_format_bytes(curr_net['bytes_recv'])}"),
                pad(""),
                pad("  ============================================================"),
                pad("   Auto-reconnect is ON. Tunnel restarts automatically"),
                pad("   if it expires. Coders must re-run User Mode after."),
                pad("  ============================================================"),
                pad("   Press 'x' then Enter to activate PANIC BUTTON (Ctrl+C also works)"),
                pad("  ============================================================"),
                pad(""),
            ]

            sys.stdout.write("\n".join(lines) + "\n")
            sys.stdout.flush()
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


def stop_tunnel():
    """Terminate the Pinggy tunnel process."""
    global _tunnel_process, _tunnel_url
    with _lock:
        if _tunnel_process:
            try:
                _tunnel_process.terminate()
                _tunnel_process.wait(timeout=10)
                logger.info("Tunnel process terminated.")
            except subprocess.TimeoutExpired:
                _tunnel_process.kill()
                logger.warning("Tunnel process killed forcefully.")
            except Exception as exc:
                logger.error("Error stopping tunnel: %s", exc)
            finally:
                _tunnel_process = None
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

    print("  [1/4] Stopping tunnel...")
    stop_tunnel()
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
    global _running, _max_coders, _room_code

    # Install signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    print("\n  ============================================================")
    print("   WIZ ISLAND - HOST MODE SETUP")
    print("  ============================================================")

    # Step 0: Optional custom guest username
    default_user = ("WizGuest" if platform.system() == "Windows" else "wizguest")
    try:
        custom_user = input(
            f"\n  Guest username (press Enter for '{default_user}'): "
        ).strip()
        if custom_user:
            if not custom_user.isalnum():
                print("  [WARNING] Username should be alphanumeric. Using default.")
                custom_user = ""
            elif len(custom_user) > 20:
                print("  [WARNING] Username too long. Using default.")
                custom_user = ""
        if custom_user:
            storage.set_guest_username(custom_user)
            print(f"  Guest username set to: {custom_user}")
        else:
            print(f"  Using default: {default_user}")
    except (EOFError, KeyboardInterrupt):
        print(f"\n  Using default: {default_user}")

    # Max coders prompt
    try:
        max_input = input(
            "\n  Max coders allowed (press Enter for unlimited): "
        ).strip()
        if max_input:
            _max_coders = max(1, int(max_input))
            print(f"  Max coders set to: {_max_coders}")
        else:
            _max_coders = 0
            print("  No limit — unlimited coders can connect.")
    except (ValueError, EOFError, KeyboardInterrupt):
        _max_coders = 0
        print("  No limit — unlimited coders can connect.")

    # Generate a room code for automatic tunnel URL discovery via ntfy.sh
    _room_code = _generate_room_code()

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

    # Step 2: Start tunnel
    tunnel_url = start_pinggy_tunnel()
    if not tunnel_url:
        print("  [ERROR] Could not establish tunnel.")
        input("\n  Press Enter to return to the menu...")
        return

    # Display connection details prominently for sharing
    guest_user, guest_pass = storage.get_guest_credentials()
    print()
    print("  ============================================================")
    print("   TUNNEL ESTABLISHED - SHARE THESE WITH YOUR GUEST")
    print("  ============================================================")
    print(f"   ROOM CODE      : {_room_code}")
    print("     ^ Share this ONCE. Guest enters it in User Mode and stays")
    print("       connected automatically across tunnel reconnects.")
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
