# wg-manager

A simple CLI tool for managing WireGuard peers on a VPS.

Built with [Typer](https://typer.tiangolo.com/) and [Rich](https://github.com/Textualize/rich).

## Requirements

- Python 3.10+
- WireGuard installed and configured on the server
- Root access

## Installation

```bash
make install
```

This creates a `.venv` virtual environment and installs all dependencies into it.

## Usage

All commands require root since they interact with WireGuard and `/etc/wireguard/`.

```bash
# List all peers and their connection status
make run ARGS='list'

# Add a new peer (generates keys, assigns IP, prints config)
make run ARGS='add phone'
make run ARGS='add laptop'

# Show config for a peer (to copy/paste into WireGuard app)
make run ARGS='show phone'

# Show QR code for a peer (scan with WireGuard mobile app)
make run ARGS='qr phone'

# Remove a peer (asks for confirmation)
make run ARGS='remove phone'
```

You can also invoke the script directly using the venv Python:

```bash
sudo .venv/bin/python wg_manager.py list
sudo .venv/bin/python wg_manager.py add laptop
```

## File structure

```
wg-manager/
├── wg_manager.py       # main script
├── requirements.txt    # Python dependencies
├── Makefile            # install / run / clean helpers
└── README.md
```

Client configs and keys are stored on the server at `/etc/wireguard/clients/`:

```
/etc/wireguard/clients/
├── phone.conf          # full client config (contains private key)
├── phone.pub           # client public key
├── laptop.conf
└── laptop.pub
```

## Adding a new device step by step

1. Run `make run ARGS='add <name>'`
2. Copy the printed config block
3. On **Windows/macOS** — open WireGuard app → Add Tunnel → paste config
4. On **Linux** — save to `/etc/wireguard/wg0.conf` and run `wg-quick up wg0`
5. On **Android/iOS** — run `make run ARGS='qr <name>'` and scan with the WireGuard app

## Notes

- IPs are auto-assigned starting from `10.0.0.2` (server is `10.0.0.1`)
- Removing a peer is live — no WireGuard restart needed
- The `list` command shows last handshake time so you can see which devices are actively connected