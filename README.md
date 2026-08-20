# erp_tracking

Traccar GPS tracking integration for **ERPNext v15 / Frappe v15**, built as a
native Desk app (no separate React frontend).

## Status: Phase 5 of 8 complete

**Phase 1-4** — done (foundation, Dashboard/Devices/Groups/Users, Live
Positions/History/Route, Trips/Stops/Summary/Events reports). See prior
notes below.

**Phase 5** (this delivery) — done. First phase with real write operations:
- `integrations/traccar/geofences.py` — full CRUD (the spec supports
  create/update/delete, so per Section 22 this implements all of it, not
  just list/get)
- `integrations/traccar/notifications.py` — full CRUD plus
  `/notifications/types`, `/notifications/notificators`, and
  `/notifications/test` (send-test)
- `integrations/traccar/commands.py` — saved command CRUD,
  `/commands/types` (optionally scoped to a device, for protocol-specific
  command lists), `/commands/send` (device-specific supported commands),
  and `send_command()` for dispatching a new or saved command
- **New `Traccar Command Log` DocType** — a local audit trail written
  server-side every time `send_command` succeeds (who, when, what, to
  which device/group, sent-vs-queued). No role has *create* permission on
  it directly — it can only be inserted by `api.send_command` itself — so
  it can't be forged from the client. This is separate from Traccar's own
  `/audit` endpoint (Section 33, Phase 7), which reflects actions on the
  Traccar server itself.
- **Permission split, decided explicitly**: Geofence reads use the normal
  `require_read()` (Manager/User/Viewer); geofence writes need
  `require_write()` (Manager/User — Viewer stays read-only, matching
  Section 40). Notifications and Commands are gated with `require_admin()`
  end-to-end (Manager only) — Section 40's role table only lists
  "Commands"/"Administration" under Manager, and Section 25 demands
  "strict permission checking" specifically for sending commands.
- `api.py`: `get_geofences/create/update/delete_geofence`,
  `get_notifications/get_notification_types/get_notificators/create/
  update/delete_notification/send_test_notification`,
  `get_commands/get_command/get_command_types/
  get_available_commands_for_device/create/update/delete_saved_command/
  send_command`
- Pages: **Geofences** (list + create/edit/delete dialog, WKT area field,
  New/Edit hidden client-side for Viewer-only users though the server
  enforces it regardless), **Notifications** (Manager-only page; CRUD
  dialog whose Type/Notificator options are fetched live from Traccar
  rather than hardcoded, plus a Send Test Notification menu item),
  **Commands** (Manager-only page; Saved Commands CRUD list, and a Send
  Command dialog whose Command Type dropdown repopulates per selected
  device via `/commands/types?deviceId=`, showing 🟢 "Command sent" or 🟠
  "Command queued" per the actual `status_code` Traccar returned)
- Dashboard's Geofences count now goes through `geofences.py` instead of
  the temporary direct-client call noted in the Phase 2-4 deliveries
- Tests: geofence CRUD + cache invalidation on write, notification types/
  notificators/create/send-test, command send (both 200-sent and
  202-queued outcomes), command-type-per-device parameter passing, and
  permission checks proving a Guest can't send a command, create a
  geofence, or even view the notifications list

**Not yet built** (Phases 6-8):
Drivers, Maintenance, Calendars, Orders, Server/Health/Statistics/Audit
pages, Live Video, French translations, and a dedicated export system
beyond what's already native-endpoint-backed in Phases 3-4.

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
    │       ├── positions.py       # Phase 3 (live + history + native exports)
    │       ├── route.py           # Phase 3
    │       ├── reports.py         # Phase 4 (generic report engine, Section 37)
    │       ├── geofences.py       # Phase 5 (full CRUD)
    │       ├── notifications.py   # Phase 5 (full CRUD + types/notificators)
    │       ├── commands.py        # Phase 5 (saved commands + send)
    │       └── utils.py           # date/pagination helpers
    ├── erp_tracking/
    │   └── doctype/
    │       ├── traccar_settings/
    │       │   ├── traccar_settings.json
    │       │   ├── traccar_settings.py   # validate() + test_connection()
    │       │   └── traccar_settings.js   # Test Connection button + status
    │       └── traccar_command_log/      # Phase 5: local send-command audit trail
    │           ├── traccar_command_log.json
    │           └── traccar_command_log.py
    ├── page/
    │   ├── erp_tracking_dashboard/
    │   ├── tracking_devices/
    │   ├── tracking_groups/
    │   ├── tracking_users/
    │   ├── tracking_positions/           # Phase 3: Live Positions
    │   ├── tracking_position_history/    # Phase 3
    │   ├── tracking_route/               # Phase 3
    │   ├── tracking_reports/             # Phase 4: Trips/Stops/Summary tabs
    │   ├── tracking_events/              # Phase 4
    │   ├── tracking_geofences/           # Phase 5
    │   ├── tracking_notifications/       # Phase 5 (Manager only)
    │   └── tracking_commands/            # Phase 5 (Manager only)
    ├── public/js/
    │   └── erp_tracking.bundle.js        # shared list UI + ReportPage (Sections 37-38)
    └── tests/
        ├── test_traccar_settings.py
        ├── test_devices_groups_users.py
        ├── test_positions_route.py
        ├── test_reports.py
        └── test_geofences_notifications_commands.py
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

bench --site <site> run-tests --app erp_tracking \
  --module erp_tracking.tests.test_positions_route

bench --site <site> run-tests --app erp_tracking \
  --module erp_tracking.tests.test_reports

bench --site <site> run-tests --app erp_tracking \
  --module erp_tracking.tests.test_geofences_notifications_commands
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

Phase 3 suite covers: live positions (including client-side device
filtering), position history parameter validation (device/date range
required), proof that CSV export calls Traccar's native `/positions/csv`
endpoint (not a hand-rolled CSV writer), and Route parameter validation
(device-or-group required, dates required, `deviceId` sent as a repeated
query param matching the spec's array encoding).

Phase 4 suite covers: report generation per report key hitting the right
endpoint, `daily` only ever being sent for Summary (never Trips/Stops/
Events even if a caller passes it), the report-key allow-list rejecting
anything not in `REPORT_CONFIG`, event-type filter encoding, a regression
test proving XLSX downloads come back as real `bytes` (not corrupted
UTF-8 text), mail-delivery 204 handling, and both branches of the
dashboard's 50-device cap on the Today counters.

Phase 5 suite covers: geofence create/update/delete (including cache
invalidation on write), notification types/notificators/create/send-test,
command sending in both its success shapes (200 "sent" and 202 "queued"),
per-device command-type filtering, and permission checks proving a Guest
user cannot send a command, create a geofence, or even view the
notifications list.

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
   and summary cards render, and Events/Trips/Stops Today now show real
   numbers (computed from today's reports) instead of the earlier "—"
   placeholder, as long as your fleet is under 50 devices.
7. Navigate to `/app/erp-tracking-devices` — confirm search, Refresh,
   Previous/Next pagination all work, and clicking a row opens the details
   dialog. The Positions/Trips/Stops/Events tabs are now live (last 24h /
   7 days); Maintenance/Commands/Geofences remain visibly disabled until
   Phases 5-6.
8. Navigate to `/app/erp-tracking-groups` and click a group to confirm the
   devices-in-group dialog filters correctly.
9. Navigate to `/app/erp-tracking-users` and confirm no `password` field
   ever appears in the table or in the Network tab response body.
10. Navigate to `/app/erp-tracking-positions` — confirm the device/group/
    status filters narrow the table, and "View on Map" opens the correct
    coordinates on openstreetmap.org.
11. Navigate to `/app/erp-tracking-position-history` — pick a device and
    date range, click **Generate**, then click **Export CSV** and confirm a
    file downloads containing Traccar's own CSV output (unmodified).
12. Navigate to `/app/erp-tracking-route` — select one or more devices,
    click **Generate**, and confirm a Leaflet map renders with a route
    polyline plus Start/End markers, alongside the position table below it.
13. Navigate to `/app/erp-tracking-reports` — confirm the Trips/Stops/
    Summary tabs each load filters, a table, and (for Summary) KPI cards.
    Click **Export XLSX** on any tab and confirm the downloaded file opens
    correctly in Excel/LibreOffice (this is the regression the binary-bytes
    fix above addresses — a corrupted download here would mean that fix
    didn't take).
14. Navigate to `/app/erp-tracking-events` — confirm events render with
    color-coded type badges, and that entering event types (comma-
    separated) into the filter narrows the results.
15. Navigate to `/app/erp-tracking-geofences` — create a geofence with a
    WKT area (e.g. `CIRCLE (-27.5 153.0, 500)`), confirm it appears in the
    list, click it, edit the description, save, then delete it and confirm
    it's gone. Log in as an `ERP Tracking Viewer`-only user and confirm the
    New Geofence button doesn't appear and the row click does nothing.
16. Navigate to `/app/erp-tracking-notifications` (as a Manager) — confirm
    the Type and Notificators dropdowns are populated from Traccar (not
    hardcoded), create a rule, then use **Send Test Notification** from the
    page menu and confirm the alert reflects success/failure.
17. Navigate to `/app/erp-tracking-commands` (as a Manager) — click **Send
    Command**, pick a device, confirm the Command Type dropdown repopulates
    for that specific device, send it, and confirm the alert shows 🟢
    "Command sent" or 🟠 "Command queued" matching what Traccar actually
    returned. Then open **Traccar Command Log** in Desk and confirm a
    record was written with your user, the device, and the command type.
18. Log in as an `ERP Tracking User` (not Manager) and confirm
    `/app/erp-tracking-commands` and `/app/erp-tracking-notifications` both
    403 — those pages are Manager-only per Section 40.

## Next phase

Phase 6 (Drivers, Maintenance, Calendars) is the last "resource CRUD"
phase before Phase 7 moves into server-level concerns (Server Info,
Health, Statistics, Audit) and Phase 8 wraps up with Live Video, the
French translation pass, and closing out the full write-permission matrix
across every DocType/page built so far.
