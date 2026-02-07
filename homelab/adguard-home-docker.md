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

## Network Setup

Set the router's DHCP DNS server to `serverip` so all devices on the network automatically use AdGuard Home for DNS. This blocks ads network-wide without installing anything on individual devices.

## Volume Paths

- `/app-config/adguardhome/conf` -- configuration files
- `/app-config/adguardhome/work` -- runtime data
