# erp_tracking

Traccar GPS tracking integration for **ERPNext v15 / Frappe v15**, built as a
native Desk app (no separate React frontend).

## Status: Phase 1 of 8

This package delivers **Phase 1** from the implementation plan:

- App skeleton (`hooks.py`, `modules.txt`, roles, install hooks)
- `Traccar Settings` Single DocType (connection, auth, session/status fields)
- Centralized `TraccarAuth` (Basic Auth + API Key, one place headers are built)
- Centralized `TraccarClient` (all HTTP, error handling, standardized responses)
- Centralized endpoint map (`config.py`), verified line-by-line against the
  supplied OpenAPI spec (Traccar 6.14.5)
- `Test Connection` button with 🟢/🔴/🟠 status states
- Three roles: `ERP Tracking Manager`, `ERP Tracking User`, `ERP Tracking Viewer`
- Automated tests for auth, connection scenarios, and secret safety

**Not yet built** (Phases 2-8 per the brief's own implementation order):
Dashboard, Devices, Groups, Users, Live Positions, Position History, Route,
Trips/Stops/Summary/Events reports, Geofences, Notifications, Commands,
Drivers, Maintenance, Calendars, Orders, Server/Health/Statistics/Audit
pages, Live Video, export system, full permission matrix, and French
translations. Ask to continue with the next phase and it will be built on
top of this same client/auth/config foundation — nothing here needs to be
rewritten for later phases to plug into it.

One correction versus a literal reading of the brief: the OpenAPI spec has
**no `GET /events` list endpoint** — only `GET /events/{id}` (single event)
and `GET /reports/events` (events for devices/groups over a time range). The
live Events page will be built on `/reports/events`, not on `/events`. See
the docstring in `config.py` for details.

## Directory layout

```
erp_tracking/
├── pyproject.toml
├── license.txt
├── README.md
└── erp_tracking/
    ├── hooks.py
    ├── install.py
    ├── modules.txt
    ├── api.py
    ├── config/
    │   └── desktop.py
    ├── integrations/
    │   └── traccar/
    │       ├── config.py        # endpoint map + settings loader
    │       ├── auth.py          # TraccarAuth (Basic + API Key)
    │       ├── client.py        # TraccarClient (all HTTP)
    │       ├── exceptions.py    # error hierarchy
    │       └── utils.py         # date/pagination helpers
    ├── erp_tracking/
    │   └── doctype/
    │       └── traccar_settings/
    │           ├── traccar_settings.json
    │           ├── traccar_settings.py   # validate() + test_connection()
    │           └── traccar_settings.js   # Test Connection button + status
    └── tests/
        └── test_traccar_settings.py
```

## Installation

```bash
# 1. Copy this app into your bench's apps directory as 'erp_tracking'
#    (or push it to a git repo and use bench get-app <repo-url>)
cp -r erp_tracking /path/to/frappe-bench/apps/erp_tracking

# 2. Install Python dependencies and register the app
cd /path/to/frappe-bench
./env/bin/pip install -e apps/erp_tracking

# 3. Install onto your site
bench --site <site> install-app erp_tracking

# 4. Run migrations (creates the Traccar Settings DocType, roles, etc.)
bench --site <site> migrate

# 5. Restart
bench restart
```

## Configuration

1. In Desk, go to **Traccar Settings** (search bar → "Traccar Settings").
2. Enter your Traccar server URL, e.g. `https://demo.traccar.org/api`.
3. Choose **Basic Auth** (username/password) or **API Key**.
4. Check **Enabled**.
5. Save.
6. Click **Test Connection**.
   - 🟢 green alert + "Connected" status = success
   - 🔴 red alert = authentication failed / server unavailable / invalid config
   - 🟠 orange alert = timeout

Only users with the `System Manager` or `ERP Tracking Manager` role can view
Traccar Settings or use Test Connection — credentials are never sent to the
browser (the `password` / `api_key` fields are Frappe `Password` fields,
encrypted at rest and excluded from API responses by Frappe core).

## Running tests

```bash
bench --site <site> run-tests --app erp_tracking \
  --module erp_tracking.tests.test_traccar_settings
```

Covers: Basic Auth success/failure, API Key success/failure, missing
credentials, connection success/timeout/connection-refused/invalid-config,
a generic `/devices` smoke test through the shared client, and secret-safety
checks (API key never appears in any returned payload; unauthorized roles
cannot call `test_connection`).

## Verifying inside ERPNext

1. Open **Traccar Settings**, confirm the form loads under the **ERP
   Tracking** module.
2. Confirm the `password` / `api_key` field shows masked dots, never plain
   text, after save + reload.
3. Click **Test Connection** against a real server (e.g.
   `https://demo.traccar.org/api` with demo credentials) and confirm the
   🟢 alert and updated `Connection Status` field.
4. Open browser dev tools → Network tab while clicking Test Connection —
   confirm the request body/response contains no password, api_key, or
   Authorization header (only the whitelisted method name and result JSON).
5. Log in as a user with only the `ERP Tracking User` role and confirm they
   cannot open Traccar Settings (list/form should 403).

## Next phase

Phase 2 (Dashboard, Devices, Groups, Users) builds directly on
`TraccarClient` — e.g. `TraccarClient().get("devices")` — so none of the
Phase 1 code changes, only new `integrations/traccar/devices.py`,
`groups.py`, `users.py` modules and their Desk pages get added.
# erp_tracking
# erp_tracking
