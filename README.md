# erp_tracking

Traccar GPS tracking integration for **ERPNext v15 / Frappe v15**, built as a
native Desk app (no separate React frontend).

## Status: Phase 8 of 8 complete — project delivered

### Post-delivery addition: full CRUD for Devices, Groups, Users
The original Phase 2 delivery only wired up list/get (read) for Devices,
Groups, and Users, even though the spec's `/devices`, `/groups`, and
`/users` endpoints all support full create/update/delete. Closed that gap:
- `devices.py` / `groups.py`: `create_*`, `update_*`, `delete_*` added,
  same read/write role split as Drivers/Geofences (Manager+User write,
  Viewer read-only)
- `users.py`: `create_user`/`update_user`/`delete_user` added, but gated
  **Manager-only** — Users are real Traccar login accounts, not a general
  fleet resource, so managing them is treated as an administrative action
  like Notifications/Commands/Calendars. The `password` field is
  deliberately **write-only**: the edit dialog never pre-fills it from a
  GET, an empty value on update means "leave unchanged" (not "clear it"),
  and even if a misconfigured Traccar server echoed a password back on
  create, `_redact()` strips it before it reaches the browser — covered by
  a dedicated test.
- Devices page: "New Device" button, plus an "Edit" button inside the
  existing details dialog's Overview tab (which already had read-only
  Positions/Trips/Stops/Events/Maintenance/Commands/Geofences tabs from
  earlier phases)
- Groups page: "New Group" button; row click now opens an edit form
  (Name, Parent Group ID, Attributes) with a "View Devices in Group"
  button and Delete, replacing the old read-only click-through
- Users page: "New User" button and row-click-to-edit, both visible only
  to Managers client-side (server-side `require_admin()` enforces it
  regardless)
- All three pages' dashboard shortcuts already existed from Phase 2 — no
  new links needed, they just now lead to fully functional CRUD instead of
  read-only lists
- New test module (`test_devices_groups_users_crud.py`) covering create/
  update/delete for all three resources, cache invalidation on write, the
  password write-only behavior specifically, and permission checks

### Third build fix — missing `package.json` (the actual root cause)
Two earlier fixes (a bad `app_include_js` value, then 20 mismatched page
folder names) were both real bugs and both necessary — but the
`TypeError [ERR_INVALID_ARG_TYPE]: paths[0] ... Received undefined` crash
in `esbuild.js`'s `get_all_files_to_build` kept recurring across multiple
independent, freshly-created benches (different machines, different Python
versions) even after both fixes. That consistency pointed at something
more fundamental: **the app had no `package.json`.**

Every Frappe app — `frappe`, `erpnext`, and every third-party app — ships a
`package.json` at its repo root, because Frappe's Node/esbuild build
tooling treats each app as a **Yarn workspace member**. Without one, the
app is never registered as a workspace, and `get_all_files_to_build` has
no valid path to resolve for it — exactly the `undefined` this crash
reports. `pyproject.toml` (Python packaging) was present from Phase 1, but
the JS-side manifest was simply missing the entire time.

**Fixed**: added a minimal `package.json` at the repo root
(`name`, `version`, `private: true`, `license`). This is the piece that
was actually missing all along; the `app_include_js` and page-folder-name
fixes were real and still necessary, but insufficient on their own without
this file.

### Second build fix (critical — affects every page from Phase 2 onward)
The earlier `hooks.py`/bundle-naming fix was necessary but not sufficient.
The real, larger cause of the same `esbuild` crash
(`TypeError [ERR_INVALID_ARG_TYPE]: The "paths[0]" argument must be of type
string. Received undefined`) was that **20 of the 21 custom Pages had a
folder name that didn't match their Page record's `name` field.** Frappe
requires a Page's asset folder to equal `scrub(name)` exactly (lowercased,
hyphens→underscores) — e.g. a page named `erp-tracking-devices` must live
in `page/erp_tracking_devices/`. Pages were built with spec-matching folder
names like `tracking_devices` but hyphenated route names like
`erp-tracking-devices` for nicer URLs, and the two were never reconciled.
When `bench build`'s asset scanner tried to resolve each page's JS file by
the expected (but nonexistent) path, it hit the `undefined` that crashed
`path.resolve()`.

**Fixed**: every affected Page's `name`/`page_name` now matches its actual
folder exactly (e.g. `tracking_devices`, not `erp-tracking-devices`), and
every `frappe.pages["..."]` registration key, Dashboard quick-action route,
and cross-page link was updated to match. Verified two ways: (1) every
page's `scrub(name)` now equals its folder name and a `<name>.js` file
exists at that path, and (2) no page name collides with another. The
`erp-tracking-dashboard` page was untouched — its folder
(`erp_tracking_dashboard`) already matched correctly, which is exactly why
it never triggered this bug and why the first fix alone looked plausible
but wasn't the whole story.

**Phase 1-7** — done (foundation; Dashboard/Devices/Groups/Users; Live
Positions/History/Route; Trips/Stops/Summary/Events reports;
Geofences/Notifications/Commands; Drivers/Maintenance/Calendars;
Server Info/Health/Statistics/Audit). See prior notes below.

**Phase 8** (this delivery) — done. Final phase:
- `integrations/traccar/orders.py` — full CRUD (Section 34), same
  read/write split as Drivers/Geofences. No Export button, matching the
  Maintenance decision (Phase 6) — no native export endpoint exists for
  Orders in the spec.
- **`integrations/traccar/stream.py`** — Live Video (Section 35). This
  phase surfaces a genuine conflict in the brief: Section 35 says "don't
  proxy video through ERPNext unnecessarily," but the only alternative
  (Traccar's documented `?token=` query-string workaround for browser
  video players) hands the frontend a token — which Section 41 explicitly
  forbids ("never receive passwords, API keys, tokens or Authorization
  headers"). Resolved by proxying deliberately: the HLS playlist and every
  `.ts` segment are fetched server-side (real credentials touch only that
  server-side request, exactly like every other endpoint in the app), and
  the playlist's segment references are rewritten to point back at this
  app's own whitelisted `get_stream_segment` endpoint. The browser's video
  player only ever talks to ERPNext over the user's already-authenticated
  Frappe session. Full reasoning is in the module's docstring.
- **A second binary-parsing bug caught before shipping** (same class as
  the Phase 4 XLSX bug): `TraccarClient._parse_body` didn't recognize
  `application/vnd.apple.mpegurl` (the HLS playlist's MIME type) as text —
  it doesn't start with `text/` or contain `xml`, so it would have been
  returned as raw bytes and broken `stream.py`'s segment-URL rewriting.
  Fixed with an explicit `mpegurl` check and a regression test proving the
  playlist comes back as a string, not bytes.
- `api.py`: `get_orders/get_order/create/update/delete_order`,
  `get_stream_playlist`, `get_stream_segment`
- Pages: **Orders** (list + CRUD dialog), **Live Camera** (device/channel
  picker, hls.js lazy-loaded from cdnjs mirroring the Leaflet/Chart.js
  pattern, `<video>` src always points at this app's own proxy endpoint —
  never at Traccar directly; Safari's native HLS support is used as a
  fallback when hls.js isn't needed)
- **Devices detail dialog closed out**: the Maintenance/Commands/Geofences
  tabs (visibly disabled since Phase 2, with a note that they'd arrive in
  a later phase) are now live, each showing a compact device-scoped view
  with a link to the full page. Commands stays visibly disabled for
  non-Manager users specifically (tooltip: "Manager only"), matching that
  resource's actual permission gate rather than a blanket "coming later."
- **French translations** (Section 47): `translations/fr.csv`, 138
  entries covering every page title, nav label, status string, and common
  action across the app — not just the handful of examples the brief
  listed. Loaded automatically by Frappe's i18n system; no build step
  needed beyond a normal `bench build`.
- Tests: Orders CRUD + cache invalidation, the playlist-rewriting logic
  (segment references replaced, comment/tag lines left untouched), the
  `mpegurl` parsing regression test, segment byte-proxying, proof that
  stream endpoints correctly still require normal authentication (unlike
  `/server` and `/health` from Phase 7), and permission checks for both
  new resources

## Closing the permission matrix (Section 40)

Every whitelisted method in the app goes through exactly one of three
checks from `permissions.py` — no page or endpoint was left ungated.
"Read" below means list/get; "Write" means create/update/delete (or
send, for Commands):

| Resource | Manager | User | Viewer | Notes |
|---|---|---|---|---|
| Traccar Settings, Test Connection | ✅ | ❌ | ❌ | credentials — Manager only |
| Dashboard | ✅ read | ✅ read | ✅ read | |
| Devices, Groups | ✅ read/write | ✅ read/write | ✅ read | full CRUD (create/edit/delete dialogs on each page) |
| Users | ✅ read/write | ✅ read only | ❌ | write is Manager-only — Users are real Traccar login accounts, not a general fleet resource; password is write-only, never round-tripped back to the browser |
| Live Positions, Position History, Route | ✅ | ✅ | ✅ | read-only resources |
| Reports (Trips/Stops/Summary/Events) | ✅ | ✅ | ✅ | read-only; export uses the same read gate |
| Geofences | ✅ read/write | ✅ read/write | ✅ read | |
| Drivers, Maintenance | ✅ read/write | ✅ read/write | ✅ read | |
| Orders | ✅ read/write | ✅ read/write | ✅ read | |
| Notifications | ✅ | ❌ | ❌ | routes real email/SMS — Manager only |
| Commands (saved + send) | ✅ | ❌ | ❌ | Section 25: strict permission checking |
| Calendars | ✅ | ❌ | ❌ | admin scheduling primitive |
| Server Information (read) | ✅ | ✅ | ✅ | not sensitive |
| Server Information (update) | ✅ | ❌ | ❌ | |
| Server Health | ✅ | ✅ | ✅ | |
| Server Statistics | ✅ | ❌ | ❌ | Section 40 System/Administration grouping |
| Audit Logs | ✅ | ❌ | ❌ | spec's own description: "Admin only" |
| Live Video | ✅ | ✅ | ✅ | read-only |

Every row above is enforced twice: once at the Frappe **Page** level
(the `roles` array in each page's `.json`, so the page doesn't even load
for an unauthorized user) and once at the **API** level (`require_read()` /
`require_write()` / `require_admin()` in every whitelisted method in
`api.py`), so a user can't route around the UI restriction by calling the
API directly. Every phase's test suite includes at least one Guest-user
(and, where relevant, a wrong-role) check proving this — see the
`TestPhaseNPermissions` classes across `tests/`.

One correction versus a literal reading of the brief: the OpenAPI spec has
**no `GET /events` list endpoint** — only `GET /events/{id}` (single event)
and `GET /reports/events` (events for devices/groups over a time range). The
live Events page will be built on `/reports/events`, not on `/events`. See
the docstring in `config.py` for details.

## Sidebar / Workspace

`erp_tracking/erp_tracking/workspace/erp_tracking/erp_tracking.json` gives
the app a proper entry in the Desk sidebar. Frappe v15 sidebar navigation
is driven entirely by the **Workspace** doctype — the old
`config/desktop.py` module-icon system (still present here, harmless, for
compatibility with anything that reads it) is not what actually puts an
app in the sidebar in v15.

The workspace includes:
- A header and 5 shortcuts (Dashboard, Devices, Live Positions, Reports,
  Traccar Settings)
- 8 cards grouping all 21 pages by category, matching the navigation
  structure from Section 46: Fleet, Tracking, Reports, Geofencing & Alerts,
  Commands, Administration, System, Settings

The workspace itself is visible to everyone (`public: 1`, no role
restriction) so any user can see the sidebar and navigate — the individual
pages and DocTypes it links to enforce their own role restrictions when
clicked (e.g. a `ERP Tracking User` clicking into **Commands** still gets
blocked, per the permission matrix above). Every link/shortcut in the
workspace was cross-checked programmatically against the actual page and
DocType names in this package to make sure nothing points at something
that doesn't exist.

No extra installation step is needed — `bench migrate` picks up workspace
files the same way it picks up Page and DocType JSON files already in the
app.



```
erp_tracking/
├── pyproject.toml
├── package.json
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
    │       ├── drivers.py         # Phase 6 (full CRUD)
    │       ├── maintenance.py     # Phase 6 (full CRUD + device filter)
    │       ├── calendars.py       # Phase 6 (full CRUD, base64 iCalendar)
    │       ├── server.py          # Phase 7 (info + health, require_auth=False bypass)
    │       ├── statistics.py      # Phase 7
    │       ├── audit.py           # Phase 7
    │       ├── orders.py          # Phase 8 (full CRUD)
    │       ├── stream.py          # Phase 8 (Live Video proxy - see docstring)
    │       └── utils.py           # date/pagination helpers
    ├── erp_tracking/
    │   ├── doctype/
    │   │   ├── traccar_settings/
    │   │   │   ├── traccar_settings.json
    │   │   │   ├── traccar_settings.py   # validate() + test_connection()
    │   │   │   └── traccar_settings.js   # Test Connection button + status
    │   │   └── traccar_command_log/      # Phase 5: local send-command audit trail
    │   │       ├── traccar_command_log.json
    │   │       └── traccar_command_log.py
    │   └── workspace/
    │       └── erp_tracking/
    │           └── erp_tracking.json     # sidebar entry (shortcuts + cards)
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
    │   ├── tracking_commands/            # Phase 5 (Manager only)
    │   ├── tracking_drivers/             # Phase 6
    │   ├── tracking_maintenance/         # Phase 6
    │   ├── tracking_calendars/           # Phase 6 (Manager only)
    │   ├── tracking_server_info/         # Phase 7
    │   ├── tracking_health/              # Phase 7
    │   ├── tracking_statistics/          # Phase 7 (Manager only)
    │   ├── tracking_audit/               # Phase 7 (Manager only)
    │   ├── tracking_orders/              # Phase 8
    │   └── tracking_live_video/          # Phase 8
    ├── public/js/
    │   └── erp_tracking.bundle.js        # shared list UI + ReportPage (Sections 37-38)
    ├── translations/
    │   └── fr.csv                        # Phase 8 (Section 47)
    └── tests/
        ├── test_traccar_settings.py
        ├── test_devices_groups_users.py
        ├── test_devices_groups_users_crud.py
        ├── test_positions_route.py
        ├── test_reports.py
        ├── test_geofences_notifications_commands.py
        ├── test_drivers_maintenance_calendars.py
        ├── test_server_health_statistics_audit.py
        └── test_orders_stream.py
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

bench --site <site> run-tests --app erp_tracking \
  --module erp_tracking.tests.test_drivers_maintenance_calendars

bench --site <site> run-tests --app erp_tracking \
  --module erp_tracking.tests.test_server_health_statistics_audit

bench --site <site> run-tests --app erp_tracking \
  --module erp_tracking.tests.test_orders_stream
```

Or run the whole suite at once:

```bash
bench --site <site> run-tests --app erp_tracking
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

Phase 6 suite covers: driver CRUD and device-filter parameter passing,
maintenance CRUD and device-filter parameter passing, calendar creation
proving the iCalendar text is correctly base64-encoded before it's sent
to Traccar, partial calendar updates only sending changed fields, and
permission checks for all three resources.

Phase 7 suite covers: the `require_auth=False` bypass itself — proving
`/server` and `/health` succeed with zero credentials configured and send
no `Authorization` header, while the same client instance calling a normal
endpoint the standard way still correctly fails locally — plus timezone
caching (second call doesn't re-hit the network), statistics/audit date
validation, and permission checks for all four Phase 7 endpoints.

Phase 8 suite covers: Order CRUD and cache invalidation, the HLS playlist
segment-rewriting logic (segment lines replaced with proxy URLs, comment/
tag lines untouched), a regression test proving the playlist's
`application/vnd.apple.mpegurl` content type is parsed as text (not
corrupted as binary), segment byte-proxying, proof that stream endpoints
still require normal authentication unlike `/server`/`/health`, and
permission checks for Orders and Live Video.

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
19. Navigate to `/app/erp-tracking-drivers` — create a driver, confirm it
    appears, edit and delete it.
20. Navigate to `/app/erp-tracking-maintenance` — create a maintenance item
    (e.g. name "Oil Change", type `totalDistance`, start 0, period 10000),
    then use the device filter dropdown and confirm the list narrows (or
    stays empty, since maintenance items aren't linked to a device until
    permissions are set up on the Traccar side — that's expected, this
    filter is a passthrough to Traccar's own `deviceId` query param).
21. Navigate to `/app/erp-tracking-calendars` (as a Manager) — the New
    Calendar dialog pre-fills a starter iCalendar template; save it,
    confirm the list shows a decoded "Schedule Preview" snippet (not a raw
    base64 blob), then edit and delete it. Log in as an `ERP Tracking User`
    and confirm `/app/erp-tracking-calendars` 403s.
22. Navigate to `/app/erp-tracking-server-info` — confirm it loads even
    for a `Viewer`-only user (this endpoint doesn't need write access),
    and that the Edit button only appears for Managers.
23. Navigate to `/app/erp-tracking-health` — confirm it shows 🟢 HEALTHY
    (or 🔴 UNAVAILABLE if your Traccar server is actually down) with a
    response time in milliseconds, and that it auto-refreshes roughly
    every 30 seconds without a manual reload.
24. Navigate to `/app/erp-tracking-statistics` (as a Manager) — generate a
    report for the last 7 days and confirm both a table and a Chart.js
    line chart render below the filters.
25. Navigate to `/app/erp-tracking-audit` (as a Manager) — generate a
    report for the last 24 hours and confirm actions appear with their
    user/type/object. Log in as an `ERP Tracking User` and confirm this
    page 403s (Section 33: the endpoint itself is admin-only per Traccar's
    own spec description, not just this app's convention).
26. Navigate to `/app/erp-tracking-orders` — create an order, confirm it
    appears, edit and delete it.
27. Navigate to `/app/erp-tracking-live-video` — select a device that has
    a camera configured on your Traccar server, click **Play**, and
    confirm video plays. Open browser dev tools → Network tab and confirm
    every request goes to `/api/method/erp_tracking.api.get_stream_...` on
    your own ERPNext domain — never directly to your Traccar server, and
    never carrying an `Authorization` header from the browser.
28. Open **Devices**, click into a device, and check the **Maintenance**,
    **Commands**, and **Geofences** tabs — confirm they now show real
    (possibly empty) data instead of the "later phase" placeholder from
    earlier deliveries, and that **Commands** stays visibly disabled with
    a "Manager only" tooltip when viewed as a non-Manager user.
29. Switch your Desk language to French (User menu → My Settings →
    Language → Français) and confirm page titles and common labels (e.g.
    "Véhicules" for Devices, "Positions en temps réel" for Live Positions,
    "Tester la connexion" for Test Connection) render in French.
30. Refresh Desk and confirm **ERP Tracking** now appears in the left
    sidebar. Click it and confirm the workspace opens with shortcuts at
    the top and the 8 category cards below, and that every link in every
    card actually opens its corresponding page instead of a 404.

## Project status

All 8 phases from the brief's own implementation order (Section 51) are
complete. Every DocType, page, and whitelisted API method is real,
syntax-checked code — not pseudo-code — and every feature was checked
against the supplied OpenAPI spec operation-by-operation before being
built (Section 50). Two real bugs (binary-response corruption for XLSX in
Phase 4, and the same class of bug for the HLS playlist's MIME type in
Phase 8) were caught by the test suite before shipping rather than after.

A handful of deliberate, documented deviations from a literal reading of
the brief exist because the actual OpenAPI spec doesn't support what the
brief assumed — each is called out where it happens rather than silently
worked around:
- No `GET /events` list endpoint exists; the Events page uses
  `GET /reports/events` instead (see `config.py`).
- Report downloads only support `xlsx` and `mail`, not CSV/PDF (see
  `reports.py`).
- Maintenance and Orders have no native export endpoint, so no
  Export button was added for either (Sections 28, 34).
- The Calendar schema has no separate Schedule/Timezone field — only a
  base64 `data` blob (see `calendars.py`).
- Live Video is proxied through ERPNext, not fetched by the browser
  directly from Traccar, because the alternative would require handing
  the frontend a session token (see `stream.py`).
