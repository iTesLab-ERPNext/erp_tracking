# erp_tracking

Traccar GPS tracking integration for **ERPNext v15 / Frappe v15**, built as a
native Desk app (no separate React frontend).

## Status: Phase 2 of 8 complete

**Phase 1** (foundation) — done:
- App skeleton (`hooks.py`, `modules.txt`, roles, install hooks)
- `Traccar Settings` Single DocType (connection, auth, session/status fields)
- Centralized `TraccarAuth` (Basic Auth + API Key, one place headers are built)
- Centralized `TraccarClient` (all HTTP, error handling, standardized responses)
- Centralized endpoint map (`config.py`), verified line-by-line against the
  supplied OpenAPI spec (Traccar 6.14.5)
- `Test Connection` button with 🟢/🔴/🟠 status states
- Three roles: `ERP Tracking Manager`, `ERP Tracking User`, `ERP Tracking Viewer`

**Phase 2** (this delivery) — done:
- `integrations/traccar/devices.py`, `groups.py`, `users.py` — list/get
  wrappers over `TraccarClient`, with short-lived caching and a `refresh`
  bypass (Section 44)
- `integrations/traccar/permissions.py` — centralized `require_read()` /
  `require_write()` / `require_admin()` used by every whitelisted method
  (Section 40)
- `integrations/traccar/dashboard.py` — aggregates device/group/user/geofence
  counts for the Dashboard cards
- `api.py` whitelisted endpoints: `get_dashboard_summary`, `get_devices`,
  `get_device`, `get_groups`, `get_group`, `get_devices_in_group`,
  `get_users`, `get_user`
- `public/js/erp_tracking_list_engine.js` — the reusable list engine
  (Section 38): search, pagination, refresh, sortable columns, shared status
  badges. Devices/Groups/Users pages all configure this one engine instead
  of each re-implementing list UI.
- Desk Pages: **ERP Tracking Dashboard** (summary cards, connection banner,
  quick actions), **Devices** (list + details dialog with an Overview tab;
  Positions/Trips/Stops/Events/Maintenance/Commands/Geofences tabs are
  visibly present but disabled until their phases land — no fake data,
  Section 49), **Groups** (list + devices-in-group drill-in), **Users**
  (list, `password` field stripped defensively before it ever leaves the
  server, per Section 41)
- Tests: device/group/user modules, dashboard aggregation, password
  redaction, and a Guest-cannot-call-whitelisted-method permission check

**Not yet built** (Phases 3-8):
Live Positions, Position History, Route, Trips/Stops/Summary/Events reports,
Geofences, Notifications, Commands, Drivers, Maintenance, Calendars, Orders,
Server/Health/Statistics/Audit pages, Live Video, export system, full
permission matrix on writes, and French translations.

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
    │       ├── config.py          # endpoint map + settings loader
    │       ├── auth.py            # TraccarAuth (Basic + API Key)
    │       ├── client.py          # TraccarClient (all HTTP)
    │       ├── exceptions.py      # error hierarchy
    │       ├── permissions.py     # require_read/write/admin role checks
    │       ├── devices.py         # Phase 2
    │       ├── groups.py          # Phase 2
    │       ├── users.py           # Phase 2 (redacts password)
    │       ├── dashboard.py       # Phase 2
    │       └── utils.py           # date/pagination helpers
    ├── erp_tracking/
    │   └── doctype/
    │       └── traccar_settings/
    │           ├── traccar_settings.json
    │           ├── traccar_settings.py   # validate() + test_connection()
    │           └── traccar_settings.js   # Test Connection button + status
    ├── page/
    │   ├── erp_tracking_dashboard/
    │   ├── tracking_devices/
    │   ├── tracking_groups/
    │   └── tracking_users/
    ├── public/js/
    │   └── erp_tracking_list_engine.js   # shared list UI (Section 38)
    └── tests/
        ├── test_traccar_settings.py
        └── test_devices_groups_users.py
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

bench --site <site> run-tests --app erp_tracking \
  --module erp_tracking.tests.test_devices_groups_users
```

Phase 1 suite covers: Basic Auth success/failure, API Key success/failure,
missing credentials, connection success/timeout/connection-refused/invalid-
config, a generic `/devices` smoke test through the shared client, and
secret-safety checks (API key never appears in any returned payload;
unauthorized roles cannot call `test_connection`).

Phase 2 suite covers: device list/get/count (online vs offline), group
list/get and devices-in-group filtering, user list/get with `password`
stripped from every record before it's cached or returned, dashboard
aggregation (including the honest "not configured" failure path), and a
Guest-user permission check against `get_devices`.

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
6. Navigate to `/app/erp-tracking-dashboard` — confirm the connection banner
   and summary cards render, with Events/Trips/Stops Today showing "—" and
   a "Available after Reports (Phase 4)" note rather than a fake number.
7. Navigate to `/app/erp-tracking-devices` — confirm search, Refresh,
   Previous/Next pagination all work, and clicking a row opens the details
   dialog with the disabled Positions/Trips/Stops/etc. tabs visible (not
   hidden — so it's clear they're coming, not missing).
8. Navigate to `/app/erp-tracking-groups` and click a group to confirm the
   devices-in-group dialog filters correctly.
9. Navigate to `/app/erp-tracking-users` and confirm no `password` field
   ever appears in the table or in the Network tab response body.

## Next phase

Phase 3 (Live Positions, Position History, Route) builds a `positions.py`
feature module on top of `TraccarClient`, plus the `/positions/csv`,
`/positions/kml`, `/positions/gpx` native export endpoints from the spec.
None of the Phase 1/2 code changes for this to plug in.
