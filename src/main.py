"""
WIZ ISLAND - Core CLI Entrypoint (main.py)

Interactive menu-driven CLI for the Wiz Island peer-to-peer
SSH tunneling tool. Supports Host Mode, User Mode, and
Panic/Terminate operations.
"""

import logging
import os
import platform
import sys

# Add parent directory to path so we can import the package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import host
from src import client
from src import storage

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
#  BANNER & UI HELPERS
# ============================================================

BANNER = r"""
  ============================================================

   __        ___       ___     _                 _
   \ \      / (_)__   |_ _|__| | __ _ _ __   __| |
    \ \ /\ / /| |_ /   | |/ _` |/ _` | '_ \ / _` |
     \ V  V / | |/ /    | | (_| | (_| | | | | (_| |
      \_/\_/  |_/___|  |___\__,_|\__,_|_| |_|\__,_|

   Serverless P2P SSH Tunneling Tool
   Platform: {platform}

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
    print(BANNER.format(platform=plat_name))


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


# ============================================================
#  MAIN ENTRY POINT
# ============================================================

def main():
    """Main application loop."""
    logger.info("Wiz Island started on %s.", platform.system())

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
            try:
                host.run_host_mode()
            except KeyboardInterrupt:
                print("\n  Host mode interrupted.")
                logger.info("Host mode interrupted by user.")
            except Exception as exc:
                logger.exception("Host mode error: %s", exc)
                print(f"\n  [ERROR] Host mode encountered an error: {exc}")
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
                input("\n  Press Enter to return to the menu...")

        elif choice == "3":
            logger.info("User selected Terminate / Panic Button.")
            print("\n  ============================================================")
            print("   TERMINATE / PANIC BUTTON")
            print("  ============================================================")
            confirm = input("\n  Are you sure you want to terminate? (yes/no): ").strip().lower()
            if confirm in ("yes", "y"):
                try:
                    host.panic_shutdown()
                except Exception as exc:
                    logger.exception("Panic shutdown error: %s", exc)
                    print(f"\n  [ERROR] Shutdown error: {exc}")
                    input("\n  Press Enter to continue...")
            else:
                print("  Cancelled.")
                input("  Press Enter to return to the menu...")


if __name__ == "__main__":
    main()
