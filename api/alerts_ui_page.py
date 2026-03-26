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
  <label for="status_filter">Status:</label>
  <select id="status_filter">
    <option value="">All</option>
    <option value="open">open</option>
    <option value="resolved">resolved</option>
  </select>
  <button id="refresh_alerts">Refresh</button>
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
  <label for="resolved_by">resolved_by:</label>
  <input id="resolved_by" type="text" placeholder="ops_user_1" />
  <button id="resolve_alert" disabled>Resolve selected alert</button>
  <pre id="detail_output" class="muted">Select an alert row to load details.</pre>

  <script>
    const tenantInput = document.getElementById("tenant_id");
    const loadButton = document.getElementById("load_alerts");
    const statusNode = document.getElementById("status");
    const errorNode = document.getElementById("error");
    const statusFilter = document.getElementById("status_filter");
    const refreshButton = document.getElementById("refresh_alerts");
    const bodyNode = document.getElementById("alerts_body");
    const detailNode = document.getElementById("detail_output");
    const resolvedByInput = document.getElementById("resolved_by");
    const resolveButton = document.getElementById("resolve_alert");
    let selectedAlertId = null;
    let selectedTenantId = null;
    let selectedStatus = null;

    function setStatus(message) { statusNode.textContent = message || ""; }
    function setError(message) { errorNode.textContent = message || ""; }

    function syncResolveButtonState() {
      const resolvedBy = resolvedByInput.value.trim();
      if (!selectedAlertId || !selectedTenantId) {
        resolveButton.disabled = true;
        return;
      }
      if (selectedStatus === "resolved") {
        resolveButton.disabled = true;
        return;
      }
      resolveButton.disabled = resolvedBy.length === 0;
    }

    async function loadDetail(tenantId, opsAlertId) {
      setError("");
      detailNode.textContent = "Loading detail...";
      const response = await fetch(`/internal/alerts/${encodeURIComponent(opsAlertId)}/detail?tenant_id=${encodeURIComponent(tenantId)}`);
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        detailNode.textContent = "";
        setError(payload?.error?.message || "Failed to load alert detail.");
        selectedAlertId = null;
        selectedTenantId = null;
        selectedStatus = null;
        syncResolveButtonState();
        return;
      }
      selectedAlertId = opsAlertId;
      selectedTenantId = tenantId;
      selectedStatus = payload.data?.status || null;
      syncResolveButtonState();
      detailNode.textContent = JSON.stringify(payload.data, null, 2);
      if (selectedStatus === "resolved") {
        setStatus("Alert is already resolved.");
      }
    }

    async function loadAlerts() {
      const tenantId = tenantInput.value.trim();
      bodyNode.innerHTML = "";
      detailNode.textContent = "Select an alert row to load details.";
      selectedAlertId = null;
      selectedTenantId = null;
      selectedStatus = null;
      syncResolveButtonState();
      setError("");

      if (!tenantId) {
        setStatus("");
        setError("tenant_id is required.");
        return;
      }

      setStatus("Loading...");
      const statusValue = statusFilter.value;
      const query = new URLSearchParams({ tenant_id: tenantId });
      if (statusValue) {
        query.set("status", statusValue);
      }
      const response = await fetch(`/internal/alerts?${query.toString()}`);
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

    async function resolveSelectedAlert() {
      setError("");
      if (!selectedAlertId || !selectedTenantId) {
        setError("Select an alert first.");
        return;
      }
      const resolvedBy = resolvedByInput.value.trim();
      if (!resolvedBy) {
        setError("resolved_by is required.");
        syncResolveButtonState();
        return;
      }
      setStatus("Resolving...");
      const response = await fetch(
        `/internal/alerts/${encodeURIComponent(selectedAlertId)}/resolve?tenant_id=${encodeURIComponent(selectedTenantId)}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ resolved_by: resolvedBy }),
        }
      );
      const payload = await response.json();
      if (!response.ok || !payload.success) {
        setStatus("");
        setError(payload?.error?.message || "Failed to resolve alert.");
        return;
      }

      setStatus(`Resolved ${selectedAlertId}.`);
      const tenantIdToRefresh = selectedTenantId;
      const alertIdToRefresh = selectedAlertId;
      await loadAlerts();
      await loadDetail(tenantIdToRefresh, alertIdToRefresh);
    }

    loadButton.addEventListener("click", loadAlerts);
    refreshButton.addEventListener("click", loadAlerts);
    statusFilter.addEventListener("change", () => {
      if (tenantInput.value.trim()) {
        loadAlerts();
      }
    });
    resolveButton.addEventListener("click", resolveSelectedAlert);
    resolvedByInput.addEventListener("input", syncResolveButtonState);
  </script>
</body>
</html>
"""
