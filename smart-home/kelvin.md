# Kelvin: self-hosted control for Cozytouch radiators

Self-hosted web app for Sauter, Atlantic and Thermor electric radiators on Cozytouch, with the Linky meter's consumption priced in euros. One Docker container, a PWA on the phone, and a read-only MCP server so Claude can answer questions about the heating bill.

Source: <https://github.com/lborruto/kelvin>

![Kelvin's home screen: each room with its temperature, alerts, this month's cost and today's schedule](https://raw.githubusercontent.com/lborruto/kelvin/main/docs/screenshots/home.webp)

## Why build this

The Cozytouch app controls the radiators but says nothing about what they cost, and the Enedis and supplier sites show the bill but not which room spent it. Home Assistant can bridge the two, but that is a whole platform to run for one job.

Kelvin does that one job:

- See every room and change it in one tap, with the change counted as done only when the radiator confirms it.
- Edit the weekly programme as an agenda, and send it only when you press « Envoyer ».
- Price the Linky data with your own tariff (Base, HC/HP or Tempo), split by room using the radiators' own meters.
- Turn the house down while you are away, with or without a return date.

## How it works

```
Phone / browser (SvelteKit PWA, French or English)
    │
    ▼
[FastAPI backend] ── SQLite in one data volume
    │
    ├─ Overkiz cloud (the Cozytouch app's API): rooms, setpoints, programmes, radiator kWh
    ├─ MyElectricalData: Linky daily and half-hour data, Tempo colours, EcoWatt
    ├─ Open-Meteo (optional): AROME / ARPEGE / ERA5-Land outdoor temperature
    └─ /mcp: read-only MCP server for Claude and other clients
```

### Key choices

- **Log in with the Cozytouch account.** No API key to request: the first login makes the account the home's owner, and the household shares it.
- **Confirmed, not assumed.** Every command is tracked per radiator until the device reports the new state. An offline radiator doesn't fail the whole command.
- **The radiators' rules are enforced up front.** Sauter radiators refuse an Éco setting less than 2 °C below Confort and only hold programme times on 30-minute steps. Kelvin blocks these changes in the app before sending them, so the radiator never answers with a vague refusal.
- **Costs say where they come from.** Each figure is marked as measured, computed from the tariff, or estimated, and partial coverage is shown, never hidden.
- **Weather-normalised view.** A regression of daily kWh on heating degree days gives the base load, the cost of each degree colder, per room, and the next 7 days' cost with a range.
- **Read-only MCP.** Claude can analyse a month, plan a red Tempo day or review a programme, but it can never change a radiator. Proposals are applied by a person, in the app.

## How to run it

```bash
git clone https://github.com/lborruto/kelvin.git && cd kelvin
cp .env.example .env
docker compose up -d --build
```

Open <http://localhost:8070> and log in with the Cozytouch app's email and password. For energy and costs, add a free [MyElectricalData](https://www.myelectricaldata.fr) token in **Réglages › Linky**.

To try it without radiators, run the built-in simulator (`KELVIN_FAKE=1`), an invented home with demo data. The [README](https://github.com/lborruto/kelvin#get-started) has the commands, the HTTPS reverse-proxy setup and the backup steps.

Keep it on the home network or a VPN: Kelvin is not made to face the internet.
