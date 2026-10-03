import ipaddress
import socket


def discover_local_ips() -> list[str]:
    """Return useful local IPv4 addresses without contacting the internet."""
    candidates: set[str] = set()
    route_address: str | None = None
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            candidates.add(result[4][0])
    except OSError:
        pass

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Selecting a route does not send traffic, and works while offline.
        sock.connect(("192.0.2.1", 80))
        route_address = sock.getsockname()[0]
        candidates.add(route_address)
    except OSError:
        pass
    finally:
        sock.close()

    usable: list[str] = []
    for candidate in candidates:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if not address.is_loopback and not address.is_link_local and address.version == 4:
            usable.append(candidate)
    # Prefer the default network route, not a numerically earlier VPN adapter.
    return sorted(set(usable), key=lambda item: (
        item != route_address,
        not ipaddress.ip_address(item).is_private,
        tuple(int(part) for part in item.split(".")),
    ))


def discover_local_ip() -> str:
    """Best-effort primary LAN address discovery."""
    addresses = discover_local_ips()
    return addresses[0] if addresses else "127.0.0.1"
