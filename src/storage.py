"""
WIZ ISLAND - Platform-Specific Storage Virtualization (storage.py)

Handles creation of virtual disk images, formatting, mounting,
user account creation, and SSH jail configuration on both
Windows and Linux platforms.
"""

import logging
import os
import platform
import random
import string
import subprocess
import shutil
import time

logger = logging.getLogger("wiz_island.storage")

# ============================================================
#  CONFIGURATION CONSTANTS
# ============================================================

WINDOWS_GUEST_USER = "WizGuest"
WINDOWS_MOUNT_DRIVE = "X:"
WINDOWS_VHDX_PATH = r"C:\WizIsland\sandbox.vhdx"
WINDOWS_SSHD_CONFIG = r"C:\ProgramData\ssh\sshd_config"

LINUX_GUEST_USER = "wizguest"
LINUX_MOUNT_DIR = "/mnt/wizsandbox"
LINUX_IMAGE_PATH = "/opt/wiz_island/sandbox.img"


def set_guest_username(username):
    """Override the default guest username for this session."""
    global WINDOWS_GUEST_USER, LINUX_GUEST_USER
    plat = platform.system()
    if plat == "Windows":
        WINDOWS_GUEST_USER = username
    else:
        LINUX_GUEST_USER = username.lower()
    logger.info("Guest username set to: %s", username)

# Dynamically generated passwords (set during setup, persisted in memory)
_guest_password = None


def _generate_password(length=16):
    """Generate a secure random password."""
    chars = string.ascii_letters + string.digits + "!@#*_+-="
    password = "".join(random.SystemRandom().choice(chars) for _ in range(length))
    return password


def _get_or_create_password():
    """Return the current session password, generating one if needed."""
    global _guest_password
    if _guest_password is None:
        _guest_password = _generate_password()
        logger.info("Generated new guest password for this session.")
    return _guest_password


def _set_password(password):
    """Manually set the guest password (used during testing or override)."""
    global _guest_password
    _guest_password = password


# ============================================================
#  PLATFORM DETECTION
# ============================================================

def get_platform():
    """Return 'windows' or 'linux' based on the current OS."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")


# ============================================================
#  COMMAND EXECUTION
# ============================================================

def run_command(cmd, description="command", shell=True, check=True):
    """Execute a system command with detailed error handling and logging.

    All system commands (diskpart, icacls, net user, dd, mount, useradd, etc.)
    are routed through this function so they are uniformly wrapped in
    try-except error handling with detailed log reporting.
    """
    logger.info("Running %s: %s", description, cmd if isinstance(cmd, str) else " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=600,
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
        logger.error("[%s] Command timed out after 600 seconds.", description)
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
    except OSError as exc:
        logger.error("[%s] OS error executing command: %s", description, exc)
        raise
    except Exception as exc:
        logger.error("[%s] Unexpected error: %s", description, exc)
        raise


# ============================================================
#  VALIDATION HELPERS
# ============================================================

def validate_disk_space(size_gb, path):
    """Verify there is enough free disk space at the given path."""
    try:
        stat = os.statvfs(path) if hasattr(os, "statvfs") else None
        if stat:
            free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
            if free_gb < size_gb:
                raise RuntimeError(
                    f"Insufficient disk space at {path}: "
                    f"{free_gb:.1f} GB free, {size_gb} GB required."
                )
            logger.info("Disk space check passed: %.1f GB free at %s", free_gb, path)
        else:
            # Windows fallback — use shutil
            total, used, free = shutil.disk_usage(path)
            free_gb = free / (1024 ** 3)
            if free_gb < size_gb:
                raise RuntimeError(
                    f"Insufficient disk space at {path}: "
                    f"{free_gb:.1f} GB free, {size_gb} GB required."
                )
            logger.info("Disk space check passed: %.1f GB free at %s", free_gb, path)
    except RuntimeError:
        raise
    except Exception as exc:
        logger.warning("Could not validate disk space: %s (proceeding anyway)", exc)


def check_existing_setup():
    """Check if a previous Wiz Island setup exists and warn the user."""
    plat = get_platform()
    if plat == "windows":
        if os.path.exists(WINDOWS_VHDX_PATH):
            return True
    else:
        if os.path.exists(LINUX_IMAGE_PATH):
            return True
    return False


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

    validate_disk_space(size_gb, vhdx_dir)

    if os.path.exists(WINDOWS_VHDX_PATH):
        logger.warning("VHDX already exists at %s. Reusing existing disk.", WINDOWS_VHDX_PATH)

        # If the drive letter is already accessible, nothing to do
        if os.path.isdir(WINDOWS_MOUNT_DRIVE + "\\"):
            logger.info("Drive %s is already accessible.", WINDOWS_MOUNT_DRIVE)
            return

        script_path = os.path.join(vhdx_dir, "diskpart_attach.txt")
        drive_letter = WINDOWS_MOUNT_DRIVE[0]

        # Step 1: Try full attach + assign (works when VHDX is not attached)
        try:
            with open(script_path, "w") as f:
                f.write(
                    f"select vdisk file=\"{WINDOWS_VHDX_PATH}\"\n"
                    "attach vdisk\n"
                    "select partition 1\n"
                    f"assign letter={drive_letter}\n"
                    "exit\n"
                )
            run_command(
                f"diskpart /s \"{script_path}\"",
                description="diskpart attach and assign",
            )
        except Exception as exc:
            logger.warning("Full attach failed (disk may already be attached): %s", exc)
            # Step 2: VHDX already attached — just assign the drive letter
            try:
                with open(script_path, "w") as f:
                    f.write(
                        f"select vdisk file=\"{WINDOWS_VHDX_PATH}\"\n"
                        "select partition 1\n"
                        f"assign letter={drive_letter}\n"
                        "exit\n"
                    )
                run_command(
                    f"diskpart /s \"{script_path}\"",
                    description="diskpart assign drive letter",
                )
            except Exception as exc2:
                logger.error("Could not assign drive letter: %s", exc2)
        finally:
            try:
                os.remove(script_path)
            except OSError:
                pass

        # Verify the drive is now accessible
        time.sleep(1)
        if not os.path.isdir(WINDOWS_MOUNT_DRIVE + "\\"):
            raise RuntimeError(
                f"Drive {WINDOWS_MOUNT_DRIVE} is not accessible after reattach. "
                f"Try running Terminate first, then re-run Host Mode."
            )
        logger.info("Drive %s is now accessible.", WINDOWS_MOUNT_DRIVE)
        return

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


def _windows_grant_vscode_permissions():
    """Grant the guest user permissions needed for VS Code Remote-SSH.

    VS Code's server bootstrap runs `Get-CimInstance Win32_Process` to
    detect the platform/parent process. A standard user is denied WMI
    access to root\\cimv2 (HRESULT 0x80041003), which aborts the install
    with "$PLATFORM is undefined". Group membership alone is NOT enough;
    we must grant explicit permissions on the WMI namespace itself.
    """
    groups = [
        "Performance Monitor Users",
        "Distributed COM Users",
    ]
    for group in groups:
        try:
            run_command(
                f'net localgroup "{group}" {WINDOWS_GUEST_USER} /add',
                description=f"add {WINDOWS_GUEST_USER} to {group}",
                check=False,
            )
        except Exception as exc:
            logger.warning("Could not add to %s: %s", group, exc)

    _windows_grant_wmi_access()


def _windows_grant_wmi_access():
    """Grant the guest user read/execute access to the root\\cimv2 WMI namespace.

    This is required for VS Code Remote-SSH: its install script enumerates
    Win32_Process via CIM. We modify the namespace security descriptor to
    add an inherited ACE granting Enable Account, Execute Methods, Remote
    Enable, and Read Security to the guest's SID.
    """
    vhdx_dir = os.path.dirname(WINDOWS_VHDX_PATH)
    try:
        os.makedirs(vhdx_dir, exist_ok=True)
    except OSError:
        vhdx_dir = os.environ.get("TEMP", r"C:\Windows\Temp")

    script_path = os.path.join(vhdx_dir, "grant_wmi.ps1")
    # Permission mask: Enable(1) | MethodExecute(2) | RemoteEnable(0x20)
    #                  | ReadSecurity(0x20000)
    ps_script = f"""
$ErrorActionPreference = 'Stop'
$account = '{WINDOWS_GUEST_USER}'
foreach ($namespace in @('root/cimv2','root')) {{
  try {{
    $accessMask = 1 -bor 2 -bor 0x20 -bor 0x20000
    $ntAccount = New-Object System.Security.Principal.NTAccount($account)
    $sid = $ntAccount.Translate([System.Security.Principal.SecurityIdentifier]).Value

    $sd = Invoke-WmiMethod -Namespace $namespace -Path "__systemsecurity=@" -Name GetSecurityDescriptor
    if ($sd.ReturnValue -ne 0) {{ throw "GetSecurityDescriptor failed ($($sd.ReturnValue))" }}
    $acl = $sd.Descriptor

    $CONTAINER_INHERIT_ACE_FLAG = 0x2
    $ACCESS_ALLOWED_ACE_TYPE = 0x0

    $ace = (New-Object System.Management.ManagementClass("win32_Ace")).CreateInstance()
    $ace.AccessMask = $accessMask
    $ace.AceFlags = $CONTAINER_INHERIT_ACE_FLAG
    $trustee = (New-Object System.Management.ManagementClass("win32_Trustee")).CreateInstance()
    $trustee.SidString = $sid
    $ace.Trustee = $trustee
    $ace.AceType = $ACCESS_ALLOWED_ACE_TYPE

    $acl.DACL += $ace.psobject.immediateBaseObject

    $set = Invoke-WmiMethod -Namespace $namespace -Path "__systemsecurity=@" -Name SetSecurityDescriptor -ArgumentList $acl
    if ($set.ReturnValue -ne 0) {{ throw "SetSecurityDescriptor failed ($($set.ReturnValue))" }}
    Write-Output "WMI access granted on $namespace for $account"
  }} catch {{
    Write-Output "WMI grant skipped on $namespace : $($_.Exception.Message)"
  }}
}}
"""
    try:
        with open(script_path, "w") as f:
            f.write(ps_script)
        run_command(
            f'powershell -NoProfile -ExecutionPolicy Bypass -File "{script_path}"',
            description="grant guest WMI access to root/cimv2",
            check=False,
        )
        logger.info("Granted WMI namespace access to %s.", WINDOWS_GUEST_USER)
    except Exception as exc:
        logger.warning("Could not grant WMI access: %s", exc)
    finally:
        try:
            os.remove(script_path)
        except OSError:
            pass


def _windows_scan_tool_paths():
    """Scan the system for installed developer tools and return found paths."""
    candidates = [
        # Python (system-wide installs)
        r"C:\Python314", r"C:\Python314\Scripts",
        r"C:\Python313", r"C:\Python313\Scripts",
        r"C:\Python312", r"C:\Python312\Scripts",
        r"C:\Python311", r"C:\Python311\Scripts",
        r"C:\Python310", r"C:\Python310\Scripts",
        r"C:\Python39", r"C:\Python39\Scripts",
        r"C:\Program Files\Python314", r"C:\Program Files\Python314\Scripts",
        r"C:\Program Files\Python313", r"C:\Program Files\Python313\Scripts",
        r"C:\Program Files\Python312", r"C:\Program Files\Python312\Scripts",
        r"C:\Program Files\Python311", r"C:\Program Files\Python311\Scripts",
        # Git
        r"C:\Program Files\Git\cmd",
        r"C:\Program Files\Git\bin",
        r"C:\Program Files\Git\usr\bin",
        r"C:\Program Files (x86)\Git\cmd",
        # Node.js
        r"C:\Program Files\nodejs",
        r"C:\Program Files (x86)\nodejs",
        # VS Code
        r"C:\Program Files\Microsoft VS Code\bin",
        # Java
        r"C:\Program Files\Java\jdk-21\bin",
        r"C:\Program Files\Java\jdk-17\bin",
        # Go
        r"C:\Program Files\Go\bin",
        # Rust
        r"C:\Users\*\.cargo\bin",
        # CUDA
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin",
        # Conda / Miniconda / Anaconda
        r"C:\ProgramData\miniconda3",
        r"C:\ProgramData\miniconda3\Scripts",
        r"C:\ProgramData\miniconda3\condabin",
        r"C:\ProgramData\Anaconda3",
        r"C:\ProgramData\Anaconda3\Scripts",
        r"C:\ProgramData\Anaconda3\condabin",
    ]

    import glob
    found = []
    seen = set()

    # Expand wildcards and check existence
    for candidate in candidates:
        if "*" in candidate:
            for expanded in glob.glob(candidate):
                if os.path.isdir(expanded):
                    norm = expanded.rstrip("\\").lower()
                    if norm not in seen:
                        found.append(expanded)
                        seen.add(norm)
        elif os.path.isdir(candidate):
            norm = candidate.rstrip("\\").lower()
            if norm not in seen:
                found.append(candidate)
                seen.add(norm)

    # Scan per-user directories for tools
    users_dir = r"C:\Users"
    if os.path.isdir(users_dir):
        for user_dir in os.listdir(users_dir):
            user_path = os.path.join(users_dir, user_dir)
            if not os.path.isdir(user_path):
                continue

            # All known per-user tool locations
            per_user_dirs = [
                # Python — multiple known install locations
                os.path.join(user_path, "AppData", "Local", "Programs", "Python"),
                os.path.join(user_path, "AppData", "Local", "Python"),
                os.path.join(user_path, "AppData", "Local", "Python", "bin"),
                # Conda
                os.path.join(user_path, "miniconda3"),
                os.path.join(user_path, "miniconda3", "Scripts"),
                os.path.join(user_path, "miniconda3", "condabin"),
                os.path.join(user_path, "Anaconda3"),
                os.path.join(user_path, "Anaconda3", "Scripts"),
                os.path.join(user_path, "Anaconda3", "condabin"),
                # npm global
                os.path.join(user_path, "AppData", "Roaming", "npm"),
                # Rust
                os.path.join(user_path, ".cargo", "bin"),
                # WindowsApps (Python Store version)
                os.path.join(user_path, "AppData", "Local",
                             "Microsoft", "WindowsApps"),
            ]

            for d in per_user_dirs:
                if os.path.isdir(d):
                    norm = d.rstrip("\\").lower()
                    if norm not in seen:
                        found.append(d)
                        seen.add(norm)

            # Check Programs\Python version subdirectories
            programs_python = os.path.join(
                user_path, "AppData", "Local", "Programs", "Python"
            )
            if os.path.isdir(programs_python):
                for py_ver in os.listdir(programs_python):
                    py_path = os.path.join(programs_python, py_ver)
                    if os.path.isdir(py_path):
                        for sub in ["", "Scripts"]:
                            d = os.path.join(py_path, sub) if sub else py_path
                            if os.path.isdir(d):
                                norm = d.rstrip("\\").lower()
                                if norm not in seen:
                                    found.append(d)
                                    seen.add(norm)

    # Fallback: use 'where.exe' to find tools the scanner might have missed
    for tool in ["python", "python3", "git", "node", "npm", "conda",
                 "go", "rustc", "java", "nvcc"]:
        try:
            result = subprocess.run(
                ["where.exe", tool],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().splitlines():
                    tool_dir = os.path.dirname(line.strip())
                    if tool_dir and os.path.isdir(tool_dir):
                        norm = tool_dir.rstrip("\\").lower()
                        if norm not in seen:
                            found.append(tool_dir)
                            seen.add(norm)
        except Exception:
            pass

    return found


def _windows_grant_tool_access():
    """Grant the guest user read+execute access to discovered tool dirs.

    Per-user Python installs (AppData\\Local\\Python) are not accessible
    to other users by default. This grants read+execute so the guest can
    run tools without being able to modify them.
    """
    tool_paths = _windows_scan_tool_paths()
    if not tool_paths:
        logger.info("No tool directories found to grant access to.")
        return

    granted = []
    for tool_dir in tool_paths:
        # Only grant access to per-user directories (C:\Users\...)
        # System-wide dirs (C:\Program Files, etc.) are already accessible
        if not tool_dir.lower().startswith(r"c:\users"):
            continue
        try:
            run_command(
                f'icacls "{tool_dir}" /grant {WINDOWS_GUEST_USER}:(OI)(CI)RX /T /C /Q',
                description=f"grant read+execute on {tool_dir}",
                check=False,
            )
            granted.append(tool_dir)
            print(f"    + Granted access: {tool_dir}")
        except Exception as exc:
            logger.warning("Could not grant access to %s: %s", tool_dir, exc)

    if granted:
        logger.info("Granted guest read+execute access to %d tool dirs.", len(granted))


def windows_create_guest_user():
    """Create a standard local user 'WizGuest' on Windows with home on X:\\."""
    password = _get_or_create_password()

    try:
        result = run_command(
            f'net user {WINDOWS_GUEST_USER}',
            description="check WizGuest user",
            check=False,
        )
        if result.returncode == 0:
            logger.info("User '%s' already exists. Resetting password.", WINDOWS_GUEST_USER)
            try:
                run_command(
                    f'net user {WINDOWS_GUEST_USER} "{password}"',
                    description="reset WizGuest password",
                )
            except Exception as exc:
                logger.warning("Could not reset password: %s", exc)
            # Ensure home directory is set to the sandbox drive
            try:
                run_command(
                    f'net user {WINDOWS_GUEST_USER} /homedir:{WINDOWS_MOUNT_DRIVE}\\',
                    description="set WizGuest home directory",
                    check=False,
                )
            except Exception as exc:
                logger.warning("Could not set home directory: %s", exc)
            _windows_grant_vscode_permissions()
            return
    except Exception as exc:
        logger.warning("Could not check user existence: %s", exc)

    try:
        run_command(
            f'net user {WINDOWS_GUEST_USER} "{password}" /add /active:yes '
            f'/homedir:{WINDOWS_MOUNT_DRIVE}\\ '
            f'/comment:"Wiz Island Guest Account" /passwordchg:no',
            description="create WizGuest user",
        )
        logger.info("Created user '%s' with home %s.", WINDOWS_GUEST_USER, WINDOWS_MOUNT_DRIVE)
    except Exception as exc:
        logger.error("Failed to create user '%s': %s", WINDOWS_GUEST_USER, exc)
        raise

    _windows_grant_vscode_permissions()


def windows_set_permissions():
    """Restrict X:\\ access so only WizGuest can use it.

    Uses /T so the grants apply recursively to all EXISTING files too.
    This matters when reusing a sandbox: the guest user is recreated with
    a new SID, and without /T the old files stay inaccessible (the cause
    of "Access denied" when uploading/editing through VS Code or SCP).
    """
    try:
        run_command(
            f'icacls {WINDOWS_MOUNT_DRIVE}\\ /inheritance:r',
            description="icacls remove inheritance",
        )
        run_command(
            f'icacls {WINDOWS_MOUNT_DRIVE}\\ '
            f'/grant {WINDOWS_GUEST_USER}:(OI)(CI)F /T /C /Q',
            description="icacls grant WizGuest full control (recursive)",
        )
        run_command(
            f'icacls {WINDOWS_MOUNT_DRIVE}\\ '
            f'/grant Administrators:(OI)(CI)F /T /C /Q',
            description="icacls grant Administrators full control (recursive)",
        )
        logger.info("Permissions set on %s for %s.", WINDOWS_MOUNT_DRIVE, WINDOWS_GUEST_USER)
    except Exception as exc:
        logger.error("Failed to set permissions on %s: %s", WINDOWS_MOUNT_DRIVE, exc)
        raise


def _windows_validate_sshd_config():
    """Test sshd_config syntax using sshd -t. Returns True if valid."""
    sshd_exe = shutil.which("sshd")
    if not sshd_exe:
        sshd_exe = r"C:\Windows\System32\OpenSSH\sshd.exe"
        if not os.path.exists(sshd_exe):
            logger.warning("sshd.exe not found; skipping config validation.")
            return True
    try:
        result = run_command(
            f'"{sshd_exe}" -t',
            description="validate sshd_config",
            check=False,
        )
        if result.returncode == 0:
            logger.info("sshd_config syntax check passed.")
            return True
        logger.error("sshd_config syntax check failed: %s", result.stderr.strip())
        return False
    except Exception as exc:
        logger.warning("Could not validate sshd_config: %s", exc)
        return True


def _windows_restart_sshd():
    """Restart the sshd service on Windows with robust error handling."""
    # Stop sshd (ignore errors if it's not running)
    run_command("net stop sshd", description="stop sshd service", check=False)

    # Brief pause to allow the service to fully release resources
    time.sleep(2)

    # Start sshd
    try:
        run_command("net start sshd", description="start sshd service")
        logger.info("sshd service restarted successfully.")
    except Exception:
        # Fallback: try sc command
        logger.warning("net start failed, trying sc start...")
        try:
            run_command("sc start sshd", description="sc start sshd", check=False)
            time.sleep(3)
            result = run_command("sc query sshd", description="query sshd status", check=False)
            if "RUNNING" in result.stdout:
                logger.info("sshd service started via sc.")
                return
        except Exception:
            pass
        raise


def _windows_ensure_password_auth():
    """Ensure PasswordAuthentication is enabled in sshd_config for guest logins."""
    try:
        if not os.path.exists(WINDOWS_SSHD_CONFIG):
            return
        with open(WINDOWS_SSHD_CONFIG, "r") as f:
            content = f.read()

        import re
        # Enable PasswordAuthentication if it's explicitly disabled
        if re.search(r"^\s*PasswordAuthentication\s+no", content, re.MULTILINE):
            content = re.sub(
                r"^(\s*)PasswordAuthentication\s+no",
                r"\1PasswordAuthentication yes",
                content,
                flags=re.MULTILINE,
            )
            with open(WINDOWS_SSHD_CONFIG, "w") as f:
                f.write(content)
            logger.info("Enabled PasswordAuthentication in sshd_config.")
    except Exception as exc:
        logger.warning("Could not check/set PasswordAuthentication: %s", exc)


def windows_configure_ssh_jail():
    """Configure sshd_config to restrict WizGuest to the sandbox drive.

    Uses a Match User block with the user's home directory set to X:\\
    so VS Code Remote-SSH can install its server and work properly.
    ForceCommand is NOT used because it prevents VS Code from functioning.
    """
    match_block = (
        f"\n# --- Wiz Island SSH Jail ---\n"
        f"Match User {WINDOWS_GUEST_USER}\n"
        f"    PasswordAuthentication yes\n"
        f"    AllowTcpForwarding yes\n"
    )

    try:
        existing = ""
        if os.path.exists(WINDOWS_SSHD_CONFIG):
            with open(WINDOWS_SSHD_CONFIG, "r") as f:
                existing = f.read()

        if f"Match User {WINDOWS_GUEST_USER}" in existing:
            logger.info("SSH jail block already exists in sshd_config.")
            return

        # Back up the original config before modifying
        backup_path = WINDOWS_SSHD_CONFIG + ".wiz_backup"
        try:
            with open(backup_path, "w") as f:
                f.write(existing)
        except IOError as exc:
            logger.warning("Could not create sshd_config backup: %s", exc)

        # Enable password auth globally if needed
        _windows_ensure_password_auth()
        # Re-read after possible modification
        if os.path.exists(WINDOWS_SSHD_CONFIG):
            with open(WINDOWS_SSHD_CONFIG, "r") as f:
                existing = f.read()

        # Insert BEFORE any existing 'Match Group' block at the end,
        # because Windows sshd_config often has:
        #   Match Group administrators
        #       AuthorizedKeysFile ...
        # Appending after it would nest our directives incorrectly.
        import re
        admin_match = re.search(
            r"\n(Match\s+Group\s+administrators)", existing, re.IGNORECASE
        )
        if admin_match:
            insert_pos = admin_match.start()
            new_content = (
                existing[:insert_pos]
                + match_block + "\n"
                + existing[insert_pos:]
            )
        else:
            new_content = existing.rstrip() + "\n" + match_block

        with open(WINDOWS_SSHD_CONFIG, "w") as f:
            f.write(new_content)
        logger.info("Added SSH config block for '%s' to sshd_config.", WINDOWS_GUEST_USER)

        # Validate config before restarting
        if not _windows_validate_sshd_config():
            logger.error("sshd_config is invalid after modification. Restoring backup.")
            if os.path.exists(backup_path):
                with open(WINDOWS_SSHD_CONFIG, "w") as f:
                    with open(backup_path, "r") as bk:
                        f.write(bk.read())
                logger.info("Restored sshd_config from backup.")
            raise RuntimeError("sshd_config validation failed after adding SSH config block.")

        _windows_restart_sshd()

    except IOError as exc:
        logger.error("Failed to modify sshd_config: %s", exc)
        raise
    except RuntimeError:
        raise
    except Exception as exc:
        logger.error("Failed to configure SSH: %s", exc)
        # Try to restore backup if restart failed
        backup_path = WINDOWS_SSHD_CONFIG + ".wiz_backup"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, "r") as f:
                    original = f.read()
                with open(WINDOWS_SSHD_CONFIG, "w") as f:
                    f.write(original)
                logger.info("Restored sshd_config from backup after failure.")
                run_command("net start sshd", description="restart sshd after restore", check=False)
            except Exception as restore_exc:
                logger.error("Failed to restore sshd_config: %s", restore_exc)
        raise


def windows_configure_firewall():
    """Ensure Windows Firewall allows inbound SSH connections on port 22."""
    try:
        run_command(
            'netsh advfirewall firewall show rule name="WizIsland SSH"',
            description="check SSH firewall rule",
            check=False,
        )
        # If rule exists, we're done
        result = run_command(
            'netsh advfirewall firewall show rule name="WizIsland SSH"',
            description="check SSH firewall rule",
            check=False,
        )
        if result.returncode == 0 and "WizIsland SSH" in result.stdout:
            logger.info("Firewall rule 'WizIsland SSH' already exists.")
            return
    except Exception:
        pass

    try:
        run_command(
            'netsh advfirewall firewall add rule name="WizIsland SSH" '
            'dir=in action=allow protocol=TCP localport=22 '
            'profile=any enable=yes',
            description="add SSH firewall rule",
        )
        logger.info("Added firewall rule 'WizIsland SSH' for port 22.")
    except Exception as exc:
        logger.warning("Could not add firewall rule (SSH may still work): %s", exc)


def _windows_set_default_shell():
    """Set the default SSH shell to PowerShell and configure guest profile.

    Sets PowerShell as the default SSH shell, and creates a system-wide
    PowerShell profile that redirects the guest user to X:\\ on login.
    This is needed because Windows SSH ignores the /homedir flag from
    'net user' and always drops users into C:\\Users\\<username>.
    """
    ps_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not os.path.exists(ps_path):
        logger.info("PowerShell not found at default path, skipping shell config.")
        return

    reg_key = r"HKLM\SOFTWARE\OpenSSH"
    try:
        run_command(
            f'reg add "{reg_key}" /v DefaultShell /t REG_SZ '
            f'/d "{ps_path}" /f',
            description="set default SSH shell to PowerShell",
        )
        logger.info("Default SSH shell set to PowerShell.")
    except Exception as exc:
        logger.warning("Could not set default SSH shell: %s", exc)

    # Create a system-wide PowerShell profile that dynamically discovers
    # dev tools and adds them to PATH at login time. This runs when the
    # guest connects via SSH/VS Code, not at setup time.
    profile_dir = r"C:\Windows\System32\WindowsPowerShell\v1.0"
    profile_path = os.path.join(profile_dir, "profile.ps1")
    sandbox_dir = WINDOWS_MOUNT_DRIVE + "\\"

    # The profile script itself discovers tools dynamically each login
    profile_block = f"""
# --- Wiz Island Guest Environment ---
if ($env:USERNAME -eq '{WINDOWS_GUEST_USER}') {{
  try {{
    $ErrorActionPreference = 'SilentlyContinue'

    # Dynamically discover dev tools and add to PATH
    $toolDirs = @(
        'C:\\Program Files\\Git\\cmd',
        'C:\\Program Files\\Git\\bin',
        'C:\\Program Files\\Git\\usr\\bin',
        'C:\\Program Files\\nodejs',
        'C:\\Program Files\\Go\\bin',
        'C:\\Program Files\\Java\\jdk-21\\bin',
        'C:\\Program Files\\Java\\jdk-17\\bin',
        'C:\\Program Files\\Microsoft VS Code\\bin'
    )

    # System-wide Python installs
    foreach ($pyRoot in @('C:\\Python314','C:\\Python313','C:\\Python312','C:\\Python311','C:\\Python310','C:\\Python39')) {{
        if (Test-Path $pyRoot -EA 0) {{ $toolDirs += $pyRoot; $toolDirs += "$pyRoot\\Scripts" }}
    }}

    # Per-user tool installs
    Get-ChildItem 'C:\\Users' -Directory -EA 0 | ForEach-Object {{
        $u = $_.FullName
        foreach ($pyBase in @(
            (Join-Path $u 'AppData\\Local\\Python'),
            (Join-Path $u 'AppData\\Local\\Python\\bin'),
            (Join-Path $u 'AppData\\Local\\Programs\\Python')
        )) {{
            if (Test-Path $pyBase -EA 0) {{
                $toolDirs += $pyBase
                $sub = Join-Path $pyBase 'Scripts'
                if (Test-Path $sub -EA 0) {{ $toolDirs += $sub }}
                Get-ChildItem $pyBase -Directory -EA 0 | ForEach-Object {{
                    $toolDirs += $_.FullName
                    $s2 = Join-Path $_.FullName 'Scripts'
                    if (Test-Path $s2 -EA 0) {{ $toolDirs += $s2 }}
                }}
            }}
        }}
        foreach ($condaBase in @(
            (Join-Path $u 'miniconda3'),
            (Join-Path $u 'Anaconda3'),
            'C:\\ProgramData\\miniconda3',
            'C:\\ProgramData\\Anaconda3'
        )) {{
            if (Test-Path $condaBase -EA 0) {{
                $toolDirs += $condaBase
                foreach ($s in @('Scripts','condabin')) {{
                    $p = Join-Path $condaBase $s
                    if (Test-Path $p -EA 0) {{ $toolDirs += $p }}
                }}
            }}
        }}
        $npmDir = Join-Path $u 'AppData\\Roaming\\npm'
        if (Test-Path $npmDir -EA 0) {{ $toolDirs += $npmDir }}
        $cargoDir = Join-Path $u '.cargo\\bin'
        if (Test-Path $cargoDir -EA 0) {{ $toolDirs += $cargoDir }}
    }}

    # CUDA
    foreach ($cudaVer in @('v12.6','v12.0','v11.8')) {{
        $cudaPath = "C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\$cudaVer\\bin"
        if (Test-Path $cudaPath -EA 0) {{ $toolDirs += $cudaPath }}
    }}

    # Add discovered paths
    foreach ($d in $toolDirs) {{
        if ((Test-Path $d -EA 0) -and ($env:Path -notlike "*$d*")) {{
            $env:Path = "$d;" + $env:Path
        }}
    }}

    # Set working directory to sandbox
    if (Test-Path '{sandbox_dir}') {{
        Set-Location '{sandbox_dir}'
    }}
  }} catch {{ }}
  $ErrorActionPreference = 'Continue'
}}
# --- End Wiz Island ---
"""

    try:
        existing = ""
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                existing = f.read()

        # Remove any previous Wiz Island profile block
        if "Wiz Island Guest" in existing:
            start_marker = "# --- Wiz Island Guest"
            end_marker = "# --- End Wiz Island ---"
            start_idx = existing.find(start_marker)
            end_idx = existing.find(end_marker)
            if start_idx >= 0 and end_idx >= 0:
                existing = (
                    existing[:start_idx].rstrip()
                    + existing[end_idx + len(end_marker):]
                )

        with open(profile_path, "w") as f:
            f.write(existing.rstrip() + profile_block)
        logger.info("Configured guest PowerShell profile: %s", profile_path)
    except Exception as exc:
        logger.warning("Could not configure PowerShell profile: %s", exc)


def windows_setup_storage(size_gb):
    """Full Windows storage setup pipeline."""
    print(f"  [1/7] Creating {size_gb} GB VHDX virtual disk...")
    windows_create_vhdx(size_gb)

    print(f"  [2/7] Creating guest user '{WINDOWS_GUEST_USER}'...")
    windows_create_guest_user()

    print(f"  [3/7] Setting permissions on {WINDOWS_MOUNT_DRIVE}...")
    windows_set_permissions()

    print("  [4/7] Configuring SSH jail...")
    windows_configure_ssh_jail()

    print("  [5/7] Configuring shell & developer tools...")
    _windows_set_default_shell()

    print("  [6/7] Granting guest access to host tools...")
    _windows_grant_tool_access()

    print("  [7/7] Configuring firewall...")
    windows_configure_firewall()

    print("  Storage setup complete.")


# ============================================================
#  WINDOWS TEARDOWN OPERATIONS
# ============================================================

def windows_teardown(wipe_data=False):
    """Remove guest user and SSH jail config on Windows.

    By default the VHDX file is PRESERVED (only detached) so the sandbox
    data survives across restarts. Pass wipe_data=True to permanently
    delete the sandbox disk and all files in it.
    """
    print("  [*] Tearing down Windows sandbox...")

    # Detach VHDX (data on disk is preserved unless wipe_data=True)
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

    # Delete VHDX file only when explicitly wiping data
    if wipe_data:
        try:
            if os.path.exists(WINDOWS_VHDX_PATH):
                os.remove(WINDOWS_VHDX_PATH)
                logger.info("Deleted VHDX file: %s", WINDOWS_VHDX_PATH)
        except OSError as exc:
            logger.warning("Could not delete VHDX: %s", exc)
    else:
        if os.path.exists(WINDOWS_VHDX_PATH):
            print(f"  [*] Sandbox data preserved at {WINDOWS_VHDX_PATH}")
            logger.info("Preserved VHDX file: %s", WINDOWS_VHDX_PATH)

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

    # Remove firewall rule
    try:
        run_command(
            'netsh advfirewall firewall delete rule name="WizIsland SSH"',
            description="delete SSH firewall rule",
            check=False,
        )
        logger.info("Removed firewall rule 'WizIsland SSH'.")
    except Exception as exc:
        logger.warning("Could not remove firewall rule: %s", exc)

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
                run_command("net stop sshd", description="stop sshd", check=False)
                time.sleep(2)
                run_command("net start sshd", description="start sshd", check=False)
    except Exception as exc:
        logger.warning("Could not clean sshd_config: %s", exc)

    # Remove PowerShell profile block
    try:
        profile_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\profile.ps1"
        if os.path.exists(profile_path):
            with open(profile_path, "r") as f:
                content = f.read()
            # Match both old and new marker names
            for start_marker in [
                "# --- Wiz Island Guest Environment ---",
                "# --- Wiz Island Guest Redirect ---",
            ]:
                end_marker = "# --- End Wiz Island ---"
                if start_marker in content:
                    start_idx = content.index(start_marker)
                    end_idx = content.find(end_marker)
                    if end_idx >= 0:
                        content = (
                            content[:start_idx].rstrip()
                            + content[end_idx + len(end_marker):]
                        )
            with open(profile_path, "w") as f:
                f.write(content.strip() + "\n" if content.strip() else "")
            logger.info("Removed guest environment from PowerShell profile.")
    except Exception as exc:
        logger.warning("Could not clean PowerShell profile: %s", exc)

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

    validate_disk_space(size_gb, image_dir)

    if os.path.exists(LINUX_IMAGE_PATH):
        logger.warning("Disk image already exists at %s. Reusing.", LINUX_IMAGE_PATH)
        return

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
                f"dd if=/dev/zero of=\"{LINUX_IMAGE_PATH}\" "
                f"bs=1M count={size_gb * 1024} status=progress",
                description="dd create disk image",
            )
    else:
        try:
            run_command(
                f"dd if=/dev/zero of=\"{LINUX_IMAGE_PATH}\" "
                f"bs=1M count={size_gb * 1024} status=progress",
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

    # Check if already mounted
    try:
        result = run_command(
            f"mountpoint -q \"{LINUX_MOUNT_DIR}\"",
            description="check if already mounted",
            check=False,
        )
        if result.returncode == 0:
            logger.info("%s is already mounted.", LINUX_MOUNT_DIR)
            return
    except Exception:
        pass

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
    """Create a dedicated system user 'wizguest' with home in the sandbox workspace."""
    password = _get_or_create_password()
    workspace = os.path.join(LINUX_MOUNT_DIR, "workspace")

    try:
        result = run_command(
            f"id {LINUX_GUEST_USER}",
            description="check wizguest user",
            check=False,
        )
        if result.returncode == 0:
            logger.info("User '%s' already exists. Resetting password.", LINUX_GUEST_USER)
            try:
                run_command(
                    f"echo '{LINUX_GUEST_USER}:{password}' | chpasswd",
                    description="reset wizguest password",
                )
            except Exception as exc:
                logger.warning("Could not reset password: %s", exc)
            # Ensure home directory is set to workspace
            try:
                run_command(
                    f"usermod -d \"{workspace}\" -s /bin/bash {LINUX_GUEST_USER}",
                    description="set wizguest home and shell",
                    check=False,
                )
            except Exception as exc:
                logger.warning("Could not update home directory: %s", exc)
            return
    except Exception as exc:
        logger.warning("Could not check user existence: %s", exc)

    try:
        os.makedirs(workspace, exist_ok=True)
        run_command(
            f"useradd -m -s /bin/bash -d \"{workspace}\" {LINUX_GUEST_USER}",
            description="create wizguest user",
        )
        run_command(
            f"echo '{LINUX_GUEST_USER}:{password}' | chpasswd",
            description="set wizguest password",
        )
        logger.info("Created user '%s' with home at %s.", LINUX_GUEST_USER, workspace)
    except Exception as exc:
        logger.error("Failed to create user '%s': %s", LINUX_GUEST_USER, exc)
        raise


def linux_set_permissions():
    """Restrict ownership of /mnt/wizsandbox to the wizguest user.

    For ChrootDirectory to work, the chroot path and all parent directories
    must be owned by root with no group/other write permissions. We create
    a writable subdirectory inside for the user's actual workspace.
    """
    try:
        # ChrootDirectory requires root ownership on the mount point
        run_command(
            f"chown root:root \"{LINUX_MOUNT_DIR}\"",
            description="chown sandbox to root (ChrootDirectory requirement)",
        )
        run_command(
            f"chmod 755 \"{LINUX_MOUNT_DIR}\"",
            description="chmod sandbox directory",
        )
        # Create a writable workspace subdirectory for the guest user
        workspace = os.path.join(LINUX_MOUNT_DIR, "workspace")
        os.makedirs(workspace, exist_ok=True)
        run_command(
            f"chown {LINUX_GUEST_USER}:{LINUX_GUEST_USER} \"{workspace}\"",
            description="chown workspace directory",
        )
        run_command(
            f"chmod 755 \"{workspace}\"",
            description="chmod workspace directory",
        )
        logger.info("Permissions set on %s for %s.", LINUX_MOUNT_DIR, LINUX_GUEST_USER)
    except Exception as exc:
        logger.error("Failed to set permissions: %s", exc)
        raise


def _linux_ensure_password_auth():
    """Ensure PasswordAuthentication is enabled in sshd_config."""
    sshd_config = "/etc/ssh/sshd_config"
    try:
        if not os.path.exists(sshd_config):
            return
        with open(sshd_config, "r") as f:
            content = f.read()

        import re
        if re.search(r"^\s*PasswordAuthentication\s+no", content, re.MULTILINE):
            content = re.sub(
                r"^(\s*)PasswordAuthentication\s+no",
                r"\1PasswordAuthentication yes",
                content,
                flags=re.MULTILINE,
            )
            with open(sshd_config, "w") as f:
                f.write(content)
            logger.info("Enabled PasswordAuthentication in sshd_config.")
    except Exception as exc:
        logger.warning("Could not check/set PasswordAuthentication: %s", exc)


def linux_configure_ssh_jail():
    """Configure sshd_config to restrict wizguest to the sandbox.

    Sets the user's home directory to the sandbox workspace so they
    land there by default. Does NOT use ChrootDirectory or
    ForceCommand internal-sftp, because those prevent VS Code
    Remote-SSH from installing its server and working properly.
    """
    workspace = os.path.join(LINUX_MOUNT_DIR, "workspace")
    sshd_config = "/etc/ssh/sshd_config"
    match_block = (
        f"\n\n# --- Wiz Island SSH Jail ---\n"
        f"Match User {LINUX_GUEST_USER}\n"
        f"    PasswordAuthentication yes\n"
        f"    AllowTcpForwarding yes\n"
        f"    X11Forwarding yes\n"
    )

    try:
        existing = ""
        if os.path.exists(sshd_config):
            with open(sshd_config, "r") as f:
                existing = f.read()

        if f"Match User {LINUX_GUEST_USER}" in existing:
            logger.info("SSH jail block already exists in sshd_config.")
            return

        # Back up original config
        backup_path = sshd_config + ".wiz_backup"
        try:
            with open(backup_path, "w") as f:
                f.write(existing)
        except IOError as exc:
            logger.warning("Could not create sshd_config backup: %s", exc)

        # Enable password auth globally if needed
        _linux_ensure_password_auth()
        # Re-read after possible modification
        if os.path.exists(sshd_config):
            with open(sshd_config, "r") as f:
                existing = f.read()

        with open(sshd_config, "a") as f:
            f.write(match_block)
        logger.info("Appended SSH config block for '%s' to sshd_config.", LINUX_GUEST_USER)

        # Validate config before restarting
        result = run_command(
            "sshd -t", description="validate sshd_config", check=False,
        )
        if result.returncode != 0:
            logger.error("sshd_config validation failed: %s", result.stderr.strip())
            if os.path.exists(backup_path):
                with open(backup_path, "r") as f:
                    original = f.read()
                with open(sshd_config, "w") as f:
                    f.write(original)
                logger.info("Restored original sshd_config from backup.")
            raise RuntimeError("sshd_config validation failed after adding SSH config block.")

        run_command(
            "systemctl restart sshd || systemctl restart ssh",
            description="restart sshd service",
        )
    except IOError as exc:
        logger.error("Failed to modify sshd_config: %s", exc)
        raise
    except RuntimeError:
        raise
    except Exception as exc:
        logger.error("Failed to restart SSH service: %s", exc)
        raise


def linux_configure_firewall():
    """Ensure the firewall allows inbound SSH connections on port 22."""
    ufw_path = shutil.which("ufw")
    if not ufw_path:
        logger.info("ufw not found, skipping firewall configuration.")
        return

    try:
        run_command(
            "ufw allow 22/tcp",
            description="allow SSH through ufw",
            check=False,
        )
        logger.info("Firewall rule for SSH port 22 configured via ufw.")
    except Exception as exc:
        logger.warning("Could not configure ufw (SSH may still work): %s", exc)


def _linux_configure_guest_env():
    """Create a useful .bashrc for the guest user with PATH and aliases."""
    workspace = os.path.join(LINUX_MOUNT_DIR, "workspace")
    bashrc_path = os.path.join(workspace, ".bashrc")

    bashrc_content = """# Wiz Island Guest Environment
export PATH="/usr/local/cuda/bin:/usr/local/go/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
export LD_LIBRARY_PATH="/usr/local/cuda/lib64:$LD_LIBRARY_PATH"

# Aliases
alias ll='ls -la'
alias la='ls -A'
alias l='ls -CF'

# Welcome message
echo ""
echo "  Welcome to Wiz Island Sandbox"
echo "  Workspace: $(pwd)"
echo "  Available tools: $(which python3 2>/dev/null && echo 'python3') $(which git 2>/dev/null && echo 'git') $(which node 2>/dev/null && echo 'node') $(which gcc 2>/dev/null && echo 'gcc')"
echo "  GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'not detected')"
echo ""
"""
    try:
        with open(bashrc_path, "w") as f:
            f.write(bashrc_content)
        run_command(
            f"chown {LINUX_GUEST_USER}:{LINUX_GUEST_USER} \"{bashrc_path}\"",
            description="chown guest .bashrc",
            check=False,
        )
        logger.info("Created guest .bashrc at %s", bashrc_path)
    except Exception as exc:
        logger.warning("Could not create guest .bashrc: %s", exc)


def linux_setup_storage(size_gb):
    """Full Linux storage setup pipeline."""
    print(f"  [1/7] Creating {size_gb} GB disk image...")
    linux_create_image(size_gb)

    print(f"  [2/7] Mounting image at {LINUX_MOUNT_DIR}...")
    linux_mount_image()

    print(f"  [3/7] Creating guest user '{LINUX_GUEST_USER}'...")
    linux_create_guest_user()

    print(f"  [4/7] Setting permissions on {LINUX_MOUNT_DIR}...")
    linux_set_permissions()

    print("  [5/7] Configuring SSH jail...")
    linux_configure_ssh_jail()

    print("  [6/7] Configuring guest environment...")
    _linux_configure_guest_env()

    print("  [7/7] Configuring firewall...")
    linux_configure_firewall()

    print("  Storage setup complete.")


# ============================================================
#  LINUX TEARDOWN OPERATIONS
# ============================================================

def linux_teardown(wipe_data=False):
    """Remove guest user and SSH jail config on Linux.

    By default the disk image is PRESERVED (only unmounted) so the
    sandbox data survives across restarts. Pass wipe_data=True to
    permanently delete the sandbox image and all files in it.
    """
    print("  [*] Tearing down Linux sandbox...")

    # Kill any remaining processes by the guest user
    try:
        run_command(
            f"pkill -u {LINUX_GUEST_USER}",
            description="kill remaining wizguest processes",
            check=False,
        )
    except Exception as exc:
        logger.warning("Could not kill guest processes: %s", exc)

    # Unmount
    try:
        run_command(
            f"umount -l \"{LINUX_MOUNT_DIR}\"",
            description="lazy unmount sandbox",
            check=False,
        )
        logger.info("Unmounted %s.", LINUX_MOUNT_DIR)
    except Exception as exc:
        logger.warning("Unmount issue: %s", exc)

    # Delete image file only when explicitly wiping data
    if wipe_data:
        try:
            if os.path.exists(LINUX_IMAGE_PATH):
                os.remove(LINUX_IMAGE_PATH)
                logger.info("Deleted image file: %s", LINUX_IMAGE_PATH)
        except OSError as exc:
            logger.warning("Could not delete image: %s", exc)

        # Remove mount directory
        try:
            if os.path.exists(LINUX_MOUNT_DIR):
                shutil.rmtree(LINUX_MOUNT_DIR, ignore_errors=True)
                logger.info("Removed mount directory: %s", LINUX_MOUNT_DIR)
        except OSError as exc:
            logger.warning("Could not remove mount dir: %s", exc)
    else:
        if os.path.exists(LINUX_IMAGE_PATH):
            print(f"  [*] Sandbox data preserved at {LINUX_IMAGE_PATH}")
            logger.info("Preserved image file: %s", LINUX_IMAGE_PATH)

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
                content = f.read()
            marker = "# --- Wiz Island SSH Jail ---"
            if marker in content:
                cleaned = content[:content.index(marker)].rstrip() + "\n"
                with open(sshd_config, "w") as f:
                    f.write(cleaned)
                logger.info("Removed SSH jail block from sshd_config.")
                run_command("systemctl restart sshd || systemctl restart ssh",
                            description="restart sshd", check=False)
    except Exception as exc:
        logger.warning("Could not clean sshd_config: %s", exc)

    print("  Teardown complete.")


# ============================================================
#  PUBLIC INTERFACE
# ============================================================

def setup_storage(size_gb):
    """Set up storage on the current platform.

    Returns True on success, raises an exception on failure.
    """
    if check_existing_setup():
        print("\n  [WARNING] Previous Wiz Island setup detected.")
        print("  Reusing keeps all your existing sandbox files.")
        response = input("  Do you want to reuse the existing setup? (yes/no): ").strip().lower()
        if response not in ("yes", "y"):
            confirm_wipe = input(
                "  Start fresh — PERMANENTLY DELETE existing sandbox data? (yes/no): "
            ).strip().lower()
            wipe = confirm_wipe in ("yes", "y")
            print("  Cleaning up previous setup first...")
            teardown_storage(wipe_data=wipe)

    plat = get_platform()
    if plat == "windows":
        windows_setup_storage(size_gb)
    else:
        linux_setup_storage(size_gb)
    return True


def teardown_storage(wipe_data=False):
    """Tear down storage on the current platform.

    By default sandbox data is preserved (disk detached but kept). Pass
    wipe_data=True to permanently delete the sandbox disk and its files.
    """
    plat = get_platform()
    if plat == "windows":
        windows_teardown(wipe_data=wipe_data)
    else:
        linux_teardown(wipe_data=wipe_data)
    # Clear the session password
    global _guest_password
    _guest_password = None


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
    password = _get_or_create_password()
    if plat == "windows":
        return WINDOWS_GUEST_USER, password
    else:
        return LINUX_GUEST_USER, password
