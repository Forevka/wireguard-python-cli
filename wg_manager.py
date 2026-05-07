#!/usr/bin/env python3
"""
WireGuard Manager - CLI tool for managing WireGuard peers on a VPS.

Requirements:
    pip install typer rich

Usage:
    python wg_manager.py list
    python wg_manager.py add <name>
    python wg_manager.py remove <name>
    python wg_manager.py show <name>
    python wg_manager.py qr <name>
"""

import subprocess
import sys
import time
from pathlib import Path

try:
    import typer
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.panel import Panel
    from rich.prompt import Confirm
    from rich.syntax import Syntax
except ImportError:
    print("Missing dependencies. Run: pip install typer rich")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────

WG_IFACE   = "wg0"
WG_DIR     = Path("/etc/wireguard")
WG_CONF    = WG_DIR / f"{WG_IFACE}.conf"
CLIENTS    = WG_DIR / "clients"
SERVER_PUB = WG_DIR / "server_public.key"
VPS_PORT   = 51820

# ── App setup ─────────────────────────────────────────────────────────────────

app     = typer.Typer(help="WireGuard peer manager", no_args_is_help=True)
console = Console()

# ── Helpers ───────────────────────────────────────────────────────────────────

def require_root() -> None:
    import os
    if os.geteuid() != 0:
        console.print("[bold red]Error:[/] This script must be run as root.")
        raise typer.Exit(1)

def run(cmd: str, capture: bool = True) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    return result.stdout.strip() if capture else ""

def wg_genkey() -> tuple[str, str]:
    priv = run("wg genkey")
    pub  = run(f"echo '{priv}' | wg pubkey")
    return priv, pub

def get_server_pub() -> str:
    if not SERVER_PUB.exists():
        console.print(f"[red]Server public key not found at {SERVER_PUB}[/]")
        raise typer.Exit(1)
    return SERVER_PUB.read_text().strip()

def get_vps_ip() -> str:
    ip = run("curl -4 -s ifconfig.me")
    if not ip:
        console.print("[red]Could not detect VPS IP.[/]")
        raise typer.Exit(1)
    return ip

def next_free_ip() -> str:
    used = set()
    if WG_CONF.exists():
        for line in WG_CONF.read_text().splitlines():
            line = line.strip()
            if line.startswith("AllowedIPs"):
                # e.g. AllowedIPs = 10.0.0.3/32
                parts = line.split("=", 1)
                if len(parts) == 2:
                    ip = parts[1].strip().split("/")[0]
                    used.add(ip)
    for i in range(2, 255):
        candidate = f"10.0.0.{i}"
        if candidate not in used:
            return candidate
    console.print("[red]No free IPs available in 10.0.0.0/24.[/]")
    raise typer.Exit(1)

def get_handshakes() -> dict[str, int]:
    """Returns {pubkey: unix_timestamp} for all peers."""
    output = run(f"wg show {WG_IFACE} latest-handshakes")
    result = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2:
            result[parts[0]] = int(parts[1])
    return result

def format_handshake(ts: int) -> str:
    if ts == 0:
        return "[yellow]Never[/]"
    ago = int(time.time()) - ts
    if ago < 60:
        return f"[green]{ago}s ago[/]"
    elif ago < 3600:
        return f"[green]{ago // 60}m ago[/]"
    elif ago < 86400:
        return f"[yellow]{ago // 3600}h ago[/]"
    return f"[red]{ago // 86400}d ago[/]"

def get_clients() -> list[Path]:
    if not CLIENTS.exists():
        return []
    return sorted(CLIENTS.glob("*.conf"))

def remove_peer_from_conf(pubkey: str, name: str) -> None:
    """Remove a [Peer] block from wg0.conf by pubkey."""
    text = WG_CONF.read_text()
    lines = text.splitlines(keepends=True)

    output = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == "[Peer]":
            block = [lines[i]]
            j = i + 1
            found = False
            while j < len(lines) and not lines[j].strip().startswith("["):
                block.append(lines[j])
                if lines[j].strip() == f"PublicKey = {pubkey}":
                    found = True
                j += 1
            if found:
                # trim trailing blank lines from output before this block
                while output and output[-1].strip() == "":
                    output.pop()
                # skip comment line before [Peer] if it's a name comment
                if output and output[-1].strip() == f"# {name}":
                    output.pop()
                i = j
                continue
            else:
                output.extend(block)
                i = j
                continue
        output.append(lines[i])
        i += 1

    WG_CONF.write_text("".join(output))

def client_config_text(priv: str, ip: str, server_pub: str, vps_ip: str) -> str:
    return (
        f"[Interface]\n"
        f"PrivateKey = {priv}\n"
        f"Address = {ip}/24\n"
        f"DNS = 1.1.1.1\n\n"
        f"[Peer]\n"
        f"PublicKey = {server_pub}\n"
        f"Endpoint = {vps_ip}:{VPS_PORT}\n"
        f"AllowedIPs = 0.0.0.0/0\n"
        f"PersistentKeepalive = 25\n"
    )

# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def list():
    """List all clients and their connection status."""
    require_root()

    clients = get_clients()

    if not clients:
        console.print(Panel(
            "[yellow]No clients configured yet.[/]\n\n"
            "Add one with: [bold]python wg_manager.py add <name>[/]",
            title="WireGuard Peers",
            border_style="cyan"
        ))
        return

    handshakes = get_handshakes()

    table = Table(
        title="WireGuard Peers",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Name",           style="bold white", no_wrap=True)
    table.add_column("IP",             style="white")
    table.add_column("Last Handshake", style="white")
    table.add_column("Public Key",     style="dim white", no_wrap=True)

    for conf_path in clients:
        name = conf_path.stem
        pub_path = CLIENTS / f"{name}.pub"

        ip_line = next(
            (l for l in conf_path.read_text().splitlines() if l.startswith("Address")), ""
        )
        ip = ip_line.split("=", 1)[1].strip().split("/")[0] if ip_line else "?"

        if pub_path.exists():
            pub = pub_path.read_text().strip()
            ts = handshakes.get(pub, 0)
            handshake_str = format_handshake(ts)
            short_pub = pub[:24] + "…"
        else:
            handshake_str = "[red]unknown[/]"
            short_pub = "?"

        table.add_row(name, ip, handshake_str, short_pub)

    console.print(table)


@app.command()
def add(name: str = typer.Argument(..., help="Client name (e.g. 'phone', 'laptop')")):
    """Add a new WireGuard client."""
    require_root()

    CLIENTS.mkdir(parents=True, exist_ok=True)

    conf_path = CLIENTS / f"{name}.conf"
    if conf_path.exists():
        console.print(f"[red]Client '{name}' already exists.[/]")
        raise typer.Exit(1)

    console.print(f"[cyan]Generating keys for[/] [bold]{name}[/]…")

    priv, pub     = wg_genkey()
    ip            = next_free_ip()
    server_pub    = get_server_pub()
    vps_ip        = get_vps_ip()
    config_text   = client_config_text(priv, ip, server_pub, vps_ip)

    # Save client files
    conf_path.write_text(config_text)
    (CLIENTS / f"{name}.pub").write_text(pub)

    # Add peer to running WireGuard
    run(f"wg set {WG_IFACE} peer {pub} allowed-ips {ip}/32")

    # Persist in wg0.conf
    with WG_CONF.open("a") as f:
        f.write(f"\n[Peer]\n# {name}\nPublicKey = {pub}\nAllowedIPs = {ip}/32\n")

    console.print(f"\n[green]✓ Client [bold]{name}[/] created with IP [bold]{ip}[/][/]\n")
    console.print(Syntax(config_text, "ini", theme="monokai", line_numbers=False))
    console.print(
        f"\n[dim]Config saved to:[/] {conf_path}\n"
        f"[dim]Show QR code:[/]    [bold]python wg_manager.py qr {name}[/]"
    )


@app.command()
def remove(name: str = typer.Argument(..., help="Client name to remove")):
    """Remove a WireGuard client."""
    require_root()

    pub_path  = CLIENTS / f"{name}.pub"
    conf_path = CLIENTS / f"{name}.conf"

    if not pub_path.exists():
        console.print(f"[red]Client '{name}' not found.[/]")
        raise typer.Exit(1)

    if not Confirm.ask(f"[yellow]Remove client '[bold]{name}[/]'?[/]"):
        raise typer.Exit(0)

    pub = pub_path.read_text().strip()

    # Remove from live WireGuard
    run(f"wg set {WG_IFACE} peer {pub} remove")

    # Remove from wg0.conf
    remove_peer_from_conf(pub, name)

    # Remove client files
    pub_path.unlink(missing_ok=True)
    conf_path.unlink(missing_ok=True)

    console.print(f"[green]✓ Client '[bold]{name}[/]' removed.[/]")


@app.command()
def show(name: str = typer.Argument(..., help="Client name to show config for")):
    """Print the config for a client (to copy/paste)."""
    require_root()

    conf_path = CLIENTS / f"{name}.conf"
    if not conf_path.exists():
        console.print(f"[red]Client '{name}' not found.[/]")
        raise typer.Exit(1)

    console.print(Syntax(conf_path.read_text(), "ini", theme="monokai", line_numbers=False))


@app.command()
def qr(name: str = typer.Argument(..., help="Client name to generate QR code for")):
    """Show a QR code for a client (scan with WireGuard mobile app)."""
    require_root()

    conf_path = CLIENTS / f"{name}.conf"
    if not conf_path.exists():
        console.print(f"[red]Client '{name}' not found.[/]")
        raise typer.Exit(1)

    if subprocess.run("which qrencode", shell=True, capture_output=True).returncode != 0:
        console.print("[yellow]Installing qrencode…[/]")
        run("apt install -y qrencode", capture=False)

    console.print(f"\n[cyan]QR code for [bold]{name}[/] (scan with WireGuard app):[/]\n")
    subprocess.run(f"qrencode -t ansiutf8 < {conf_path}", shell=True)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()