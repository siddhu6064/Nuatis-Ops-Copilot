"""Minimal operator UI page for alert read workflows."""

from __future__ import annotations


def render_alerts_ui_page() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Nuatis Ops Alerts</title>
  <style>
    body { font-family: sans-serif; margin: 1rem; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border: 1px solid #ccc; padding: 0.4rem; text-align: left; }
    tr:hover { background: #f7f7f7; cursor: pointer; }
    .muted { color: #666; }
    #error { color: #a40000; }
    pre { background: #f5f5f5; padding: 0.6rem; overflow-x: auto; }
  </style>
</head>
<body>
  <h1>Ops Alerts</h1>
  <label for="tenant_id">Tenant ID:</label>
  <input id="tenant_id" type="text" placeholder="tenant_a" />
  <button id="load_alerts">Load alerts</button>
  <p id="status" class="muted"></p>
  <p id="error"></p>

  <table aria-label="alerts table">
    <thead>
      <tr>
        <th>ops_alert_id</th>
        <th>status</th>
        <th>alert_type</th>
        <th>created_at</th>
      </tr>
    </thead>
    <tbody id="alerts_body"></tbody>
  </table>

  <h2>Alert detail</h2>
  <pre id="detail_output" class="muted">Select an alert row to load details.</pre>

  <script>
    const tenantInput = document.getElementById("tenant_id");
    const loadButton = document.getElementById("load_alerts");
    const statusNode = document.getElementById("status");
    const errorNode = document.getElementById("error");
    const bodyNode = document.getElementById("alerts_body");
    const detailNode = document.getElementById("detail_output");

    function setStatus(message) { statusNode.textContent = message || ""; }
    function setError(message) { errorNode.textContent = message || ""; }

    async function loadDetail(tenantId, opsAlertId) {
      setError("");
      detailNode.textContent = "Loading detail...";
      const response = await fetch(`/internal/alerts/${encodeURIComponent(opsAlertId)}/detail?tenant_id=${encodeURIComponent(tenantId)}`);
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        detailNode.textContent = "";
        setError(payload?.error?.message || "Failed to load alert detail.");
        return;
      }
      detailNode.textContent = JSON.stringify(payload.data, null, 2);
    }

    async function loadAlerts() {
      const tenantId = tenantInput.value.trim();
      bodyNode.innerHTML = "";
      detailNode.textContent = "Select an alert row to load details.";
      setError("");

      if (!tenantId) {
        setStatus("");
        setError("tenant_id is required.");
        return;
      }

      setStatus("Loading...");
      const response = await fetch(`/internal/alerts?tenant_id=${encodeURIComponent(tenantId)}`);
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        setStatus("");
        setError(payload?.error?.message || "Failed to load alerts.");
        return;
      }

      const alerts = payload.data || [];
      if (alerts.length === 0) {
        setStatus("No alerts found.");
        return;
      }

      setStatus(`Loaded ${alerts.length} alert(s). Click a row for detail.`);
      alerts.forEach((alert) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${alert.ops_alert_id || ""}</td>
          <td>${alert.status || ""}</td>
          <td>${alert.alert_type || ""}</td>
          <td>${alert.created_at || ""}</td>
        `;
        row.addEventListener("click", () => loadDetail(tenantId, alert.ops_alert_id));
        bodyNode.appendChild(row);
      });
    }

    loadButton.addEventListener("click", loadAlerts);
  </script>
</body>
</html>
"""
