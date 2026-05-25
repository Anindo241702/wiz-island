# Wiz Island - User Manual

**Version 1.2.0**

A comprehensive guide for new users to set up, configure, and use Wiz Island for peer-to-peer SSH tunneling.

---

## Table of Contents

1. [What is Wiz Island?](#1-what-is-wiz-island)
2. [System Requirements](#2-system-requirements)
3. [Installation](#3-installation)
   - [Windows Installation](#31-windows-installation)
   - [Linux Installation](#32-linux-installation-ubuntudebian)
   - [Manual Installation](#33-manual-installation)
4. [Tunnel Provider (Pinggy)](#4-tunnel-provider-pinggy)
5. [Using Wiz Island](#5-using-wiz-island)
   - [Launching the Application](#51-launching-the-application)
   - [Host Mode](#52-host-mode-sharing-your-machine)
   - [User Mode](#53-user-mode-connecting-to-a-host)
   - [Terminate / Panic Button](#54-terminate--panic-button)
6. [The Host Dashboard](#6-the-host-dashboard)
7. [Connecting via VS Code](#7-connecting-via-vs-code)
8. [Using the Host's GPU, CPU, and Storage](#8-using-the-hosts-gpu-cpu-and-storage-for-coders)
9. [Command-Line Arguments](#9-command-line-arguments)
10. [Troubleshooting](#10-troubleshooting)
11. [Security Considerations](#11-security-considerations)
12. [FAQ](#12-faq)
13. [Uninstalling](#13-uninstalling)

---

## 1. What is Wiz Island?

Wiz Island is a **serverless, peer-to-peer CLI tool** that allows you to securely share your computer's resources (CPU, GPU, RAM, and storage) with another person over an SSH tunnel, without needing a dedicated server.

**How it works:**
- The **Host** runs Wiz Island on their machine, which creates an isolated sandbox environment and opens a secure tunnel via Pinggy.
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
| **Internet**  | Required for Pinggy tunnel                     |
| **Privileges**| Administrator (Windows) or root/sudo (Linux)   |

### Software Dependencies (Auto-Installed)

These are installed automatically by the setup scripts:

- **Python 3.10+** — Core application runtime
- **OpenSSH Server** — SSH connectivity
- **OpenSSH Client** — Required for Pinggy tunnel
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
   - Ensure OpenSSH Client is available (for Pinggy tunnel)
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
   - Ensure SSH client is available (for Pinggy tunnel)
   - Configure firewall rules via `ufw` (if available)
   - Install Python dependencies (`psutil`)
   - Launch the Wiz Island CLI

> **Supported architectures:** x86_64 (amd64), aarch64 (arm64), armv7l (arm), i686 (386)

### 3.3 Manual Installation

If you prefer to install dependencies yourself:

1. Install Python 3.10+ from [python.org](https://python.org)
2. Install OpenSSH Server for your platform
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Launch the application:
   ```bash
   python src/main.py        # Windows
   python3 src/main.py       # Linux
   ```

---

## 4. Tunnel Provider (Pinggy)

Wiz Island uses [Pinggy](https://pinggy.io) to create secure TCP tunnels. **No account or sign-up is required** — the tunnel is established via a standard SSH command.

Pinggy's free tier provides:
- Free TCP tunnels with randomly assigned URLs
- No authentication tokens needed
- Works through standard SSH (port 443)

> **Note:** Free tunnels have a session time limit. If the tunnel disconnects, simply restart Host Mode to get a new tunnel URL.

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

#### Step 1: Guest Username & Max Coders

```
  Guest username (press Enter for 'WizGuest'): devteam
  Max coders allowed (press Enter for unlimited): 5
```

You can set a custom guest username or press Enter to keep the default. You can also set how many coders can connect simultaneously.

#### Step 2: Storage Quota

```
  Enter storage quota in GB (e.g., 10): 10
```

Enter how much disk space to allocate for the guest sandbox. This creates an isolated virtual disk:
- **Windows:** Creates an expandable VHDX file mounted as drive `X:\`
- **Linux:** Creates an EXT4 disk image mounted at `/mnt/wizsandbox`

> **Tip:** Start with a small quota (5-10 GB). The virtual disk is expandable.

If a previous setup is detected, you'll be asked whether to reuse it or start fresh.

#### Step 3: Tunnel Creation

The application automatically starts a Pinggy TCP tunnel on port 22 (SSH) via SSH. No account or token is needed. This typically takes 5-10 seconds.

#### Step 4: Dashboard

Once the tunnel is established, a real-time dashboard appears:

```
  ============================================================
   WIZ ISLAND - HOST DASHBOARD
  ============================================================

   TUNNEL URL       : tcp://rnuap-xxx.a.free.pinggy.link:12345
   SSH Command      : ssh wizguest@rnuap-xxx.a.free.pinggy.link -p 12345
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
   Paste the tunnel connection string: tcp://rnuap-xxx.a.free.pinggy.link:12345
   ```
   Accepted formats:
   - `tcp://rnuap-xxx.a.free.pinggy.link:12345`
   - `rnuap-xxx.a.free.pinggy.link:12345`
   - `ssh wizguest@rnuap-xxx.a.free.pinggy.link -p 12345`

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
   ssh wizguest@rnuap-xxx.a.free.pinggy.link -p 12345
   ```

#### Cleaning SSH Config

Select **[2] Clean/Remove WizIsland SSH Config** to remove the WizIsland entry from your SSH config file. This is useful when you're done with a session.

### 5.4 Terminate / Panic Button

Select **[3] TERMINATE** from the main menu (or press `x` + Enter while the dashboard is running).

This performs a complete cleanup:

1. **Stops the Pinggy tunnel** — No more external connections
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
| **Tunnel URL** | The public Pinggy TCP address for connections |
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
- The **Explorer** panel shows the Host's sandbox filesystem — drag & drop files to upload
- The **Terminal** runs on the Host machine — PowerShell, Git Bash, or cmd (Windows), bash (Linux)
- You have full access to the Host's CPU, RAM, GPU, and storage for builds and tasks
- File editing happens locally; saves are synced to the Host instantly
- You can install VS Code extensions on the remote side for full IDE features
- Python, Node.js, compilers, and other tools installed on the Host are available
- Create virtual environments, install packages, run dev servers

### Port Forwarding (Dev Servers)

When you run a dev server in the VS Code terminal (e.g., `npm run dev`, `flask run`), VS Code automatically detects the open port and offers to forward it. Click "Open in Browser" to view the app in **your local browser**.

You can also manually forward ports via the **Ports** panel in VS Code (`Ctrl+Shift+P` → "Ports: Focus on Ports View").

Manual port forwarding from terminal:
```bash
# Forward host's port 3000 to your local port 3000
ssh -L 3000:localhost:3000 WizIsland
```

---

## 8. Using the Host's GPU, CPU, and Storage (For Coders)

Once connected via VS Code Remote-SSH (or a regular SSH terminal), you are running commands **directly on the Host machine**. Everything executes using the Host's hardware.

### Uploading Code

**Via VS Code (drag & drop):**
1. Open the Explorer panel (left sidebar) in VS Code
2. Drag your files/folders from your local machine into the Explorer — they upload to the Host's sandbox

**Via VS Code Terminal:**
```bash
# You're already on the Host machine in the terminal
# Create a project folder
mkdir myproject && cd myproject
```

**Via SCP (from your local machine):**
```bash
# From your local terminal (not VS Code):
scp -P <port> myfile.py WizIsland:~/myfile.py
scp -r -P <port> ./myproject WizIsland:~/myproject
```

### Running Code on the Host's CPU

The terminal in VS Code runs on the Host. Any command you type executes on the Host's CPU:

```bash
# Python
python3 script.py

# Node.js
node app.js

# C/C++
gcc -o program main.c && ./program
g++ -O2 -o program main.cpp && ./program

# Java
javac Main.java && java Main

# Run a build
make -j$(nproc)    # Uses all Host CPU cores
```

### Using the Host's GPU

If the Host has an NVIDIA GPU with CUDA installed:

```bash
# Check GPU availability
nvidia-smi

# Run CUDA/PyTorch code
python3 -c "import torch; print(torch.cuda.is_available())"

# Train a model
python3 train.py --device cuda

# Compile CUDA code
nvcc -o gpu_program gpu_kernel.cu && ./gpu_program
```

The GPU is directly accessible — no extra configuration needed. Whatever GPU drivers and toolkits the Host has installed are available to you.

### Storage

Your files are stored in the Host's sandbox:
- **Windows hosts:** `X:\` drive
- **Linux hosts:** `/mnt/wizsandbox/workspace`

The sandbox size is set by the Host during setup. Check available space:
```bash
df -h .           # Linux
dir               # Windows
```

### Multi-Coder Collaboration

Multiple coders can connect simultaneously using the same credentials:
- All coders share the same sandbox filesystem
- Each coder gets their own terminal session
- Files saved by one coder are immediately visible to others
- The Host dashboard shows how many coders are connected

**Tips for teams:**
- Create separate folders per coder: `mkdir /workspace/alice`, `mkdir /workspace/bob`
- Use `git` for version control within the sandbox
- Communicate about which files you're editing to avoid conflicts

---

## 9. Command-Line Arguments

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

## 10. Troubleshooting

### Common Issues

#### "Tunnel process exited unexpectedly"
- **Cause:** Network issue or SSH client problem
- **Fix:** Check your internet connection. Ensure the SSH client is installed and working. Ensure no firewall is blocking outbound connections on port 443.

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
- **Cause:** The connection counter checks port 22 directly; tunneled traffic arrives on a different port
- **Fix:** This is expected behavior. The counter tracks direct SSH connections. Your connection through the tunnel is still active.

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

## 11. Security Considerations

### What Wiz Island Does for Security

- **Isolated Sandbox:** Guest users start in an isolated virtual disk workspace
- **SSH Configuration:** The guest account is restricted via `sshd_config` Match User rules
- **No Sudo Access:** The guest account has no administrator/root privileges
- **Random Passwords:** A new secure password is generated for each session
- **Encrypted Tunnel:** All traffic goes through Pinggy's SSH-encrypted TCP tunnel
- **Panic Button:** Instant full cleanup at any time

### What You Should Be Aware Of

- **Resource Sharing:** The guest has access to your CPU, RAM, and GPU while connected. Monitor usage via the dashboard.
- **Password Sharing:** Only share the guest password with people you trust.
- **Network Exposure:** While the Pinggy tunnel is active, anyone with the URL and password can attempt to connect.
- **Session Duration:** Don't leave a session running indefinitely without monitoring.

### Best Practices

1. Only share connection details with trusted individuals
2. Monitor the dashboard for unexpected connections
3. Use the Panic Button immediately if you notice suspicious activity
4. Run Terminate when you're done hosting — don't leave the tunnel open
5. Check `logs/wiz_island.log` periodically for unusual activity

---

## 12. FAQ

**Q: Is Wiz Island free to use?**
A: Yes. Wiz Island is completely free. It uses Pinggy's free tier for tunneling, which requires no account or payment.

**Q: Can the guest access my personal files?**
A: The guest's home directory is set to the sandbox workspace. While they have shell access for VS Code compatibility, they don't have administrator/root privileges and their default workspace is the isolated sandbox.

**Q: Does the guest get root/admin access?**
A: No. The guest account is a standard user with no elevated privileges.

**Q: Can I host and connect at the same time?**
A: Technically yes, but it's not recommended. Each mode is designed for one role per session.

**Q: What happens if I lose internet while hosting?**
A: The Pinggy tunnel will disconnect. Connected users will be dropped. When your internet returns, you'll need to restart Host Mode to get a new tunnel URL.

**Q: Can multiple users connect at the same time?**
A: Yes, multiple SSH sessions can connect using the same credentials. All users share the same sandbox.

**Q: Is the virtual disk data persistent between sessions?**
A: Yes, if you choose to reuse an existing setup. The virtual disk file persists on your hard drive until you run Terminate.

**Q: How do I change the sandbox size after setup?**
A: Run Terminate to clean up, then re-run Host Mode with a new size.

**Q: Does this work on macOS?**
A: The Host Mode is designed for Windows and Linux. User Mode (client) works on macOS since it only modifies the SSH config file. Full macOS Host support may be added in a future version.

---

## 13. Uninstalling

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

   **Linux:**
   ```bash
   sudo apt-get remove openssh-server  # Only if you don't need SSH
   ```

3. **Remove log files** in the `logs/` directory

---

*Wiz Island v1.2.0 - Serverless P2P SSH Tunneling Tool*
