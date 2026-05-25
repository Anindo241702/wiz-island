# Wiz Island - User Manual

**Version 1.1.0**

A comprehensive guide for new users to set up, configure, and use Wiz Island for peer-to-peer SSH tunneling.

---

## Table of Contents

1. [What is Wiz Island?](#1-what-is-wiz-island)
2. [System Requirements](#2-system-requirements)
3. [Installation](#3-installation)
   - [Windows Installation](#31-windows-installation)
   - [Linux Installation](#32-linux-installation-ubuntudebian)
   - [Manual Installation](#33-manual-installation)
4. [Getting an Ngrok Account](#4-getting-an-ngrok-account)
5. [Using Wiz Island](#5-using-wiz-island)
   - [Launching the Application](#51-launching-the-application)
   - [Host Mode](#52-host-mode-sharing-your-machine)
   - [User Mode](#53-user-mode-connecting-to-a-host)
   - [Terminate / Panic Button](#54-terminate--panic-button)
6. [The Host Dashboard](#6-the-host-dashboard)
7. [Connecting via VS Code](#7-connecting-via-vs-code)
8. [Command-Line Arguments](#8-command-line-arguments)
9. [Troubleshooting](#9-troubleshooting)
10. [Security Considerations](#10-security-considerations)
11. [FAQ](#11-faq)
12. [Uninstalling](#12-uninstalling)

---

## 1. What is Wiz Island?

Wiz Island is a **serverless, peer-to-peer CLI tool** that allows you to securely share your computer's resources (CPU, GPU, RAM, and storage) with another person over an SSH tunnel, without needing a dedicated server.

**How it works:**
- The **Host** runs Wiz Island on their machine, which creates an isolated sandbox environment and opens a secure tunnel via Ngrok.
- The **Client/User** receives a connection string and uses it to connect to the Host's machine through SSH.
- Everything is set up automatically — no manual SSH server configuration needed.

**Use cases:**
- Remote pair programming with VS Code
- Sharing compute resources for development/testing
- Providing a temporary sandboxed environment for collaboration
- Remote access to your own machine from anywhere

---

## 2. System Requirements

### Minimum Requirements

| Component     | Requirement                                    |
|---------------|------------------------------------------------|
| **OS**        | Windows 10/11 or Ubuntu/Debian-based Linux     |
| **Python**    | 3.10 or higher                                 |
| **RAM**       | 2 GB minimum (4 GB+ recommended)               |
| **Disk**      | Enough free space for the sandbox (user-defined)|
| **Internet**  | Required for Ngrok tunnel                      |
| **Privileges**| Administrator (Windows) or root/sudo (Linux)   |

### Software Dependencies (Auto-Installed)

These are installed automatically by the setup scripts:

- **Python 3.10+** — Core application runtime
- **OpenSSH Server** — SSH connectivity
- **Ngrok** — Secure tunnel provider
- **psutil** — System monitoring library (Python)

---

## 3. Installation

### 3.1 Windows Installation

1. **Download** or clone the Wiz Island project to your computer.

2. **Right-click** `setup.bat` and select **"Run as Administrator"**.

3. The script will automatically:
   - Check for Administrator privileges (re-launches with UAC if needed)
   - Install Python via `winget` (if not present)
   - Install OpenSSH Server (if not present)
   - Install Ngrok via `winget` (if not present)
   - Configure Windows Firewall rules for SSH
   - Install Python dependencies (`psutil`)
   - Launch the Wiz Island CLI

4. If any step fails, the script will display an error message with instructions for manual installation.

> **Note:** The first run may take a few minutes while dependencies are being installed.

### 3.2 Linux Installation (Ubuntu/Debian)

1. **Download** or clone the Wiz Island project to your computer.

2. Open a terminal and run:
   ```bash
   chmod +x setup.sh
   sudo ./setup.sh
   ```

3. The script will automatically:
   - Check for sudo/root privileges (re-launches with sudo if needed)
   - Detect your package manager (apt-get, dnf, or yum)
   - Install Python3 and pip (if not present)
   - Install OpenSSH Server (if not present)
   - Download and install the Ngrok binary for your architecture
   - Configure firewall rules via `ufw` (if available)
   - Install Python dependencies (`psutil`)
   - Launch the Wiz Island CLI

> **Supported architectures:** x86_64 (amd64), aarch64 (arm64), armv7l (arm), i686 (386)

### 3.3 Manual Installation

If you prefer to install dependencies yourself:

1. Install Python 3.10+ from [python.org](https://python.org)
2. Install OpenSSH Server for your platform
3. Install Ngrok from [ngrok.com/download](https://ngrok.com/download)
4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Launch the application:
   ```bash
   python src/main.py        # Windows
   python3 src/main.py       # Linux
   ```

---

## 4. Getting an Ngrok Account

Wiz Island uses Ngrok to create secure TCP tunnels. You need a **free Ngrok account**:

1. Go to [https://ngrok.com/](https://ngrok.com/) and click **Sign Up**.
2. Create an account (you can use Google/GitHub to sign in).
3. After logging in, go to [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken).
4. Copy your **AuthToken** — you'll need this when running Host Mode.

> **Important:** Keep your AuthToken private. Anyone with your token can create tunnels under your account.

> **Free tier limits:** The free Ngrok plan allows 1 online tunnel at a time with randomly assigned URLs. This is sufficient for most Wiz Island use cases.

---

## 5. Using Wiz Island

### 5.1 Launching the Application

After installation, the CLI presents an interactive menu:

```
  ============================================================

   __        ___       ___     _                 _
   \ \      / (_)__   |_ _|__| | __ _ _ __   __| |
    \ \ /\ / /| |_ /   | |/ _` |/ _` | '_ \ / _` |
     \ V  V / | |/ /    | | (_| | (_| | | | | (_| |
      \_/\_/  |_/___|  |___\__,_|\__,_|_| |_|\__,_|

   Serverless P2P SSH Tunneling Tool  v1.0.0
   Platform: Linux 5.15.0
   Privileges: Administrator

  ============================================================

  ------------------------------------------------------------
   MAIN MENU
  ------------------------------------------------------------

   [1]  HOST MODE     - Share your machine's resources
   [2]  USER MODE     - Connect to a remote host
   [3]  TERMINATE     - Panic button / Full cleanup

   [0]  EXIT

  ------------------------------------------------------------
```

### 5.2 Host Mode (Sharing Your Machine)

Select **[1] HOST MODE** from the main menu. The setup process has several steps:

#### Step 1: Storage Quota

```
  Enter storage quota in GB (e.g., 10): 10
```

Enter how much disk space to allocate for the guest sandbox. This creates an isolated virtual disk:
- **Windows:** Creates an expandable VHDX file mounted as drive `X:\`
- **Linux:** Creates an EXT4 disk image mounted at `/mnt/wizsandbox`

> **Tip:** Start with a small quota (5-10 GB). The virtual disk is expandable.

If a previous setup is detected, you'll be asked whether to reuse it or start fresh.

#### Step 2: Ngrok AuthToken

```
  You can get your AuthToken from: https://dashboard.ngrok.com/get-started/your-authtoken
  Enter your Ngrok AuthToken: 2abc123def456...
```

Paste your Ngrok AuthToken. The application will configure it automatically.

#### Step 3: Tunnel Creation

The application starts an Ngrok TCP tunnel on port 22 (SSH). This typically takes 5-10 seconds.

#### Step 4: Dashboard

Once the tunnel is established, a real-time dashboard appears:

```
  ============================================================
   WIZ ISLAND - HOST DASHBOARD
  ============================================================

   TUNNEL URL       : tcp://0.tcp.ngrok.io:12345
   SSH Command      : ssh wizguest@0.tcp.ngrok.io -p 12345
   Guest Password   : aB3xK9mP2qR7wF_
   Uptime           : 5m 23s

  ------------------------------------------------------------
   SYSTEM PERFORMANCE
  ------------------------------------------------------------
   CPU Usage        : [####----------------] 20.5%  (8 cores)
   RAM Usage        : [########------------] 42.3%  (6892 / 16304 MB)
   RAM Available    : 9.2 GB

  ------------------------------------------------------------
   STORAGE (Sandbox)
  ------------------------------------------------------------
   Total            : 10.0 GB
   Used             : [#-------------------] 0.12 GB (1.2%)
   Free             : 9.88 GB
   Mount Path       : /mnt/wizsandbox

  ------------------------------------------------------------
   NETWORK
  ------------------------------------------------------------
   Active SSH Conns : 0
   Upload Rate      : 1.2 KB/s
   Download Rate    : 0.8 KB/s
   Total Sent       : 45.3 MB
   Total Received   : 123.7 MB

  ============================================================
   Press 'x' then Enter to activate PANIC BUTTON (Ctrl+C also works)
  ============================================================
```

**After the tunnel is established, a connection summary is displayed.**

Share these details with your guest:
- The **Tunnel URL** (or the **SSH Command** line)
- The **Guest Username** (WizGuest on Windows, wizguest on Linux)
- The **Guest Password** (randomly generated each session)

Press Enter to launch the live dashboard, which refreshes every 2 seconds.

### 5.3 User Mode (Connecting to a Host)

Select **[2] USER MODE** from the main menu. You'll see a sub-menu:

```
   [1]  Connect to a Host
   [2]  Clean/Remove WizIsland SSH Config
   [0]  Back to Main Menu
```

#### Connecting to a Host

1. Select **[1] Connect to a Host**
2. Paste the connection string provided by the Host:
   ```
   Paste the Ngrok connection string: tcp://0.tcp.ngrok.io:12345
   ```
   Accepted formats:
   - `tcp://0.tcp.ngrok.io:12345`
   - `0.tcp.ngrok.io:12345`
   - `ssh wizguest@0.tcp.ngrok.io -p 12345`

3. The application will:
   - Parse the connection details
   - Test TCP connectivity to the host
   - Ask for the guest username (WizGuest for Windows hosts, wizguest for Linux hosts)
   - Optionally accept the guest password for display in instructions
   - Update your `~/.ssh/config` file
   - Display detailed connection instructions for terminal and VS Code

4. Connect using one of the provided methods:
   ```bash
   ssh WizIsland
   ```
   Or:
   ```bash
   ssh wizguest@0.tcp.ngrok.io -p 12345
   ```

#### Cleaning SSH Config

Select **[2] Clean/Remove WizIsland SSH Config** to remove the WizIsland entry from your SSH config file. This is useful when you're done with a session.

### 5.4 Terminate / Panic Button

Select **[3] TERMINATE** from the main menu (or press `x` + Enter while the dashboard is running).

This performs a complete cleanup:

1. **Stops the Ngrok tunnel** — No more external connections
2. **Kills all guest SSH sessions** — Immediately disconnects any connected users
3. **Unmounts virtual disks** — Safely detaches the sandbox storage
4. **Deletes guest accounts** — Removes the temporary user account
5. **Cleans SSH config** — Removes jail configuration from sshd_config
6. **Removes firewall rules** — Cleans up any added firewall exceptions

After termination, your machine is returned to its exact native state.

---

## 6. The Host Dashboard

The dashboard provides real-time monitoring of your system while hosting:

| Metric | Description |
|--------|-------------|
| **Tunnel URL** | The public Ngrok TCP address for connections |
| **SSH Command** | Ready-to-copy command for the guest |
| **Guest Password** | Randomly generated password for this session |
| **Uptime** | How long the session has been active |
| **CPU Usage** | Current CPU utilization with core count |
| **RAM Usage** | Memory usage with used/total breakdown |
| **RAM Available** | Free RAM available for processes |
| **Storage** | Sandbox disk usage (total, used, free, percent) |
| **Active SSH Conns** | Number of currently connected SSH sessions |
| **Network Rates** | Real-time upload/download transfer rates |
| **Total Transfer** | Cumulative data sent/received |

The dashboard refreshes every 2 seconds. All metrics are collected via the `psutil` library for cross-platform consistency.

---

## 7. Connecting via VS Code

VS Code's **Remote - SSH** extension provides the best experience for development:

### Setup (One-Time)

1. Open VS Code
2. Go to Extensions (`Ctrl+Shift+X`)
3. Search for **"Remote - SSH"** (by Microsoft)
4. Click **Install**

### Connecting

1. After running User Mode and configuring your SSH config:
2. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
3. Type: **"Remote-SSH: Connect to Host..."**
4. Select **"WizIsland"** from the dropdown
5. Select the platform type (Linux/Windows) when prompted
6. Enter the guest password when prompted
7. VS Code will install its remote server component and open a remote window

### Working Remotely

Once connected:
- The **Explorer** panel shows the Host's sandbox filesystem
- The **Terminal** runs on the Host machine with full shell access
- You have full access to the Host's CPU, RAM, GPU, and storage for builds and tasks
- File editing happens locally; saves are synced to the Host
- You can install VS Code extensions on the remote side for full IDE features
- Python, Node.js, compilers, and other tools installed on the Host are available

---

## 8. Command-Line Arguments

You can skip the interactive menu by using command-line arguments:

```bash
# Show version
python src/main.py --version
python src/main.py -v

# Launch directly into Host Mode
python src/main.py --mode host
python src/main.py -m host

# Launch directly into User Mode
python src/main.py --mode user
python src/main.py -m user

# Launch directly into Terminate
python src/main.py --mode terminate
python src/main.py -m terminate
```

---

## 9. Troubleshooting

### Common Issues

#### "Ngrok exited unexpectedly"
- **Cause:** Invalid AuthToken or network issue
- **Fix:** Verify your AuthToken at https://dashboard.ngrok.com. Check your internet connection. Ensure no other Ngrok tunnel is running (free tier allows only 1).

#### "Storage setup failed"
- **Cause:** Insufficient privileges or disk space
- **Fix:** Ensure you're running as Administrator (Windows) or root (Linux). Check available disk space.

#### "Python not found" (after installation on Windows)
- **Cause:** Python not added to PATH
- **Fix:** Close and reopen your terminal. Or add Python to PATH manually via System Settings > Environment Variables.

#### "Connection refused" when SSHing
- **Cause:** SSH server not running, or firewall blocking port 22
- **Fix:** Ensure OpenSSH Server is running. On Windows: `net start sshd`. On Linux: `sudo systemctl start ssh`. Check firewall rules.

#### "Permission denied" when connecting
- **Cause:** Wrong password or user doesn't exist
- **Fix:** Make sure the Host has shared the correct password. The password is randomly generated each session and shown on the Host dashboard.

#### Dashboard shows "0 Active SSH Conns" even when connected
- **Cause:** The connection counter checks port 22 directly; Ngrok traffic arrives on a different port
- **Fix:** This is expected behavior. The counter tracks direct SSH connections. Your connection through Ngrok is still active.

### Log Files

All operations are logged to `logs/wiz_island.log` in the project directory. Check this file for detailed error messages and debug information.

To view recent logs:
```bash
# Linux
tail -50 logs/wiz_island.log

# Windows (PowerShell)
Get-Content logs\wiz_island.log -Tail 50
```

### Getting Help

If you encounter issues not covered here:
1. Check the log file for detailed error messages
2. Ensure all prerequisites are installed correctly
3. Try running the setup script again
4. Open an issue on the project repository

---

## 10. Security Considerations

### What Wiz Island Does for Security

- **Isolated Sandbox:** Guest users start in an isolated virtual disk workspace
- **SSH Configuration:** The guest account is restricted via `sshd_config` Match User rules
- **No Sudo Access:** The guest account has no administrator/root privileges
- **Random Passwords:** A new secure password is generated for each session
- **Encrypted Tunnel:** All traffic goes through Ngrok's encrypted TCP tunnel
- **Panic Button:** Instant full cleanup at any time

### What You Should Be Aware Of

- **Resource Sharing:** The guest has access to your CPU, RAM, and GPU while connected. Monitor usage via the dashboard.
- **AuthToken Security:** Keep your Ngrok AuthToken private. Don't share it publicly.
- **Password Sharing:** Only share the guest password with people you trust.
- **Network Exposure:** While the Ngrok tunnel is active, anyone with the URL and password can attempt to connect.
- **Session Duration:** Don't leave a session running indefinitely without monitoring.

### Best Practices

1. Only share connection details with trusted individuals
2. Monitor the dashboard for unexpected connections
3. Use the Panic Button immediately if you notice suspicious activity
4. Run Terminate when you're done hosting — don't leave the tunnel open
5. Check `logs/wiz_island.log` periodically for unusual activity

---

## 11. FAQ

**Q: Is Wiz Island free to use?**
A: Yes. Wiz Island is free. Ngrok's free tier provides sufficient functionality for peer-to-peer connections.

**Q: Can the guest access my personal files?**
A: The guest's home directory is set to the sandbox workspace. While they have shell access for VS Code compatibility, they don't have administrator/root privileges and their default workspace is the isolated sandbox.

**Q: Does the guest get root/admin access?**
A: No. The guest account is a standard user with no elevated privileges.

**Q: Can I host and connect at the same time?**
A: Technically yes, but it's not recommended. Each mode is designed for one role per session.

**Q: What happens if I lose internet while hosting?**
A: The Ngrok tunnel will disconnect. Connected users will be dropped. When your internet returns, you'll need to restart Host Mode to get a new tunnel URL.

**Q: Can multiple users connect at the same time?**
A: Yes, multiple SSH sessions can connect using the same credentials. All users share the same sandbox.

**Q: Is the virtual disk data persistent between sessions?**
A: Yes, if you choose to reuse an existing setup. The virtual disk file persists on your hard drive until you run Terminate.

**Q: How do I change the sandbox size after setup?**
A: Run Terminate to clean up, then re-run Host Mode with a new size.

**Q: Does this work on macOS?**
A: The Host Mode is designed for Windows and Linux. User Mode (client) works on macOS since it only modifies the SSH config file. Full macOS Host support may be added in a future version.

---

## 12. Uninstalling

### Quick Cleanup

Run option **[3] TERMINATE** from the main menu. This removes:
- The virtual disk file
- The guest user account
- SSH jail configuration
- Firewall rules

### Full Removal

After running Terminate:

1. **Delete the project folder** containing Wiz Island
2. **Optionally uninstall** the auto-installed dependencies:

   **Windows:**
   ```
   winget uninstall Ngrok.Ngrok
   ```

   **Linux:**
   ```bash
   sudo rm /usr/local/bin/ngrok
   sudo apt-get remove openssh-server  # Only if you don't need SSH
   ```

3. **Remove log files** in the `logs/` directory

---

*Wiz Island v1.1.0 - Serverless P2P SSH Tunneling Tool*
