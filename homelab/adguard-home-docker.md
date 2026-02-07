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
    - ./conf:/opt/adguardhome/conf
    - ./work:/opt/adguardhome/work
```

## Web UI

- Setup wizard (first run): `http://192.168.0.15:3000`
- Admin panel (after setup): `http://192.168.0.15:80`

## Ports

- **53 TCP/UDP** -- DNS server. This is where all network devices send their DNS queries.
- **80** -- Admin web interface
- **3000** -- Initial setup wizard (also kept open for alternative access)

## Network Setup

Set the router's DHCP DNS server to `192.168.0.15` so all devices on the network automatically use AdGuard Home for DNS. This blocks ads network-wide without installing anything on individual devices.

## Volume Paths

The config uses relative paths (`./conf` and `./work`) which resolve to `/app-config/conf/` and `/app-config/work/` since the compose file is in `/app-config/`.
