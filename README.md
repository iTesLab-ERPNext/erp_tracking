# ERP Tracking

Traccar GPS tracking inside ERPNext v15. The app runs natively in Frappe Desk —
no separate React application, no second design system.

- Traccar version targeted: **6.14.5** (the supplied OpenAPI document is the
  single source of truth)
- Frappe / ERPNext: **v15**
- Credentials stay server-side. The browser only ever calls whitelisted Frappe
  methods.

## Install

```bash
bench get-app erp_tracking <repository-url>
bench --site <site> install-app erp_tracking
bench --site <site> migrate
bench build --app erp_tracking
bench restart
```

Then open **ERP Tracking > Configuration** (or the `Traccar Settings` single
DocType):

1. Set **Traccar API URL** — the base API URL, e.g. `https://demo.traccar.org/api`.
2. Choose **Authentication Type**: `Basic Auth` (Traccar e-mail + password) or
   `API Key` (bearer token). Both are declared in the specification's
   `securitySchemes`.
3. Tick **Enabled**, save, then press **Test Connection**.

Assign one of the three roles to each user: `ERP Tracking Manager`,
`ERP Tracking User`, `ERP Tracking Viewer`.

## What you get

| Area | Pages |
| --- | --- |
| Overview | Dashboard, Configuration |
| Fleet | Devices (create/edit/delete for managers), Device Details, Groups (create/edit/delete), Drivers (create/edit/delete), Maintenance |
| Tracking | Live Positions, Position History, Route, Live Camera |
| Reports | **Fleet Overview** (KPIs, charts, device/driver/group breakdowns), Summary, Trips, Stops, Events, Geofence Visits |
| Alerts | Events, Notifications |
| Geofencing | Geofences (create / edit / delete for managers) |
| Commands | Saved commands, command types, send command |
| Administration | Traccar Users (create/edit/delete, manager only), Orders, Calendars (create/edit/delete), Audit Logs |
| System | Server Information, Statistics, Health |

Devices, Groups, Drivers and Calendars offer full CRUD to the manager role
and read-only access to everyone else, the same split Geofences has always
used. Traccar Users additionally require the manager role just to view the
list (unchanged from earlier phases) - write access sits behind that same
gate.

## Architecture

```
erp_tracking/
├── erp_tracking/
│   ├── hooks.py                     app assets, install and scheduler hooks
│   ├── install.py                   creates the three roles
│   ├── permissions.py               the only place roles are checked
│   ├── api.py                       every @frappe.whitelist() method
│   ├── export.py                    CSV / XLSX / PDF generation
│   ├── integrations/traccar/
│   │   ├── config.py                endpoints, REPORT_CONFIG, LIST_CONFIG
│   │   ├── auth.py                  the only module that reads credentials
│   │   ├── client.py                the only module that makes HTTP calls
│   │   ├── exceptions.py            typed, user-safe errors
│   │   ├── utils.py                 envelope, validation, cache, redaction
│   │   ├── listing.py               generic list engine
│   │   ├── reports.py               generic report engine
│   │   └── devices.py, positions.py, events.py, geofences.py, commands.py,
│   │       notifications.py, drivers.py, maintenance.py, calendars.py,
│   │       groups.py, users.py, orders.py, server.py, statistics.py,
│   │       audit.py, stream.py
│   ├── erp_tracking/                the "ERP Tracking" module
│   │   ├── doctype/traccar_settings/
│   │   ├── page/                    21 desk pages
│   │   └── workspace/erp_tracking/
│   ├── public/js/                   core, list_engine, report_engine, map
│   ├── translations/fr.csv
│   └── tests/
└── README.md
```

Two engines carry most of the UI. `erp_tracking.ListEngine` renders every
collection page (devices, groups, drivers, maintenance, calendars, orders,
notifications, saved commands, geofences, users) from `LIST_CONFIG`.
`erp_tracking.ReportEngine` renders every report from `REPORT_CONFIG`. Adding a
report or a list means adding a dictionary entry, not a page.

## Standard response

Every integration method returns the same envelope:

```json
{ "success": true, "data": [], "message": "", "status_code": 200, "error": null }
```

Failures carry `success: false`, `data: null` and a translated, user-safe
`message`. Stack traces go to the Frappe error log, never to the browser.

## Security

- `password` and `api_key` are Frappe `Password` fields (encrypted at rest) and
  are read only inside `auth.py`.
- No credential, token, cookie or `Authorization` header is ever returned to the
  client, logged, or written into rendered HTML. `utils.redact()` scrubs
  anything credential-shaped before it reaches a log line.
- `utils.validate_path()` rejects absolute URLs, `..` and anything that is not a
  relative Traccar path, so the server-side client cannot be turned into an open
  proxy by a crafted request.
- Report names and list resources are validated against allow-lists.
- Commands, settings, statistics and the audit log require the manager role.
- Live video is relayed by the server (see below) precisely so that no Traccar
  session token has to be handed to the browser.

## How the specification shaped the app

The supplied OpenAPI document is authoritative. A few places where it differs
from a naive reading of the brief:

| Brief says | Specification says | What the app does |
| --- | --- | --- |
| Events page uses `/events` | Only `GET /events/{id}` exists; there is no `/events` collection | The Events page reads `GET /reports/events`; `/events/{id}` backs the single-event lookup |
| Export CSV / XLSX / PDF from reports | Traccar offers `/reports/{name}/{type}` with `type` in `xlsx\|mail` only | XLSX comes from Traccar; CSV and PDF are rendered server-side by Frappe |
| Geofences show Type and Group | The Geofence schema has `id, name, description, area, calendarId, attributes` | "Type" is derived from the WKT prefix (Circle / Polygon / Corridor); Group is not shown because Traccar does not return it |
| Calendars show Description, Schedule, Timezone | The Calendar schema has `id, name, data, attributes` | Schedule and Timezone are parsed out of the base64 iCalendar blob; no invented fields |
| Notifications show "Disabled" | The Notification schema has no `disabled` field | The list shows `always`, `notificators` and `calendarId` instead |
| Position pagination | `/positions` has no `limit`/`offset` | The window is fetched once and paged server-side |
| `daily` on summary | Documented only on `/reports/summary/{type}` | Sent only on the download path |
| `alarm` on events | Documented only on `/reports/events/{type}` | Sent only on the download path |

Endpoints present in the specification but deliberately **not** wired up:
`/server/gc`, `/server/reboot`, `/server/cache`, `/server/file/{path}`,
`/session/{id}` (user impersonation), `/users/totp`, `/password/*`,
`/share/*`, `/permissions/bulk`, `/attributes/computed/test`,
`/devices/{id}/image`, `/positions/{id}` (delete). They are either destructive,
authentication-adjacent, or outside the brief. Nothing was invented.

`POST`/`PUT`/`DELETE /users` **are** wired up (manager role only) - creating
Traccar accounts from ERPNext is now supported; passwords are handled
write-only (see `integrations/traccar/users.py`) and are never returned in
any response. `GET /reports/combined` is wired up as
`erp_tracking.api.get_combined_report` and also feeds the Reports > Fleet
Overview tab, alongside the existing trips/summary/events reports.

## Live video

The HLS endpoints are authenticated. Rather than give the browser a Traccar
session token — which the security requirements forbid — the playlist and its
`.ts` segments are relayed through two whitelisted methods, and the playlist's
segment URIs are rewritten to point back at Frappe. Only bytes cross; no
credential does. The feature stays off until **Enable Live Video** is ticked in
Traccar Settings.

## Tests

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app erp_tracking
bench --site <site> run-tests --module erp_tracking.tests.test_security
bench --site <site> run-tests --module erp_tracking.tests.test_crud_and_overview
```

Covered: Basic Auth and API Key success/failure, missing credentials, timeouts,
unreachable server, HTTP status mapping, path validation, log redaction, device
and position reads, date and device filters, all five reports, CSV/XLSX/PDF
exports, native-endpoint preference, role enforcement per method, allow-list
rejection, and assertions that no response ever contains a secret. Full
create/edit/delete for devices, groups, users, drivers and calendars
(including the password write-only path and the iCalendar encode/decode
round trip) and the fleet overview's KPI/breakdown math are in
`test_crud_and_overview.py` specifically.

## Translations

French strings live in `erp_tracking/translations/fr.csv` and are loaded by
`bench migrate`. All user-facing strings pass through `_()` in Python and
`__()` in JavaScript.

## Caching

Device, group, user, calendar and driver lists, server information, command
types and notification types are cached in the Frappe cache for the duration set
in Traccar Settings (`cache_ttl`, default 60s). Credentials are never cached;
only a short-lived "these credentials validated" flag is. Every page has a
Refresh action that bypasses the cache, and Traccar Settings has **Clear Cache**.

## License

MIT — see `license.txt`.
