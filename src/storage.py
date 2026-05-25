"""
WIZ ISLAND - Platform-Specific Storage Virtualization (storage.py)

Handles creation of virtual disk images, formatting, mounting,
user account creation, and SSH jail configuration on both
Windows and Linux platforms.
"""

import logging
import os
import platform
import subprocess
import shutil

logger = logging.getLogger("wiz_island.storage")

WINDOWS_GUEST_USER = "WizGuest"
WINDOWS_GUEST_PASS = "W!zGu3st2024#"
WINDOWS_MOUNT_DRIVE = "X:"
WINDOWS_VHDX_PATH = r"C:\WizIsland\sandbox.vhdx"
WINDOWS_SSHD_CONFIG = r"C:\ProgramData\ssh\sshd_config"

LINUX_GUEST_USER = "wizguest"
LINUX_GUEST_PASS = "wizguest2024"
LINUX_MOUNT_DIR = "/mnt/wizsandbox"
LINUX_IMAGE_PATH = "/opt/wiz_island/sandbox.img"


def get_platform():
    """Return 'windows' or 'linux' based on the current OS."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


def run_command(cmd, description="command", shell=True, check=True):
    """Execute a system command with detailed error handling and logging."""
    logger.info("Running %s: %s", description, cmd if isinstance(cmd, str) else " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.stdout.strip():
            logger.debug("[stdout] %s", result.stdout.strip())
        if result.stderr.strip():
            logger.debug("[stderr] %s", result.stderr.strip())
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )
        return result
    except subprocess.TimeoutExpired:
        logger.error("[%s] Command timed out after 300 seconds.", description)
        raise
    except subprocess.CalledProcessError as exc:
        logger.error(
            "[%s] Command failed (exit code %d).\n  stdout: %s\n  stderr: %s",
            description, exc.returncode,
            exc.stdout.strip() if exc.stdout else "",
            exc.stderr.strip() if exc.stderr else "",
        )
        raise
    except FileNotFoundError:
        logger.error("[%s] Command not found: %s", description, cmd)
        raise
    except Exception as exc:
        logger.error("[%s] Unexpected error: %s", description, exc)
        raise


# ============================================================
#  WINDOWS STORAGE OPERATIONS
# ============================================================

def windows_create_vhdx(size_gb):
    """Create an expandable VHDX file using diskpart."""
    vhdx_dir = os.path.dirname(WINDOWS_VHDX_PATH)
    try:
        os.makedirs(vhdx_dir, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create directory %s: %s", vhdx_dir, exc)
        raise

    size_mb = size_gb * 1024
    diskpart_script = (
        f"create vdisk file=\"{WINDOWS_VHDX_PATH}\" "
        f"maximum={size_mb} type=expandable\n"
        f"select vdisk file=\"{WINDOWS_VHDX_PATH}\"\n"
        "attach vdisk\n"
        "create partition primary\n"
        "format fs=ntfs label=\"WizSandbox\" quick\n"
        f"assign letter={WINDOWS_MOUNT_DRIVE[0]}\n"
        "exit\n"
    )

    script_path = os.path.join(vhdx_dir, "diskpart_create.txt")
    try:
        with open(script_path, "w") as f:
            f.write(diskpart_script)
        logger.info("Created diskpart script at %s", script_path)
    except IOError as exc:
        logger.error("Failed to write diskpart script: %s", exc)
        raise

    try:
        run_command(
            f"diskpart /s \"{script_path}\"",
            description="diskpart create VHDX",
        )
        logger.info(
            "VHDX created and mounted: %s (%d GB) -> %s",
            WINDOWS_VHDX_PATH, size_gb, WINDOWS_MOUNT_DRIVE,
        )
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


def windows_create_guest_user():
    """Create a standard local user 'WizGuest' on Windows."""
    try:
        result = run_command(
            f'net user {WINDOWS_GUEST_USER}',
            description="check WizGuest user",
            check=False,
        )
        if result.returncode == 0:
            logger.info("User '%s' already exists.", WINDOWS_GUEST_USER)
            return
    except Exception as exc:
        logger.warning("Could not check user existence: %s", exc)

    try:
        run_command(
            f'net user {WINDOWS_GUEST_USER} {WINDOWS_GUEST_PASS} /add /active:yes '
            f'/comment:"Wiz Island Guest Account" /passwordchg:no',
            description="create WizGuest user",
        )
        logger.info("Created user '%s'.", WINDOWS_GUEST_USER)
    except Exception as exc:
        logger.error("Failed to create user '%s': %s", WINDOWS_GUEST_USER, exc)
        raise


def windows_set_permissions():
    """Restrict X:\\ access so only WizGuest can use it."""
    try:
        run_command(
            f'icacls {WINDOWS_MOUNT_DRIVE}\\ /inheritance:r',
            description="icacls remove inheritance",
        )
        run_command(
            f'icacls {WINDOWS_MOUNT_DRIVE}\\ /grant {WINDOWS_GUEST_USER}:(OI)(CI)F',
            description="icacls grant WizGuest full control",
        )
        run_command(
            f'icacls {WINDOWS_MOUNT_DRIVE}\\ /grant Administrators:(OI)(CI)F',
            description="icacls grant Administrators full control",
        )
        logger.info("Permissions set on %s for %s.", WINDOWS_MOUNT_DRIVE, WINDOWS_GUEST_USER)
    except Exception as exc:
        logger.error("Failed to set permissions on %s: %s", WINDOWS_MOUNT_DRIVE, exc)
        raise


def windows_configure_ssh_jail():
    """Append a Match User block to sshd_config to jail WizGuest into X:\\."""
    match_block = (
        f"\n\n# --- Wiz Island SSH Jail ---\n"
        f"Match User {WINDOWS_GUEST_USER}\n"
        f'    ForceCommand cmd.exe /k "cd /d {WINDOWS_MOUNT_DRIVE}\\"\n'
    )

    try:
        existing = ""
        if os.path.exists(WINDOWS_SSHD_CONFIG):
            with open(WINDOWS_SSHD_CONFIG, "r") as f:
                existing = f.read()

        if f"Match User {WINDOWS_GUEST_USER}" in existing:
            logger.info("SSH jail block already exists in sshd_config.")
            return

        with open(WINDOWS_SSHD_CONFIG, "a") as f:
            f.write(match_block)
        logger.info("Appended SSH jail block for '%s' to sshd_config.", WINDOWS_GUEST_USER)

        run_command(
            "net stop sshd && net start sshd",
            description="restart sshd service",
        )
    except IOError as exc:
        logger.error("Failed to modify sshd_config: %s", exc)
        raise
    except Exception as exc:
        logger.error("Failed to restart SSH service: %s", exc)
        raise


def windows_setup_storage(size_gb):
    """Full Windows storage setup pipeline."""
    print(f"  [1/4] Creating {size_gb} GB VHDX virtual disk...")
    windows_create_vhdx(size_gb)

    print(f"  [2/4] Creating guest user '{WINDOWS_GUEST_USER}'...")
    windows_create_guest_user()

    print(f"  [3/4] Setting permissions on {WINDOWS_MOUNT_DRIVE}...")
    windows_set_permissions()

    print("  [4/4] Configuring SSH jail...")
    windows_configure_ssh_jail()

    print("  Storage setup complete.")


# ============================================================
#  WINDOWS TEARDOWN OPERATIONS
# ============================================================

def windows_teardown():
    """Remove virtual disk, guest user, and SSH jail config on Windows."""
    print("  [*] Tearing down Windows sandbox...")

    # Detach VHDX
    try:
        vhdx_dir = os.path.dirname(WINDOWS_VHDX_PATH)
        os.makedirs(vhdx_dir, exist_ok=True)
        script_path = os.path.join(vhdx_dir, "diskpart_detach.txt")
        with open(script_path, "w") as f:
            f.write(
                f"select vdisk file=\"{WINDOWS_VHDX_PATH}\"\n"
                "detach vdisk\n"
                "exit\n"
            )
        run_command(
            f"diskpart /s \"{script_path}\"",
            description="diskpart detach VHDX",
        )
        os.remove(script_path)
    except Exception as exc:
        logger.warning("VHDX detach issue: %s", exc)

    # Delete VHDX file
    try:
        if os.path.exists(WINDOWS_VHDX_PATH):
            os.remove(WINDOWS_VHDX_PATH)
            logger.info("Deleted VHDX file: %s", WINDOWS_VHDX_PATH)
    except OSError as exc:
        logger.warning("Could not delete VHDX: %s", exc)

    # Delete guest user
    try:
        run_command(
            f"net user {WINDOWS_GUEST_USER} /delete",
            description="delete WizGuest user",
            check=False,
        )
        logger.info("Deleted user '%s'.", WINDOWS_GUEST_USER)
    except Exception as exc:
        logger.warning("Could not delete user: %s", exc)

    # Remove SSH jail config
    try:
        if os.path.exists(WINDOWS_SSHD_CONFIG):
            with open(WINDOWS_SSHD_CONFIG, "r") as f:
                lines = f.read()
            marker = "# --- Wiz Island SSH Jail ---"
            if marker in lines:
                cleaned = lines[:lines.index(marker)].rstrip() + "\n"
                with open(WINDOWS_SSHD_CONFIG, "w") as f:
                    f.write(cleaned)
                logger.info("Removed SSH jail block from sshd_config.")
                run_command("net stop sshd && net start sshd",
                            description="restart sshd", check=False)
    except Exception as exc:
        logger.warning("Could not clean sshd_config: %s", exc)

    print("  Teardown complete.")


# ============================================================
#  LINUX STORAGE OPERATIONS
# ============================================================

def linux_create_image(size_gb):
    """Create an empty disk image file using dd and format it as EXT4."""
    image_dir = os.path.dirname(LINUX_IMAGE_PATH)
    try:
        os.makedirs(image_dir, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create directory %s: %s", image_dir, exc)
        raise

    # Use fallocate if available, fallback to dd
    fallocate_path = shutil.which("fallocate")
    if fallocate_path:
        try:
            run_command(
                f"fallocate -l {size_gb}G \"{LINUX_IMAGE_PATH}\"",
                description="fallocate disk image",
            )
        except Exception:
            logger.warning("fallocate failed, falling back to dd.")
            run_command(
                f"dd if=/dev/zero of=\"{LINUX_IMAGE_PATH}\" bs=1M count={size_gb * 1024} status=progress",
                description="dd create disk image",
            )
    else:
        try:
            run_command(
                f"dd if=/dev/zero of=\"{LINUX_IMAGE_PATH}\" bs=1M count={size_gb * 1024} status=progress",
                description="dd create disk image",
            )
        except Exception as exc:
            logger.error("Failed to create disk image: %s", exc)
            raise

    # Format as EXT4
    try:
        run_command(
            f"mkfs.ext4 -F \"{LINUX_IMAGE_PATH}\"",
            description="format image as EXT4",
        )
        logger.info("Disk image created and formatted: %s (%d GB)", LINUX_IMAGE_PATH, size_gb)
    except Exception as exc:
        logger.error("Failed to format image as EXT4: %s", exc)
        raise


def linux_mount_image():
    """Loop-mount the disk image to the sandbox directory."""
    try:
        os.makedirs(LINUX_MOUNT_DIR, exist_ok=True)
    except OSError as exc:
        logger.error("Failed to create mount directory %s: %s", LINUX_MOUNT_DIR, exc)
        raise

    try:
        run_command(
            f"mount -o loop \"{LINUX_IMAGE_PATH}\" \"{LINUX_MOUNT_DIR}\"",
            description="loop-mount disk image",
        )
        logger.info("Mounted %s at %s", LINUX_IMAGE_PATH, LINUX_MOUNT_DIR)
    except Exception as exc:
        logger.error("Failed to mount image: %s", exc)
        raise


def linux_create_guest_user():
    """Create a dedicated system user 'wizguest' with no sudo privileges."""
    try:
        result = run_command(
            f"id {LINUX_GUEST_USER}",
            description="check wizguest user",
            check=False,
        )
        if result.returncode == 0:
            logger.info("User '%s' already exists.", LINUX_GUEST_USER)
            return
    except Exception as exc:
        logger.warning("Could not check user existence: %s", exc)

    try:
        run_command(
            f"useradd -m -s /bin/bash -d \"{LINUX_MOUNT_DIR}\" {LINUX_GUEST_USER}",
            description="create wizguest user",
        )
        run_command(
            f"echo '{LINUX_GUEST_USER}:{LINUX_GUEST_PASS}' | chpasswd",
            description="set wizguest password",
        )
        logger.info("Created user '%s' with home at %s.", LINUX_GUEST_USER, LINUX_MOUNT_DIR)
    except Exception as exc:
        logger.error("Failed to create user '%s': %s", LINUX_GUEST_USER, exc)
        raise


def linux_set_permissions():
    """Restrict ownership of /mnt/wizsandbox to the wizguest user."""
    try:
        run_command(
            f"chown -R {LINUX_GUEST_USER}:{LINUX_GUEST_USER} \"{LINUX_MOUNT_DIR}\"",
            description="chown sandbox directory",
        )
        run_command(
            f"chmod 700 \"{LINUX_MOUNT_DIR}\"",
            description="chmod sandbox directory",
        )
        logger.info("Permissions set on %s for %s.", LINUX_MOUNT_DIR, LINUX_GUEST_USER)
    except Exception as exc:
        logger.error("Failed to set permissions: %s", exc)
        raise


def linux_configure_ssh_jail():
    """Append a Match User block to sshd_config to jail wizguest."""
    sshd_config = "/etc/ssh/sshd_config"
    match_block = (
        f"\n\n# --- Wiz Island SSH Jail ---\n"
        f"Match User {LINUX_GUEST_USER}\n"
        f"    ChrootDirectory {LINUX_MOUNT_DIR}\n"
        f"    ForceCommand internal-sftp\n"
        f"    AllowTcpForwarding no\n"
        f"    X11Forwarding no\n"
    )

    try:
        existing = ""
        if os.path.exists(sshd_config):
            with open(sshd_config, "r") as f:
                existing = f.read()

        if f"Match User {LINUX_GUEST_USER}" in existing:
            logger.info("SSH jail block already exists in sshd_config.")
            return

        with open(sshd_config, "a") as f:
            f.write(match_block)
        logger.info("Appended SSH jail block for '%s' to sshd_config.", LINUX_GUEST_USER)

        run_command(
            "systemctl restart sshd",
            description="restart sshd service",
        )
    except IOError as exc:
        logger.error("Failed to modify sshd_config: %s", exc)
        raise
    except Exception as exc:
        logger.error("Failed to restart SSH service: %s", exc)
        raise


def linux_setup_storage(size_gb):
    """Full Linux storage setup pipeline."""
    print(f"  [1/5] Creating {size_gb} GB disk image...")
    linux_create_image(size_gb)

    print(f"  [2/5] Mounting image at {LINUX_MOUNT_DIR}...")
    linux_mount_image()

    print(f"  [3/5] Creating guest user '{LINUX_GUEST_USER}'...")
    linux_create_guest_user()

    print(f"  [4/5] Setting permissions on {LINUX_MOUNT_DIR}...")
    linux_set_permissions()

    print("  [5/5] Configuring SSH jail...")
    linux_configure_ssh_jail()

    print("  Storage setup complete.")


# ============================================================
#  LINUX TEARDOWN OPERATIONS
# ============================================================

def linux_teardown():
    """Remove disk image, guest user, and SSH jail config on Linux."""
    print("  [*] Tearing down Linux sandbox...")

    # Unmount
    try:
        run_command(
            f"umount \"{LINUX_MOUNT_DIR}\"",
            description="unmount sandbox",
            check=False,
        )
        logger.info("Unmounted %s.", LINUX_MOUNT_DIR)
    except Exception as exc:
        logger.warning("Unmount issue: %s", exc)

    # Delete image file
    try:
        if os.path.exists(LINUX_IMAGE_PATH):
            os.remove(LINUX_IMAGE_PATH)
            logger.info("Deleted image file: %s", LINUX_IMAGE_PATH)
    except OSError as exc:
        logger.warning("Could not delete image: %s", exc)

    # Remove mount directory
    try:
        if os.path.exists(LINUX_MOUNT_DIR):
            os.rmdir(LINUX_MOUNT_DIR)
            logger.info("Removed mount directory: %s", LINUX_MOUNT_DIR)
    except OSError as exc:
        logger.warning("Could not remove mount dir: %s", exc)

    # Delete guest user
    try:
        run_command(
            f"userdel -r {LINUX_GUEST_USER}",
            description="delete wizguest user",
            check=False,
        )
        logger.info("Deleted user '%s'.", LINUX_GUEST_USER)
    except Exception as exc:
        logger.warning("Could not delete user: %s", exc)

    # Remove SSH jail config
    sshd_config = "/etc/ssh/sshd_config"
    try:
        if os.path.exists(sshd_config):
            with open(sshd_config, "r") as f:
                lines = f.read()
            marker = "# --- Wiz Island SSH Jail ---"
            if marker in lines:
                cleaned = lines[:lines.index(marker)].rstrip() + "\n"
                with open(sshd_config, "w") as f:
                    f.write(cleaned)
                logger.info("Removed SSH jail block from sshd_config.")
                run_command("systemctl restart sshd",
                            description="restart sshd", check=False)
    except Exception as exc:
        logger.warning("Could not clean sshd_config: %s", exc)

    print("  Teardown complete.")


# ============================================================
#  PUBLIC INTERFACE
# ============================================================

def setup_storage(size_gb):
    """Set up storage on the current platform."""
    plat = get_platform()
    if plat == "windows":
        windows_setup_storage(size_gb)
    else:
        linux_setup_storage(size_gb)


def teardown_storage():
    """Tear down storage on the current platform."""
    plat = get_platform()
    if plat == "windows":
        windows_teardown()
    else:
        linux_teardown()


def get_mount_path():
    """Return the mount path for the current platform."""
    plat = get_platform()
    if plat == "windows":
        return WINDOWS_MOUNT_DRIVE + "\\"
    else:
        return LINUX_MOUNT_DIR


def get_guest_credentials():
    """Return (username, password) for the guest account on the current platform."""
    plat = get_platform()
    if plat == "windows":
        return WINDOWS_GUEST_USER, WINDOWS_GUEST_PASS
    else:
        return LINUX_GUEST_USER, LINUX_GUEST_PASS
