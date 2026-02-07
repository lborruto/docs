# AdGuard Home in Docker

Network-wide DNS ad blocker. All devices on the network use this as their DNS server, blocking ads and trackers at the DNS level.

## Docker Compose

```yaml
adguardhome:
  image: adguard/adguardhome:latest
  container_name: adguardhome
  restart: unless-stopped
  ports:
    - 53:53/udp
    - 53:53/tcp
    - 80:80/tcp
    - 3000:3000/tcp
  volumes:
    - /app-config/adguardhome/conf:/opt/adguardhome/conf
    - /app-config/adguardhome/work:/opt/adguardhome/work
```

## Web UI

- Setup wizard (first run): `http://homelab.internal:3000`
- Admin panel (after setup): `http://homelab.internal`

## Ports

- **53 TCP/UDP** -- DNS server. This is where all network devices send their DNS queries.
- **80** -- Admin web interface
- **3000** -- Initial setup wizard (also kept open for alternative access)

## DNS Configuration

- **Upstream DNS:** `1.1.1.1` (Cloudflare)
- **Fallback DNS:** `1.0.0.1` (Cloudflare)

## Blocklists

Removed the default blocklist. Using [Hagezi](https://github.com/hagezi/dns-blocklists) lists instead:

- `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/pro.txt`
- `https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@latest/adblock/tif.txt`

## DNS Rewrites

- `homelab.internal` -> `192.168.x.xx`

## Network Setup

Set the router's DHCP DNS server to the server's IP so all devices on the network automatically use AdGuard Home for DNS. This blocks ads network-wide without installing anything on individual devices.

## Volume Paths

- `/app-config/adguardhome/conf` -- configuration files
- `/app-config/adguardhome/work` -- runtime data
