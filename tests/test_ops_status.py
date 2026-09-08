"""tests/test_ops_status.py — one-page operator dashboard."""
def test_ops_status_renders(client):
    resp = client.get("/ops/status")
    assert resp.status_code == 200
    body = resp.text
    for label in ("/healthz", "/healthz/db", "/healthz/deps",
                  "/healthz/schema", "/healthz/errors", "/auditoria"):
        assert label in body, f"Missing {label} in /ops/status"


def test_ops_status_lists_each_endpoint_with_purpose(client):
    body = client.get("/ops/status").text
    for purpose in ("Liveness", "Database", "Schema drift", "Error counter"):
        assert purpose in body, f"Missing purpose label: {purpose}"


def test_ops_status_includes_action_button(client):
    body = client.get("/ops/status").text
    # Has at least one clickable button (an Open/Refresh action).
    assert "button" in body.lower() or "Abrir" in body
