"""
WIZ ISLAND - Core CLI Entrypoint (main.py)

Interactive menu-driven CLI for the Wiz Island peer-to-peer
SSH tunneling tool. Supports Host Mode, User Mode, and
Panic/Terminate operations.
"""

import argparse
import ctypes
import logging
import os
import platform
import signal
import sys

# Add parent directory to path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import host
from src import client
from src import storage

# ============================================================
#  VERSION
# ============================================================

__version__ = "1.3.0"

# ============================================================
#  LOGGING CONFIGURATION
# ============================================================

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "wiz_island.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a"),
        logging.StreamHandler(sys.stdout),
    ],
)

# Suppress verbose output to console; keep DEBUG in file only
for handler in logging.root.handlers:
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
        handler.setLevel(logging.WARNING)

logger = logging.getLogger("wiz_island.main")


# ============================================================
#  TERMINAL UI / COLORS
# ============================================================

def _supports_color():
    """Enable ANSI colors where possible; return True if usable."""
    if not sys.stdout.isatty():
        return False
    if platform.system() == "Windows":
        # Enable VT100 processing on Windows 10+ consoles
        try:
            kernel32 = ctypes.windll.kernel32
            # -11 = STD_OUTPUT_HANDLE, 0x0004 = ENABLE_VIRTUAL_TERMINAL_PROCESSING
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
            return True
        except Exception:
            return False
    return True


_COLOR = _supports_color()


class C:
    """ANSI color codes (empty strings when color is unsupported)."""
    RESET = "\033[0m" if _COLOR else ""
    BOLD = "\033[1m" if _COLOR else ""
    DIM = "\033[2m" if _COLOR else ""
    CYAN = "\033[96m" if _COLOR else ""
    BLUE = "\033[94m" if _COLOR else ""
    GREEN = "\033[92m" if _COLOR else ""
    YELLOW = "\033[93m" if _COLOR else ""
    RED = "\033[91m" if _COLOR else ""
    MAGENTA = "\033[95m" if _COLOR else ""


def colorize(text, color):
    """Wrap text in a color code with reset."""
    return f"{color}{text}{C.RESET}"


# ============================================================
#  PRIVILEGE CHECKS
# ============================================================

def is_admin():
    """Check if the current process has administrator/root privileges."""
    try:
        if platform.system() == "Windows":
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except AttributeError:
        return False
    except Exception:
        return False


def warn_if_not_admin():
    """Print a warning if not running with elevated privileges."""
    if not is_admin():
        print()
        print("  ============================================================")
        print("   WARNING: Not running with Administrator/root privileges!")
        print("  ============================================================")
        print("   Host Mode requires elevated privileges to:")
        print("   - Create virtual disks (diskpart / dd)")
        print("   - Create guest user accounts")
        print("   - Modify SSH server configuration")
        print("   - Configure firewall rules")
        print()
        print("   On Windows: Right-click setup.bat -> Run as Administrator")
        print("   On Linux:   sudo python3 src/main.py")
        print("  ============================================================")
        print()
        return True
    return False


# ============================================================
#  BANNER & UI HELPERS
# ============================================================

BANNER_ART = r"""
   __        ___       ___     _                 _
   \ \      / (_)__   |_ _|__| | __ _ _ __   __| |
    \ \ /\ / /| |_ /   | |/ _` |/ _` | '_ \ / _` |
     \ V  V / | |/ /    | | (_| | (_| | | | | (_| |
      \_/\_/  |_/___|  |___\__,_|\__,_|_| |_|\__,_|
"""

_TOP = "  +" + "-" * 58 + "+"


def clear_screen():
    """Clear terminal screen cross-platform."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def print_banner():
    """Display the application banner."""
    plat_name = f"{platform.system()} {platform.release()}"
    is_adm = is_admin()
    priv = "Administrator" if is_adm else "Standard User"
    priv_color = C.GREEN if is_adm else C.YELLOW

    print()
    print(colorize(_TOP, C.CYAN))
    print(colorize(BANNER_ART.strip("\n"), C.BOLD + C.CYAN))
    print()
    print("   " + colorize("Serverless P2P SSH Tunneling Tool", C.BOLD)
          + "  " + colorize(f"v{__version__}", C.MAGENTA))
    print("   " + colorize("Platform   : ", C.DIM) + plat_name)
    print("   " + colorize("Privileges : ", C.DIM) + colorize(priv, priv_color))
    print(colorize(_TOP, C.CYAN))


def print_menu():
    """Display the main menu."""
    print()
    print("   " + colorize("MAIN MENU", C.BOLD + C.BLUE))
    print(colorize("  " + "-" * 58, C.DIM))
    print()
    print("   " + colorize("[1]", C.GREEN) + "  "
          + colorize("HOST MODE", C.BOLD) + "   - Share your machine's resources")
    print("   " + colorize("[2]", C.GREEN) + "  "
          + colorize("USER MODE", C.BOLD) + "   - Connect to a remote host")
    print("   " + colorize("[3]", C.YELLOW) + "  "
          + colorize("TERMINATE", C.BOLD) + "   - Panic button / Full cleanup")
    print()
    print("   " + colorize("[0]", C.RED) + "  "
          + colorize("EXIT", C.BOLD))
    print()
    print(colorize("  " + "-" * 58, C.DIM))


def get_choice():
    """Get a valid menu choice from the user."""
    while True:
        try:
            choice = input("\n   " + colorize("Select an option [0-3]: ", C.BOLD + C.CYAN)).strip()
            if choice in ("0", "1", "2", "3"):
                return choice
            print(colorize("   Invalid choice. Please enter 0, 1, 2, or 3.", C.RED))
        except (EOFError, KeyboardInterrupt):
            print("\n   Exiting Wiz Island...")
            sys.exit(0)


def graceful_exit(signum, frame):
    """Handle SIGINT/SIGTERM for graceful exit from the menu."""
    print("\n\n  Exiting Wiz Island...")
    logger.info("Received signal %d, exiting.", signum)
    sys.exit(0)


# ============================================================
#  CLI ARGUMENT PARSING
# ============================================================

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="wiz-island",
        description="Wiz Island - Serverless P2P SSH Tunneling Tool",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Wiz Island v{__version__}",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["host", "user", "terminate"],
        help="Launch directly into a specific mode (skip the menu).",
    )
    return parser.parse_args()


# ============================================================
#  MAIN ENTRY POINT
# ============================================================

def main():
    """Main application loop."""
    args = parse_args()

    # Install signal handlers for graceful exit
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    logger.info("Wiz Island v%s started on %s.", __version__, platform.system())

    # Direct mode launch via CLI args
    if args.mode:
        if args.mode == "host":
            if warn_if_not_admin():
                confirm = input("  Continue anyway? (yes/no): ").strip().lower()
                if confirm not in ("yes", "y"):
                    sys.exit(0)
            host.run_host_mode()
            sys.exit(0)
        elif args.mode == "user":
            client.run_user_mode()
            sys.exit(0)
        elif args.mode == "terminate":
            host.panic_shutdown()
            sys.exit(0)

    # Interactive menu loop
    while True:
        clear_screen()
        print_banner()
        print_menu()

        choice = get_choice()

        if choice == "0":
            clear_screen()
            print("\n  Goodbye! Thanks for using Wiz Island.\n")
            logger.info("User exited normally.")
            sys.exit(0)

        elif choice == "1":
            logger.info("User selected Host Mode.")
            if warn_if_not_admin():
                confirm = input("  Continue anyway? (yes/no): ").strip().lower()
                if confirm not in ("yes", "y"):
                    continue
            try:
                host.run_host_mode()
            except KeyboardInterrupt:
                print("\n  Host mode interrupted.")
                logger.info("Host mode interrupted by user.")
            except Exception as exc:
                logger.exception("Host mode error: %s", exc)
                print(f"\n  [ERROR] Host mode encountered an error: {exc}")
                print("  Check logs/wiz_island.log for details.")
                input("\n  Press Enter to return to the menu...")

        elif choice == "2":
            logger.info("User selected User Mode.")
            try:
                client.run_user_mode()
            except KeyboardInterrupt:
                print("\n  User mode interrupted.")
                logger.info("User mode interrupted by user.")
            except Exception as exc:
                logger.exception("User mode error: %s", exc)
                print(f"\n  [ERROR] User mode encountered an error: {exc}")
                print("  Check logs/wiz_island.log for details.")
                input("\n  Press Enter to return to the menu...")

        elif choice == "3":
            logger.info("User selected Terminate / Panic Button.")
            print("\n  ============================================================")
            print("   TERMINATE / PANIC BUTTON")
            print("  ============================================================")
            print()
            print("   This will:")
            print("   - Stop the tunnel")
            print("   - Kill all guest SSH sessions")
            print("   - Unmount the virtual disk (data is KEPT by default)")
            print("   - Delete guest user accounts")
            print("   - Restore machine to native state")
            print()
            confirm = input("  Are you sure you want to terminate? (yes/no): ").strip().lower()
            if confirm in ("yes", "y"):
                wipe_confirm = input(
                    "  Also PERMANENTLY DELETE all sandbox data? (yes/no, default no): "
                ).strip().lower()
                wipe_data = wipe_confirm in ("yes", "y")
                if not wipe_data:
                    print("  Sandbox data will be preserved for next time.")
                try:
                    host.panic_shutdown(wipe_data=wipe_data)
                except Exception as exc:
                    logger.exception("Panic shutdown error: %s", exc)
                    print(f"\n  [ERROR] Shutdown error: {exc}")
                    print("  Check logs/wiz_island.log for details.")
                    input("\n  Press Enter to continue...")
            else:
                print("  Cancelled.")
                input("  Press Enter to return to the menu...")


if __name__ == "__main__":
    main()
