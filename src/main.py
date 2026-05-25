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

__version__ = "1.1.0"

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

BANNER = r"""
  ============================================================

   __        ___       ___     _                 _
   \ \      / (_)__   |_ _|__| | __ _ _ __   __| |
    \ \ /\ / /| |_ /   | |/ _` |/ _` | '_ \ / _` |
     \ V  V / | |/ /    | | (_| | (_| | | | | (_| |
      \_/\_/  |_/___|  |___\__,_|\__,_|_| |_|\__,_|

   Serverless P2P SSH Tunneling Tool  v{version}
   Platform: {platform}
   Privileges: {privileges}

  ============================================================
"""

MENU = """
  ------------------------------------------------------------
   MAIN MENU
  ------------------------------------------------------------

   [1]  HOST MODE     - Share your machine's resources
   [2]  USER MODE     - Connect to a remote host
   [3]  TERMINATE     - Panic button / Full cleanup

   [0]  EXIT

  ------------------------------------------------------------
"""


def clear_screen():
    """Clear terminal screen cross-platform."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def print_banner():
    """Display the application banner."""
    plat_name = f"{platform.system()} {platform.release()}"
    priv = "Administrator" if is_admin() else "Standard User"
    print(BANNER.format(version=__version__, platform=plat_name, privileges=priv))


def print_menu():
    """Display the main menu."""
    print(MENU)


def get_choice():
    """Get a valid menu choice from the user."""
    while True:
        try:
            choice = input("   Select an option [0-3]: ").strip()
            if choice in ("0", "1", "2", "3"):
                return choice
            print("   Invalid choice. Please enter 0, 1, 2, or 3.")
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
            print("   - Unmount virtual disks")
            print("   - Delete guest user accounts")
            print("   - Restore machine to native state")
            print()
            confirm = input("  Are you sure you want to terminate? (yes/no): ").strip().lower()
            if confirm in ("yes", "y"):
                try:
                    host.panic_shutdown()
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
