# Implementation guide — phase by phase

Each phase lists the files it adds, where they go, the bench commands to run,
and how to verify the result inside ERPNext.

---

## Phase 1 — Structure, settings, authentication, client, connection test

**Files created**

| File | Purpose |
| --- | --- |
| `pyproject.toml`, `MANIFEST.in`, `license.txt`, `.gitignore` | Python packaging for `bench get-app` |
| `erp_tracking/__init__.py` | app version |
| `erp_tracking/hooks.py` | asset bundles, install hooks, hourly scheduler |
| `erp_tracking/modules.txt` | declares the `ERP Tracking` module |
| `erp_tracking/install.py` | creates the three roles, seeds the settings single |
| `erp_tracking/patches.txt`, `erp_tracking/patches/v1_0/create_tracking_roles.py` | roles on existing sites |
| `erp_tracking/permissions.py` | role constants and `ensure_*` guards |
| `erp_tracking/integrations/traccar/config.py` | all endpoints, `REPORT_CONFIG`, `LIST_CONFIG` |
| `erp_tracking/integrations/traccar/exceptions.py` | typed errors with user-safe messages |
| `erp_tracking/integrations/traccar/utils.py` | envelope, validation, cache, redaction |
| `erp_tracking/integrations/traccar/auth.py` | `TraccarAuth` — the only credential reader |
| `erp_tracking/integrations/traccar/client.py` | `TraccarClient` — the only HTTP caller |
| `erp_tracking/erp_tracking/doctype/traccar_settings/*` | the Single DocType (JSON + py + js) |
| `erp_tracking/api.py` | `test_connection`, `get_configuration_state` (grows in later phases) |

**Bench**

```bash
bench get-app erp_tracking <repo>
bench --site <site> install-app erp_tracking
bench --site <site> migrate
bench build --app erp_tracking
bench restart
```

**Verify**

1. Open `/app/traccar-settings`. The form shows Connection, Authentication,
   Connection Status and Preferences sections.
2. Enter a demo server (`https://demo.traccar.org/api`) with valid credentials,
   tick Enabled, save.
3. Press **Test Connection** → green "Connection successful" with the Traccar
   version. Enter a wrong password → red "Authentication failed". Point at an
   unreachable host → red "Server unavailable". Set timeout to 1 against a slow
   host → orange "Connection timeout".
4. Open the browser network tab on any of those calls: the response contains
   `success`, `status_code` and `message` and **no** credential.

---

## Phase 2 — Dashboard, devices, groups, users

**Files created**

- `integrations/traccar/listing.py` — the generic list engine
- `integrations/traccar/devices.py`, `groups.py`, `users.py`
- `public/js/erp_tracking.bundle.js`, `core.js`, `list_engine.js`
- `public/css/erp_tracking.bundle.css`
- `erp_tracking/page/erp_tracking_dashboard/*`, `tracking_devices/*`,
  `tracking_device_detail/*`, `tracking_groups/*`, `tracking_users/*`
- `erp_tracking/workspace/erp_tracking/erp_tracking.json`

**Bench**: `bench --site <site> migrate && bench build --app erp_tracking && bench restart`

**Verify**

1. The **ERP Tracking** workspace appears in the sidebar with the nine cards.
2. Dashboard shows the counters and a green **Connected** badge; disabling the
   integration flips it to **Traccar is not configured.**
3. Devices lists real Traccar devices; search, sort, Previous/Next and the
   Export menu all work. Clicking a row opens Device Details with the tabs.

---

## Phase 3 — Live positions, position history, route

**Files created**

- `integrations/traccar/positions.py`
- `public/js/map.js`
- `page/tracking_positions/*`, `page/tracking_position_history/*`

**Verify**

1. Live Positions shows one row per device plus a map with a marker per device.
   The device, group and status filters narrow both.
2. "View on Map" opens the single-position dialog.
3. Position History with a device and a date range draws the polyline and lists
   the fixes. Export → GPX and KML come straight from Traccar
   (`/positions/gpx`, `/positions/kml`); CSV uses `/positions/csv`.
4. Route is reached at `tracking-reports/route` and draws the same track.

---

## Phase 4 — Reports and events

**Files created**

- `integrations/traccar/reports.py`, `events.py`
- `public/js/report_engine.js`
- `page/tracking_reports/*`, `page/tracking_events/*`

**Verify**

1. Visit `tracking-reports/summary`, `/trips`, `/stops`, `/events`, `/route`,
   `/geofences`. Each builds its own filters from the backend metadata.
2. Generating without a device or group returns "Select at least one device or
   one group." rather than a Traccar error.
3. KPI cards appear above each table; paging works on the result set.
4. Export XLSX on trips hits `/reports/trips/xlsx` (check the Traccar access
   log); Export CSV and PDF are produced by Frappe.
5. **Send by Email** returns 204 from `/reports/trips/mail` and shows a
   confirmation.

---

## Phase 5 — Geofences, notifications, commands

**Files created**

- `integrations/traccar/geofences.py`, `notifications.py`, `commands.py`
- `page/tracking_geofences/*`, `page/tracking_notifications/*`,
  `page/tracking_commands/*`

**Verify**

1. As a manager, create a geofence with `CIRCLE (36.80 10.18, 500)`; it appears
   in Traccar. Edit and delete work. As a viewer, the New button is absent.
2. Commands page: **Command Types** lists the types for the chosen device
   (`/commands/types?deviceId=`), and switching "SMS commands" changes the list.
3. **Send Command** to an online device shows green "Command sent" (HTTP 200);
   to an offline device it shows orange "Command queued" (HTTP 202).
4. Signed in as an `ERP Tracking User`, the Commands page is not reachable and
   `erp_tracking.api.send_command` raises a permission error.

---

## Phase 6 — Drivers, maintenance, calendars, orders

**Files created**

- `integrations/traccar/drivers.py`, `maintenance.py`, `calendars.py`, `orders.py`
- `page/tracking_drivers/*`, `tracking_maintenance/*`, `tracking_calendars/*`,
  `tracking_orders/*`

**Verify** each page lists, searches, pages and exports. Calendars show a
schedule and timezone parsed from the iCalendar payload — no invented columns.

---

## Phase 7 — Server, health, statistics, audit, live video

**Files created**

- `integrations/traccar/server.py`, `statistics.py`, `audit.py`, `stream.py`
- `page/tracking_server/*`, `tracking_health/*`, `tracking_statistics/*`,
  `tracking_audit/*`, `tracking_camera/*`

**Verify**

1. Server Information shows only fields `/server` actually returns (`bingKey` is
   excluded on purpose).
2. Server Health shows green **Healthy** with a response time, and re-checks
   every 60 seconds. Stop Traccar → red **Unavailable**.
3. Statistics draws the frappe-charts line chart and the table.
4. Audit Logs is reachable only for managers; a `ERP Tracking User` gets a
   permission error.
5. Live Camera stays disabled until **Enable Live Video** is ticked. With it on,
   the `<video>` element loads `/api/method/erp_tracking.api.stream_playlist`;
   inspect the playlist — the segment URIs point at Frappe, not at Traccar, and
   carry no token.

---

## Phase 8 — Exports, permissions, security, caching, tests, translations

**Files created**

- `erp_tracking/export.py`, `templates/includes/export.html`
- `erp_tracking/translations/fr.csv`
- `erp_tracking/tests/test_auth.py`, `test_client.py`, `test_api.py`,
  `test_export.py`, `test_security.py`, `test_connection.py`

**Bench**

```bash
bench --site <site> set-config allow_tests true
bench --site <site> run-tests --app erp_tracking
```

**Verify**

1. Switch a user's language to French (`fr`) — the navigation reads
   *Tableau de bord*, *Véhicules*, *Trajets*, *Arrêts*, *Rapports*.
2. Export any report with a device filter set; only the filtered rows appear in
   the file.
3. `bench --site <site> run-tests --module erp_tracking.tests.test_security`
   passes, including the assertions that responses never contain secrets.
4. Traccar Settings → **Clear Cache** forces the next page load to re-fetch.

---

## Phase 9 — Full CRUD (Devices, Groups, Users, Drivers, Calendars) and Fleet Overview

Drivers and Geofences already had full backend CRUD from earlier phases;
Devices and Groups had the backend but no whitelisted endpoint or UI; Users
and Calendars had neither. This phase closes every remaining gap without
touching the generic engines (`ListEngine`, `ReportEngine`) or any file not
listed below.

**Files modified**

| File | Change |
| --- | --- |
| `integrations/traccar/users.py` | Added `create_user` / `update_user` / `delete_user`. Password is required on create, sent on update only when the caller actually supplied a new one, and stripped from every response via the existing `TraccarAuth.sanitize_user`. |
| `integrations/traccar/calendars.py` | Added `create_calendar` / `update_calendar` / `delete_calendar`. `get_calendar` now also returns a decoded `ical_text` field (plain text, not the raw base64) purely so the edit dialog has something to prefill - it is re-encoded to base64 before it reaches Traccar. |
| `integrations/traccar/reports.py` | Added `fetch_combined` / `get_combined_report` (`/reports/combined`, previously defined in `TRACCAR_ENDPOINTS` but never wired up) and `build_fleet_overview` / `get_fleet_overview`, which aggregate the *existing* trips/summary/events reports into fleet-wide KPIs and device/driver/group breakdowns. No new Traccar endpoint was introduced for the overview itself. |
| `api.py` | Added `save_device` / `delete_device`, `get_group` / `save_group` / `delete_group`, `save_user` / `delete_user` (manager-only, same gate as `get_users`), `save_calendar` / `delete_calendar`, `get_combined_report`, `get_fleet_overview`, `export_devices_report` (wires up the previously-unused `/reports/devices/{type}` download). |
| `page/tracking_devices/*`, `tracking_device_detail/*` | List page gained a "New Device" action; the detail page (already the "view details" surface) gained Edit/Delete menu items. Both share one dialog builder, `erp_tracking.open_device_dialog`. |
| `page/tracking_groups/*` | Rebuilt on the exact pattern already used by Geofences: primary "New Group" action, row click opens an edit dialog with a "View Devices in Group" button and Delete. |
| `page/tracking_drivers/*` | Same pattern; the backend and `api.py` endpoints (`save_driver`/`delete_driver`) already existed, only the UI was missing. |
| `page/tracking_calendars/*` | Same pattern; editing fetches `get_calendar` first (for `ical_text`), then opens the dialog. |
| `page/tracking_users/*` | Same pattern, restricted to the page's existing Manager-only role list; the password field is write-only (never pre-filled, omitted from the payload entirely when left blank on edit). |
| `page/tracking_reports/*` | Added an `overview` sub-route (`tracking-reports/overview`) rendered by a new `FleetOverview` class in the same file - KPI cards, three `frappe.Chart` breakdowns (by device / driver / group), a trips-per-day chart, and Device/Group/From/To filters using the same `page.add_field` pattern `ReportEngine` already uses. |
| `erp_tracking/workspace/erp_tracking/erp_tracking.json` | Added a "Fleet Overview" link at the top of the existing Reports card. |
| `translations/fr.csv` | Added French strings for every new label. |
| `tests/test_crud_and_overview.py` | New. Covers create/update/delete for all five resources, the password write-only behavior specifically, the iCalendar encode/decode round trip, role enforcement (existing `ROLE_USER`/`ROLE_VIEWER` fixtures from `test_security.py`), the combined-report device/group requirement, and the fleet overview's KPI/breakdown math. |

**Bench**

```bash
bench --site <site> migrate
bench build --app erp_tracking
bench restart
```

No new DocType, Page record, or Python dependency was added, so `migrate`
only needs to re-sync the one workspace JSON that changed.

**Verify**

1. Devices: **New Device** on the list page creates one; open its detail
   page and use the menu's **Edit Device** / **Delete Device**.
2. Groups, Drivers, Calendars: **New …** on each list page creates one;
   click a row to edit; **Delete** in that same dialog removes it. On
   Calendars, confirm the edit dialog shows the original schedule text (not
   a base64 blob) and that re-saving does not corrupt it.
3. Traccar Users (Manager only): create a user with a password, confirm
   the list never shows it; edit the same user leaving the password field
   blank and confirm the password still works to log into Traccar directly;
   set a new password and confirm the old one stops working.
4. Visit `tracking-reports/overview` (or the workspace's new **Fleet
   Overview** link): KPI cards and three breakdown charts render for the
   default date range; changing the Device/Group filters and clicking
   **Generate** updates them; clearing all devices/groups and generating
   shows the "no devices or groups selected" empty state rather than an
   error.
5. `bench --site <site> run-tests --module erp_tracking.tests.test_crud_and_overview`
   passes, and the full suite (`run-tests --app erp_tracking`) still passes -
   nothing from Phases 1-8 was changed.

---

## Useful commands

```bash
# reload a single doctype or page after editing its JSON
bench --site <site> reload-doc erp_tracking doctype traccar_settings
bench --site <site> migrate

# rebuild assets after touching public/js or public/css
bench build --app erp_tracking

# watch the integration log (endpoint, method, status, duration — never secrets)
tail -f sites/<site>/logs/erp_tracking.log

# clear caches when a page does not appear
bench --site <site> clear-cache && bench --site <site> clear-website-cache
```
