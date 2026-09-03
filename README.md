# IoT Honeypot Monitoring and Threat Analysis Platform

Production-quality academic defensive-security project that combines ESP32 telemetry, a Flask monitoring backend, SQLite storage, Socket.IO real-time updates, and Cowrie SSH honeypot activity in one dashboard.

## Architecture

```text
ESP32 Device -> HTTP POST -> Flask API -> SQLite Database -> Dashboard
Cowrie Honeypot -> cowrie.json -> Cowrie Parser -> Flask API -> Database -> Dashboard
```

## Folder Structure

```text
iot_honeypot/
├── app.py
├── config.py
├── database.py
├── models.py
├── requirements.txt
├── README.md
├── routes/
│   ├── api.py
│   └── dashboard.py
├── services/
│   ├── validation.py
│   ├── telemetry.py
│   └── cowrie_service.py
├── parser/
│   └── cowrie_parser.py
├── templates/
├── static/
├── logs/
└── migrations/
```

## Windows 11 Setup

Install Python 3.12 or newer from `python.org`, then open PowerShell:

```powershell
cd D:\project\iot-honeypot\iot_honeypot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:SECRET_KEY = "replace-with-a-long-random-secret"
flask --app app init-db
python app.py
```

Open `http://127.0.0.1:5000`.

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask and CSRF signing key | development fallback |
| `DATABASE_URL` | SQLAlchemy database URI | `sqlite:///instance/iot_honeypot.db` |
| `LOG_LEVEL` | Application log level | `INFO` |
| `COWRIE_LOG_PATH` | Default Cowrie JSON path | `logs/cowrie.json` |
| `SOCKETIO_ASYNC_MODE` | Socket.IO backend | `threading` |
| `FLASK_DEBUG` | Set `1` to enable Flask debug mode | `0` |

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Real-time Bootstrap dashboard |
| `GET` | `/health` | Service health check |
| `POST` | `/api/device` | Register or update an ESP32 device |
| `GET` | `/api/device` | List devices |
| `GET` | `/api/devices` | Compatibility alias for listing devices |
| `POST` | `/api/log` | Store ESP32 telemetry |
| `GET` | `/api/logs` | List telemetry; supports `source_ip`, `device_name`, `event_type` |
| `POST` | `/api/cowrie` | Store Cowrie JSON event, or parse a local file with `log_path` |
| `GET` | `/api/cowrie` | List Cowrie events; supports `source_ip` |
| `GET` | `/api/stats` | Dashboard counters and chart data |

All JSON endpoints validate input, return JSON responses, and use appropriate HTTP status codes.

## ESP32 Telemetry Tests

Boot event:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/log `
  -ContentType "application/json" `
  -Body '{"device_name":"ESP32_DEVKIT","event_type":"boot","severity":"info","payload":"device started"}'
```

Heartbeat event:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/log `
  -ContentType "application/json" `
  -Body '{"device_name":"ESP32_DEVKIT","event_type":"heartbeat","temperature":28,"humidity":70}'
```

## ESP32 Setup

1. Install Arduino IDE.
2. Add the ESP32 board package URL in Arduino IDE preferences:
   `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
3. Install `esp32` from Boards Manager.
4. Open `esp32/esp32_honeypot.ino`.
5. Set `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_BASE_URL`.
6. Select `ESP32 Dev Module` or `DOIT ESP32 DEVKIT V1`.
7. Upload and open Serial Monitor at `115200`.

The sketch uses `WiFi.h` and `HTTPClient.h`, registers the device at `/api/device`, sends a boot event, and posts heartbeat telemetry to `/api/log`.

## Kali Cowrie Setup

Install and run Cowrie on the Kali VM:

```bash
sudo apt update
sudo apt install git python3-venv python3-pip authbind -y
git clone https://github.com/cowrie/cowrie.git
cd cowrie
python3 -m venv cowrie-env
source cowrie-env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp etc/cowrie.cfg.dist etc/cowrie.cfg
bin/cowrie start
```

Cowrie JSON logs are usually written under:

```text
cowrie/var/log/cowrie/cowrie.json
```

Forward logs to the Windows Flask host:

```bash
python3 cowrie_parser.py \
  --log /home/kali/cowrie/var/log/cowrie/cowrie.json \
  --api http://WINDOWS_HOST_IP:5000/api/cowrie \
  --follow
```

For one-time forwarding from the start of the file:

```bash
python3 cowrie_parser.py \
  --log /home/kali/cowrie/var/log/cowrie/cowrie.json \
  --api http://WINDOWS_HOST_IP:5000/api/cowrie \
  --from-start
```

## Cowrie API Test

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5000/api/cowrie `
  -ContentType "application/json" `
  -Body '{"timestamp":"2026-05-30T10:00:00Z","src_ip":"192.0.2.44","username":"root","eventid":"cowrie.login.failed"}'
```

## Dashboard Verification

1. Open `http://127.0.0.1:5000`.
2. Send the ESP32 boot and heartbeat examples.
3. Send the Cowrie API test.
4. Confirm the overview counters update.
5. Confirm new ESP32 and Cowrie rows appear without refreshing.
6. Use the search fields to filter by IP, device, and event type.

## Security Implementation

The platform uses SQLAlchemy ORM, structured input validation, environment variables, Flask-WTF CSRF protection for browser-facing routes, CSRF exemption for machine-to-machine JSON APIs, rotating application logs, generic server errors, and strict JSON parsing. Do not expose the Flask development server directly to the internet; use a firewall or reverse proxy in shared lab networks.

## File Responsibilities

| File | Responsibility |
| --- | --- |
| `app.py` | Application factory, extension wiring, logging, CLI database initialization |
| `config.py` | Environment-driven settings |
| `database.py` | SQLAlchemy, Socket.IO, and CSRF extension objects |
| `models.py` | `Device`, `Event`, and `CowrieEvent` schema |
| `routes/api.py` | REST API endpoints and Socket.IO broadcasts |
| `routes/dashboard.py` | Dashboard and health routes |
| `services/validation.py` | JSON, IP, severity, timestamp, and status validation |
| `services/telemetry.py` | ESP32 event/device persistence, filters, and dashboard statistics |
| `services/cowrie_service.py` | Cowrie persistence and duplicate detection |
| `parser/cowrie_parser.py` | Cowrie JSON parser and continuous API forwarder |
| `templates/dashboard.html` | Bootstrap dashboard |
| `static/css/dashboard.css` | Dashboard styling |
| `static/js/dashboard.js` | Socket.IO, charts, and search filtering |
