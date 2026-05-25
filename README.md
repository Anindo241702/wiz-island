# Wiz Island

**Serverless Peer-to-Peer SSH Tunneling Tool** | v1.1.0

Wiz Island is a CLI tool written in Python that allows a client to connect securely to a Host machine's CPU/GPU/RAM/Storage over an SSH tunnel via Pinggy. The tool configures everything automatically on both Windows and Debian-based Linux (Ubuntu/Kali). No accounts or API keys required.

> **New to Wiz Island?** Read the [**User Manual (MANUAL.md)**](MANUAL.md) for step-by-step instructions with screenshots.

## Architecture

```
 HOST MACHINE                           CLIENT MACHINE
 +------------------+                  +------------------+
 |  Wiz Island CLI  |                  |  Wiz Island CLI  |
 |  (Host Mode)     |                  |  (User Mode)     |
 |                  |                  |                  |
 |  +------------+  |  Pinggy TCP     |  SSH Config      |
 |  | Sandbox    |<-|--  Tunnel  -----|->Injection       |
 |  | (VHDX/EXT4)|  |   (Port 22)    |                  |
 |  +------------+  |                  |  VS Code         |
 |                  |                  |  Remote-SSH      |
 |  SSH Server      |                  |                  |
 |  Guest Account   |                  |                  |
 +------------------+                  +------------------+
```

- **Host Machine**: Becomes the SSH server, spins up a secure Pinggy TCP tunnel, and isolates user workspaces in a virtual disk.
- **Client Machine**: Inputs the connection string, updates their local SSH config, and connects via terminal or VS Code.

## Project Structure

```
wiz-island/
├── setup.bat          # Windows Admin Auto-Installer
├── setup.sh           # Linux Sudo Auto-Installer
├── requirements.txt   # Python dependencies (psutil)
├── README.md          # This file
├── MANUAL.md          # Comprehensive user manual
├── LICENSE            # MIT License
└── src/
    ├── __init__.py
    ├── main.py        # Core CLI Entrypoint (Interactive Menu + CLI Args)
    ├── host.py        # Host-side orchestration & Real-Time Dashboard
    ├── client.py      # Client-side SSH configuration injection
    └── storage.py     # Platform-specific storage virtualization
```

## Requirements

- **Python 3.10+**
- **No accounts needed** — uses [Pinggy](https://pinggy.io) free tunnel (via SSH)
- **Administrator/root** privileges (for Host Mode)

## Quick Start

### Windows

1. Right-click `setup.bat` and select **Run as Administrator**
2. The script auto-installs Python, OpenSSH Server/Client, and firewall rules
3. The Wiz Island CLI launches automatically

### Linux (Ubuntu/Debian)

```bash
chmod +x setup.sh
sudo ./setup.sh
```

### Manual Launch

```bash
pip install -r requirements.txt
python src/main.py
```

### CLI Arguments

```bash
python src/main.py --version           # Show version
python src/main.py --mode host         # Skip menu, launch Host Mode
python src/main.py --mode user         # Skip menu, launch User Mode
python src/main.py --mode terminate    # Skip menu, run cleanup
```

## Features

| Feature | Description |
|---------|-------------|
| Auto-Install | Setup scripts install all dependencies automatically |
| Virtual Disk Sandbox | Isolated storage (VHDX on Windows, EXT4 on Linux) |
| SSH Jailing | Guest users are locked into the sandbox directory |
| Random Passwords | Secure passwords generated fresh each session |
| Real-Time Dashboard | Live CPU, RAM, disk, network metrics via psutil |
| Connection Testing | Client tests TCP connectivity before saving config |
| Panic Button | Instant full cleanup with one keypress |
| Signal Handling | Graceful shutdown on Ctrl+C / SIGTERM |
| Firewall Config | Automatic SSH port 22 firewall rules |
| Cross-Platform | Windows CMD and Linux terminal compatible UI |
| Logging | Detailed logs saved to `logs/wiz_island.log` |

## Platform Details

### Windows

| Feature | Implementation |
|---------|---------------|
| Virtual Disk | Expandable VHDX via diskpart (NTFS) |
| Mount Point | Drive X:\ |
| Guest User | WizGuest (standard local account) |
| Permissions | icacls (restricted to WizGuest + Admins) |
| SSH Config | sshd_config Match User + home dir restriction |
| Firewall | netsh advfirewall rule for port 22 |

### Linux

| Feature | Implementation |
|---------|---------------|
| Virtual Disk | EXT4 image via fallocate/dd |
| Mount Point | /mnt/wizsandbox |
| Guest User | wizguest (no sudo) |
| Permissions | root-owned chroot + user-owned workspace |
| SSH Config | sshd_config Match User + home dir restriction |
| Firewall | ufw allow 22/tcp |

## Security

- Guest accounts have **no administrator/root** privileges
- Virtual disks are **isolated** from the host filesystem
- Guest home directories are set to the **sandbox workspace**
- Passwords are **randomly generated** for each session (16 chars, mixed)
- The **Panic Button** provides immediate full cleanup
- All traffic is encrypted through Pinggy's SSH tunnel

## Documentation

- **[README.md](README.md)** — Quick reference (this file)
- **[MANUAL.md](MANUAL.md)** — Comprehensive user manual with troubleshooting
- **[LICENSE](LICENSE)** — MIT License

## License

MIT License - See [LICENSE](LICENSE) for details.
