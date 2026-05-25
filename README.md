# Wiz Island

**Serverless Peer-to-Peer SSH Tunneling Tool**

Wiz Island is a CLI tool written in Python that allows a client to connect securely to a Host machine's CPU/GPU/RAM/Storage over an SSH tunnel via Ngrok. The tool configures everything automatically on both Windows and Debian-based Linux (Ubuntu/Kali).

## Architecture

- **Host Machine**: Becomes the SSH server, spins up a secure Ngrok TCP tunnel, and isolates user workspaces.
- **Client Machine**: Inputs the connection string, updates their local VS Code SSH config, and connects.

## Project Structure

```
wiz-island/
├── setup.bat          # Windows Admin Auto-Installer
├── setup.sh           # Linux Sudo Auto-Installer
├── requirements.txt   # Python dependencies
├── README.md          # This file
└── src/
    ├── __init__.py
    ├── main.py        # Core CLI Entrypoint (Interactive Menu)
    ├── host.py        # Host-side orchestration & Dashboard
    ├── client.py      # Client-side SSH configuration injection
    └── storage.py     # Platform-specific storage virtualization
```

## Requirements

- **Python 3.10+**
- **Ngrok account** (free tier works) - [sign up here](https://ngrok.com/)
- **Administrator/root** privileges (for storage and SSH configuration)

## Quick Start

### Windows

1. Right-click `setup.bat` and select **Run as Administrator**
2. The script will automatically install Python, OpenSSH Server, and Ngrok if missing
3. The Wiz Island CLI will launch automatically

### Linux (Ubuntu/Debian)

```bash
chmod +x setup.sh
sudo ./setup.sh
```

The script will install Python3, pip, OpenSSH Server, and Ngrok if missing, then launch the CLI.

### Manual Launch (if dependencies are already installed)

```bash
pip install -r requirements.txt
python src/main.py
```

## Usage

### Host Mode (Option 1)

1. Select **[1] HOST MODE** from the main menu
2. Enter the desired storage quota in GB
3. Enter your Ngrok AuthToken (from [ngrok.com/dashboard](https://dashboard.ngrok.com/get-started/your-authtoken))
4. The tool will:
   - Create a virtual disk (VHDX on Windows, EXT4 image on Linux)
   - Create an isolated guest user account
   - Configure SSH jailing
   - Start an Ngrok TCP tunnel
   - Display a real-time dashboard with system metrics

### User Mode (Option 2)

1. Select **[2] USER MODE** from the main menu
2. Paste the Ngrok connection string provided by the Host (e.g., `tcp://0.tcp.ngrok.io:12345`)
3. The tool will update your SSH config and provide connection instructions for:
   - Terminal SSH
   - VS Code Remote-SSH

### Terminate / Panic Button (Option 3)

Immediately:
- Terminates the Ngrok tunnel
- Closes all active guest SSH sessions
- Unmounts virtual disks
- Deletes temporary guest accounts
- Restores the machine to its native state

## Platform Details

### Windows

| Feature | Implementation |
|---------|---------------|
| Virtual Disk | VHDX via diskpart (expandable, NTFS) |
| Mount Point | Drive X:\ |
| Guest User | WizGuest (standard local account) |
| Permissions | icacls (restricted to WizGuest + Admins) |
| SSH Jail | sshd_config Match User + ForceCommand |

### Linux

| Feature | Implementation |
|---------|---------------|
| Virtual Disk | EXT4 image via fallocate/dd |
| Mount Point | /mnt/wizsandbox |
| Guest User | wizguest (no sudo) |
| Permissions | chown + chmod 700 |
| SSH Jail | sshd_config ChrootDirectory |

## Logging

All operations are logged to `logs/wiz_island.log` with timestamps and severity levels. Check this file for debugging if anything goes wrong.

## Security Notes

- Guest accounts are created with restricted permissions
- Virtual disks are isolated from the host filesystem
- SSH sessions are jailed to the sandbox directory
- The Panic Button provides immediate cleanup
- StrictHostKeyChecking is disabled for client convenience (the connection goes through Ngrok's encrypted tunnel)

## License

This project is provided as-is for educational and personal use.
