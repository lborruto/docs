# Twingate in Docker

Twingate provides zero-trust remote access to the home network. No port forwarding, no VPN server to maintain -- just install the Twingate client on your devices and access your services from anywhere.

## Docker Compose

```yaml
twingate:
  image: twingate/connector:1
  container_name: twingate-tall-ostrich
  environment:
    TWINGATE_NETWORK: lucab
    TWINGATE_ACCESS_TOKEN: <from-twingate-admin>
    TWINGATE_REFRESH_TOKEN: <from-twingate-admin>
    TWINGATE_LABEL_HOSTNAME: debian-server
    TWINGATE_LABEL_DEPLOYED_BY: docker
  sysctls:
    net.ipv4.ping_group_range: "0 2147483647"
  pull_policy: always
  restart: unless-stopped
```

## How It Works

1. The Twingate connector runs on the home server and establishes an outbound connection to Twingate's relay network
2. Your devices (phone, laptop) run the Twingate client
3. When you access `homelab.internal:8080` from outside, the client routes traffic through Twingate's relay to the connector, which forwards it to the local service
4. No inbound ports needed on the router

## Setup

1. Create a free account at [twingate.com](https://www.twingate.com/)
2. Create a Remote Network and add a Connector
3. Twingate gives you the `ACCESS_TOKEN` and `REFRESH_TOKEN`
4. Define Resources (e.g. `homelab.internal` or a whole CIDR range) to control what's accessible
5. Install the Twingate client on your devices

## Why Not a VPN?

- No need to open/forward any ports on the router
- Per-resource access control (not all-or-nothing like a VPN)
- Works through NAT and firewalls without configuration
- Free for up to 5 users
