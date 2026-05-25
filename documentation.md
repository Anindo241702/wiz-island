# Wiz Island — Complete Project Documentation

**Version:** 1.2.0  
**License:** MIT  
**Platform:** Windows 10/11, Ubuntu/Debian Linux

---

## What Is Wiz Island?

Wiz Island is a **serverless, zero-configuration CLI tool** that turns any powerful computer into a shared development workstation — accessible from anywhere over the internet, through a secure SSH tunnel.

Think of it this way: you have a powerful PC in your office with a fast GPU, 32 GB of RAM, and a big SSD. You want your teammates (or yourself from home) to be able to connect to that machine, upload code, run builds, train models, and work as if they were sitting in front of it — all through VS Code or a terminal.

Wiz Island does exactly that with one command. No server setup. No cloud account. No monthly bill.

---

## Why Every Coder Needs This

### The Problem

- You have a powerful desktop/workstation at the office, but you're working from a laptop at home.
- Your team needs GPU compute for training ML models, but you can't afford cloud GPU instances for everyone.
- You want to pair-program remotely, but screen sharing is laggy and your partner can't actually run code on your machine.
- Setting up SSH servers, tunnels, firewalls, user accounts, and disk isolation manually is tedious and error-prone.

### The Solution

Wiz Island automates everything:

1. **One command** creates an isolated sandbox, a guest user, configures SSH, opens a tunnel.
2. **Share a connection string** — your teammate pastes it, and they're in.
3. **Full hardware access** — CPU, RAM, GPU, storage — through VS Code Remote-SSH or any terminal.
4. **No cloud, no server, no subscription** — direct peer-to-peer connection via [Pinggy](https://pinggy.io) free tunnel.
5. **Instant cleanup** — press one button and the machine returns to its original state.

---

## What Features Does It Have?

### Core Features

| Feature | Description |
|---------|-------------|
| **One-Click Setup** | `setup.bat` (Windows) or `setup.sh` (Linux) installs everything automatically |
| **Sandboxed Storage** | Isolated virtual disk (VHDX on Windows, EXT4 on Linux) — guest files don't touch your system |
| **Secure Guest Accounts** | Dedicated user with randomly generated 16-character password, no admin/root privileges |
| **Free TCP Tunnel** | Pinggy tunnel via SSH — no account, no API key, no credit card required |
| **VS Code Remote-SSH** | Full IDE experience with file editing, terminal, extensions, debugging |
| **Port Forwarding** | Run `npm run dev`, `flask run`, etc. and access the dev server from your local browser |
| **Real-Time Dashboard** | Live CPU, RAM, GPU, disk, and network monitoring on the host side |
| **Multi-Coder Support** | Multiple coders can connect simultaneously, with configurable limits |
| **Custom Usernames** | Host can set any guest username instead of the default |
| **Panic Button** | Instant full cleanup — stops tunnel, kills sessions, unmounts disk, deletes user |
| **Cross-Platform** | Works on Windows 10/11 and Ubuntu/Debian Linux |
| **CLI Arguments** | `--mode host`, `--mode user`, `--mode terminate` for automation |

### For Coders (What You Can Do Once Connected)

| Capability | How |
|-----------|-----|
| **Upload files** | Drag & drop in VS Code Explorer, or use `scp` |
| **Edit & save code** | VS Code editor with full IntelliSense, auto-save, and extensions |
| **Run any language** | Python, Node.js, C/C++, Java, Rust, Go — whatever is installed on the host |
| **Use the GPU** | `nvidia-smi`, PyTorch CUDA, TensorFlow GPU, CUDA compilation — all work directly |
| **Run dev servers** | `npm run dev`, `flask run`, `python manage.py runserver` — access from your local browser via port forwarding |
| **Create virtual environments** | `python -m venv .venv`, `conda create`, `nvm use` — full control |
| **Use any terminal** | PowerShell, Git Bash, cmd, bash — choose your shell |
| **Install packages** | `pip install`, `npm install`, `apt-get` (if host grants sudo) |
| **Use Git** | Clone repos, commit, push — full git workflow in the sandbox |
| **API keys & secrets** | Set environment variables in your session: `export API_KEY=xxx` |
| **Collaborate** | Multiple coders work on the same sandbox simultaneously |

### Port Forwarding (Dev Servers)

This is a critical feature for web developers. When you run a dev server on the host:

```bash
# On the host (via VS Code terminal):
npm run dev        # Starts on localhost:3000
flask run          # Starts on localhost:5000
python manage.py runserver  # Starts on localhost:8000
```

VS Code automatically detects the port and offers to forward it. You can then open `localhost:3000` in **your local browser** (on your own machine) and see the app running on the host's hardware. This works because SSH port forwarding is enabled.

You can also manually forward ports:
```bash
# From your local terminal:
ssh -L 3000:localhost:3000 WizIsland
```

### Virtual Environments

Full virtual environment support works out of the box:

```bash
# Python virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux
.venv\Scripts\activate      # Windows
pip install -r requirements.txt

# Node.js (nvm)
nvm install 20
nvm use 20
npm install

# Conda
conda create -n myenv python=3.11
conda activate myenv

# Next.js
npx create-next-app@latest myapp
cd myapp && npm run dev
```

### API Keys & Environment Variables

Set API keys in your session just like you would locally:

```bash
# Set for current session
export OPENAI_API_KEY="sk-..."
export DATABASE_URL="postgresql://..."

# Or create a .env file
echo 'API_KEY=your_key_here' > .env

# Python dotenv
pip install python-dotenv
```

These persist within your SSH session. For permanent storage, add them to your shell profile in the sandbox.

---

## How It Works (Architecture)

```
 HOST MACHINE                             CLIENT MACHINE
 +------------------------+              +------------------------+
 |  Wiz Island CLI        |              |  Wiz Island CLI        |
 |  (Host Mode)           |              |  (User Mode)           |
 |                        |              |                        |
 |  +------------------+  |  Pinggy TCP  |  SSH Config Injection  |
 |  | Sandbox          |<-|-- Tunnel ----|->                      |
 |  | (VHDX / EXT4)    |  |  (Port 22)  |  VS Code Remote-SSH    |
 |  | - Your code      |  |             |  - Full file editor    |
 |  | - Virtual envs   |  |             |  - Terminal access     |
 |  | - Git repos      |  |             |  - Port forwarding     |
 |  +------------------+  |             |  - Extensions          |
 |                        |              |                        |
 |  SSH Server            |              |  Or: ssh WizIsland     |
 |  Guest Account         |              |  Or: scp, sftp         |
 |  GPU / CPU / RAM       |              |                        |
 |  Real-Time Dashboard   |              |                        |
 +------------------------+              +------------------------+
```

1. **Host** runs Wiz Island → creates sandbox → creates guest user → opens tunnel
2. **Host** shares the connection string + password with the coder
3. **Coder** runs User Mode → pastes connection string → SSH config is auto-injected
4. **Coder** connects via VS Code Remote-SSH or `ssh WizIsland`
5. **Coder** works directly on host hardware — full CPU, GPU, RAM, storage access

---

## Why Is It Different?

| | Wiz Island | Cloud VMs (AWS, GCP) | Ngrok + Manual SSH | VS Code Live Share |
|---|---|---|---|---|
| **Cost** | Free | $50-500+/month | Free (HTTP only) | Free |
| **GPU Access** | Direct | Expensive | Manual setup | No |
| **Setup Time** | 2 minutes | 30+ minutes | 20+ minutes | Instant |
| **File System** | Full access | Full access | Full access | Limited |
| **Terminal** | Full shell | Full shell | Full shell | Read-only |
| **Port Forwarding** | Built-in | Manual | Paid for TCP | No |
| **Isolation** | Sandboxed | Full VM | None | N/A |
| **Cleanup** | One button | Manual | Manual | N/A |
| **Account Required** | No | Yes | Yes | Yes |
| **Runs Locally** | Yes | No (cloud) | Yes | Sort of |
| **Multi-User** | Yes | Per VM | Manual | Yes |

### Key Differentiators

1. **Zero accounts, zero cost** — No cloud account, no Pinggy account, no API keys. Completely free.
2. **Direct hardware access** — Your GPU, your CPU, your RAM. Not a virtual machine in the cloud — the real thing.
3. **Sandboxed by default** — Guest users are isolated in a virtual disk. Your personal files are protected.
4. **One-command setup** — Run the setup script, share the connection string. Done.
5. **VS Code native** — Not a web IDE, not a terminal multiplexer. Real VS Code with all extensions, IntelliSense, debugging, and port forwarding.
6. **Instant cleanup** — Panic button removes everything. No orphaned VMs or forgotten SSH keys.

---

## Project Structure

```
wiz-island/
├── setup.bat            # Windows bootstrapper (auto-installs everything)
├── setup.sh             # Linux bootstrapper (auto-installs everything)
├── requirements.txt     # Python dependencies (psutil)
├── README.md            # Quick reference
├── MANUAL.md            # Step-by-step user manual
├── documentation.md     # This file — full project documentation
├── LICENSE              # MIT License
└── src/
    ├── __init__.py
    ├── main.py          # CLI entrypoint (menu + argument parsing)
    ├── host.py          # Host mode: tunnel, dashboard, panic button
    ├── client.py        # User mode: SSH config injection
    └── storage.py       # Virtual disk, user accounts, SSH config, firewall
```

### Module Responsibilities

**main.py** — Entry point. Displays the interactive menu (Host Mode, User Mode, Terminate), parses CLI arguments (`--mode host/user/terminate`, `--version`), sets up logging.

**host.py** — Manages the host session lifecycle:
- Prompts for guest username and max coders
- Starts the Pinggy TCP tunnel via SSH subprocess
- Parses the dynamically generated tunnel URL from stdout
- Renders the real-time dashboard (flicker-free, cursor repositioning)
- Monitors CPU, RAM, GPU, disk, network via psutil
- Handles panic shutdown (stop tunnel, kill sessions, teardown storage)

**client.py** — Manages the client connection:
- Parses tunnel URL (supports `tcp://host:port`, `host:port`, `ssh user@host -p port`)
- Tests TCP connectivity before saving config
- Injects SSH config entry into `~/.ssh/config`
- Displays connection instructions for terminal and VS Code

**storage.py** — Platform-specific system operations:
- Creates virtual disks (VHDX via diskpart on Windows, EXT4 via fallocate on Linux)
- Creates guest user accounts with random passwords
- Sets file permissions (icacls on Windows, chown/chmod on Linux)
- Configures SSH jail (sshd_config Match User blocks)
- Sets default SSH shell to PowerShell on Windows
- Enables SSH port forwarding for dev server access
- Manages firewall rules (netsh on Windows, ufw on Linux)
- Handles full teardown and cleanup

---

## Security Model

### What Is Protected

- **File isolation** — Guest user's home directory is the sandbox virtual disk. They cannot navigate to your personal files by default.
- **No admin access** — Guest account has no sudo/administrator privileges.
- **Random passwords** — New 16-character password generated each session.
- **Encrypted traffic** — All data travels through SSH-encrypted tunnel.
- **Instant cleanup** — One-button teardown removes user, disk, SSH config, and firewall rules.

### What Is Shared

- **CPU, RAM, GPU** — The guest has access to the host's compute resources. Monitor usage via the dashboard.
- **Network** — The guest can access the internet from the host machine.
- **Installed software** — Whatever tools are installed on the host (Python, Node, compilers, CUDA) are available to the guest.

### Best Practices

1. Only share connection details with people you trust
2. Set a max coder limit to prevent unexpected connections
3. Monitor the dashboard for unusual activity
4. Use the Panic Button if anything looks wrong
5. Run Terminate when done — don't leave the tunnel open indefinitely

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Windows 10/11 or Ubuntu/Debian Linux |
| **Python** | 3.10+ |
| **RAM** | 2 GB minimum (4 GB+ recommended) |
| **Disk** | Enough free space for the sandbox |
| **Internet** | Required for the tunnel |
| **Privileges** | Administrator (Windows) or root/sudo (Linux) |

All other dependencies (OpenSSH, psutil) are installed automatically by the setup scripts.

---

## Quick Start

### Host (the person sharing their PC)

```bash
# Windows: right-click setup.bat → Run as Administrator
# Linux:
chmod +x setup.sh && sudo ./setup.sh
```

Select Host Mode → set guest username → set max coders → set storage quota → tunnel starts automatically → share the connection string and password with your coders.

### Coder (the person connecting)

```bash
pip install -r requirements.txt
python src/main.py
```

Select User Mode → Connect to Host → paste the connection string → connect via `ssh WizIsland` or VS Code Remote-SSH.

---

## Use Cases

1. **Remote GPU access** — Train ML models on your office workstation from your laptop at home
2. **Team collaboration** — Multiple coders working on the same codebase, same hardware
3. **Code review sessions** — Share your environment instantly for pair programming
4. **Build servers** — Offload heavy compilation to a powerful machine
5. **Teaching/workshops** — Instructor shares a pre-configured environment with students
6. **Freelance work** — Provide clients access to a sandboxed development environment
7. **Cross-platform testing** — Access a Windows machine from Linux or vice versa

---

## Tunnel Provider

Wiz Island uses [Pinggy](https://pinggy.io) for TCP tunneling:

- **Free** — No account, no API key, no credit card
- **SSH-based** — Uses standard SSH client (already installed on most systems)
- **TCP tunnels** — Direct TCP forwarding on port 22 for SSH
- **Dynamic URLs** — Each session gets a unique public URL
- **No installation** — Uses the SSH client that's already on your system

The tunnel command runs internally:
```
ssh -p 443 -R 0:localhost:22 tcp@a.pinggy.io
```

---

## Frequently Asked Questions

**Q: Is this really free?**  
A: Yes. Wiz Island is MIT-licensed open source. Pinggy's free tier provides the tunnel. No accounts or payments needed.

**Q: Can the guest access my personal files?**  
A: By default, no. The guest's home directory is set to the sandbox virtual disk. They don't have admin privileges and their default workspace is isolated.

**Q: Can I use this for production?**  
A: Wiz Island is designed for development and collaboration, not production hosting. Use it for coding, testing, and builds.

**Q: What if the tunnel disconnects?**  
A: Restart Host Mode to get a new tunnel URL. Connected users will need the new URL.

**Q: Can multiple coders connect at the same time?**  
A: Yes. All coders share the same credentials and sandbox. Set a max coder limit in Host Mode if needed.

**Q: Does this work with any IDE?**  
A: Any IDE that supports SSH remote development works — VS Code (recommended), JetBrains Gateway, Vim/Neovim over SSH, Emacs TRAMP, etc.

**Q: Can the coder install software on the host?**  
A: They can install software in the sandbox (pip install, npm install, etc.). System-wide installations require admin privileges which the guest doesn't have unless the host grants them.

**Q: What about Windows Defender or antivirus?**  
A: Wiz Island uses standard Windows system tools (diskpart, icacls, net user, OpenSSH). Some antivirus software may flag SSH tunneling. Add an exception if needed.

---

*Wiz Island v1.2.0 — Serverless P2P SSH Tunneling Tool*  
*Built for coders who need raw hardware access without the cloud.*
