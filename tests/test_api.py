"""API end-to-end tests: push, list, detail, resolve, delete, suspected offline"""

from datetime import timedelta
from sqlmodel import Session, select

from cmdb.models import Device, utcnow


def make_push(**overrides) -> dict:
    """Build a base push payload, overridable per field"""
    base = {
        "hostname": "demo-node-01",
        "serial_number": "DEMO-SN-0001",
        "mgmt": {
            "mac": "02:00:00:00:00:01",
            "ip": "192.0.2.11",
            "prefix_length": 24,
        },
        "nics": [
            {"name": "eth0", "mac": "02:00:00:00:00:02",
             "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]},
            {"name": "eth1", "mac": "02:00:00:00:00:03",
             "ips": [{"ip": "198.51.100.13", "prefix_length": 24}]},
        ],
        "full_sync": True,
        "source": "collector",
    }
    base.update(overrides)
    return base


def test_push_created_and_unchanged(client):
    r1 = client.post("/api/v1/devices", json=make_push())
    assert r1.status_code == 200
    assert r1.json()["result"] == "created"

    r2 = client.post("/api/v1/devices", json=make_push())
    assert r2.json()["result"] == "unchanged"


def test_push_diff_created(client):
    client.post("/api/v1/devices", json=make_push())
    push = make_push(mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                           "prefix_length": 24})
    r = client.post("/api/v1/devices", json=push)
    body = r.json()
    assert body["result"] == "diff_created"
    assert body["pending_change_id"] is not None


def test_push_invalid_payload_422(client):
    r = client.post("/api/v1/devices", json={"nics": []})
    assert r.status_code == 422


def test_new_format_push_with_gpu(client):
    """New format push: agent/os/hardware structure, GPU stored, os fields persisted"""
    push = {
        "agent": {"version": "0.1.0", "source": "collector",
                  "timestamp": "2026-09-13T10:00:00+08:00"},
        "os": {"hostname": "demo-node-01", "type": "linux",
               "version": "Ubuntu 22.04.5 LTS", "kernel": "5.15.0-131-generic"},
        "mgmt": {"mac": "02:00:00:00:00:01", "ip": "192.0.2.11",
                 "prefix_length": 24},
        "hardware": {
            "chassis_serial_number": "DEMO-SN-0001",
            "gpu": {"slots": [
                {"uuid": "GPU-abc", "name": "NVIDIA H100 80GB HBM3",
                 "serial_number": "DEMO-SN-0007", "size": 80, "size_unit": "GB",
                 "driver_version": "535.183.01", "pcie_id": "0000:1B:00.0"}
            ]},
        },
    }
    r = client.post("/api/v1/devices", json=push)
    assert r.status_code == 200
    assert r.json()["result"] == "created"

    detail = client.get("/api/v1/devices/1").json()
    assert detail["os_type"] == "linux"
    assert detail["os_version"] == "Ubuntu 22.04.5 LTS"
    assert detail["kernel"] == "5.15.0-131-generic"
    assert detail["agent_version"] == "0.1.0"
    assert len(detail["gpus"]) == 1
    assert detail["gpus"][0]["uuid"] == "GPU-abc"
    assert detail["gpus"][0]["size_gb"] == 80


def test_legacy_format_compatible(client):
    """Legacy format (top-level hostname etc.) auto-converted, old collectors keep working"""
    legacy = {
        "hostname": "demo-node-01",
        "serial_number": "DEMO-SN-0001",
        "nics": [{"name": "eth0", "mac": "02:00:00:00:00:02",
                  "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]}],
        "full_sync": False,
        "source": "collector",
    }
    r = client.post("/api/v1/devices", json=legacy)
    assert r.status_code == 200
    assert r.json()["result"] == "created"
    detail = client.get("/api/v1/devices/1").json()
    assert detail["hostname"] == "demo-node-01"
    assert detail["serial_number"] == "DEMO-SN-0001"


def test_list_and_detail(client):
    client.post("/api/v1/devices", json=make_push())

    r = client.get("/api/v1/devices")
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["status"] == "active"
    assert len(item["nics"]) == 2

    device_id = item["id"]
    detail = client.get(f"/api/v1/devices/{device_id}").json()
    assert detail["hostname"] == "demo-node-01"
    assert detail["nics"][0]["ips"][0]["ip"] == "198.51.100.11"


def test_list_search_and_status_filter(client, engine):
    client.post("/api/v1/devices", json=make_push())

    r = client.get("/api/v1/devices", params={"search": "nomatch"})
    assert r.json()["total"] == 0
    r = client.get("/api/v1/devices", params={"search": "demo-node"})
    assert r.json()["total"] == 1

    # manually backdate last_pushed_at by 4 days -> suspected_offline
    with Session(engine) as session:
        device = session.exec(select(Device)).one()
        device.last_pushed_at = utcnow() - timedelta(days=4)
        session.add(device)
        session.commit()

    r = client.get("/api/v1/devices", params={"status": "suspected_offline"})
    assert r.json()["total"] == 1
    r = client.get("/api/v1/devices", params={"status": "active"})
    assert r.json()["total"] == 0


def test_resolve_flow(client):
    client.post("/api/v1/devices", json=make_push())
    push = make_push(mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                           "prefix_length": 24},
                     nics=[{"name": "eth0", "mac": "02:00:00:00:00:02",
                            "ips": [{"ip": "198.51.100.11", "prefix_length": 24}]}])
    pending_id = client.post("/api/v1/devices", json=push).json()["pending_change_id"]

    # pending resolution list
    items = client.get("/api/v1/pending-changes").json()["items"]
    assert len(items) == 1 and items[0]["id"] == pending_id

    # diff detail
    detail = client.get(f"/api/v1/pending-changes/{pending_id}").json()
    assert detail["payload"]["mgmt"]["ip"] == "192.0.2.12"
    fields = {f["field"] for f in detail["diff"]["fields"]}
    assert fields == {"mgmt.ip"}

    # resolve: use new value for mgmt.ip, delete eth1
    r = client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {"mgmt.ip": "new"}, "nic_choices": {"eth1": "new"}},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "applied"

    # device data updated per the resolution
    device = client.get("/api/v1/devices/1").json()
    assert device["mgmt_ip"] == "192.0.2.12"
    assert [n["name"] for n in device["nics"]] == ["eth0"]

    # resolving twice -> 409
    r = client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {}, "nic_choices": {}},
    )
    assert r.status_code == 409


def test_resolve_discard(client):
    client.post("/api/v1/devices", json=make_push())
    push = make_push(mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                           "prefix_length": 24})
    pending_id = client.post("/api/v1/devices", json=push).json()["pending_change_id"]

    r = client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {"mgmt.ip": "old"}, "nic_choices": {}},
    )
    assert r.status_code == 200

    device = client.get("/api/v1/devices/1").json()
    assert device["mgmt_ip"] == "192.0.2.11"  # original value kept


def test_change_history(client):
    client.post("/api/v1/devices", json=make_push())
    push = make_push(mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                           "prefix_length": 24})
    pending_id = client.post("/api/v1/devices", json=push).json()["pending_change_id"]
    client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {"mgmt.ip": "new"}, "nic_choices": {}},
    )

    r = client.get("/api/v1/change-history", params={"device_id": 1})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert "mgmt.ip" in items[0]["summary"]


def test_delete_device(client):
    client.post("/api/v1/devices", json=make_push())
    r = client.delete("/api/v1/devices/1")
    assert r.status_code == 204
    assert client.get("/api/v1/devices/1").status_code == 404
    assert client.delete("/api/v1/devices/1").status_code == 404


def test_list_sort_and_multi_field_search(client):
    client.post("/api/v1/devices", json=make_push())
    client.post("/api/v1/devices", json=make_push(
        hostname="S1B02DC-VL102",
        serial_number="DEMO-SN-0012",
        mgmt={"mac": "02:00:00:00:00:11", "ip": "10.0.0.5", "prefix_length": 24},
    ))

    # sort by management IP descending
    r = client.get("/api/v1/devices", params={"sort_by": "mgmt_ip", "sort_order": "desc"})
    items = r.json()["items"]
    assert items[0]["mgmt_ip"] > items[-1]["mgmt_ip"]

    # sort by management IP ascending
    r = client.get("/api/v1/devices", params={"sort_by": "mgmt_ip", "sort_order": "asc"})
    items = r.json()["items"]
    assert items[0]["mgmt_ip"] < items[-1]["mgmt_ip"]

    # search covers serial number and management IP
    r = client.get("/api/v1/devices", params={"search": "DEMO-SN-0012"})
    assert r.json()["total"] == 1
    r = client.get("/api/v1/devices", params={"search": "10.0.0.5"})
    assert r.json()["total"] == 1

    # sorting by a non-whitelisted field -> falls back to default hostname sort, no error
    r = client.get("/api/v1/devices", params={"sort_by": "hostname; DROP TABLE"})
    assert r.status_code == 200


def test_dashboard(client):
    client.post("/api/v1/devices", json=make_push())
    body = client.get("/api/v1/dashboard").json()
    assert body["total_devices"] == 1
    assert body["active"] == 1
    assert body["suspected_offline"] == 0
    assert body["pending_changes"] == 0


def test_ip_reverse_search(client):
    """Searching a NIC business IP finds the device via reverse lookup"""
    client.post("/api/v1/devices", json=make_push())
    r = client.get("/api/v1/devices", params={"search": "198.51.100.13"})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["hostname"] == "demo-node-01"


def test_tags(client):
    client.post("/api/v1/devices", json=make_push())
    r = client.put("/api/v1/devices/1/tags", json={"tags": ["生产", "web"]})
    assert r.json()["tags"] == ["生产", "web"]

    items = client.get("/api/v1/devices").json()["items"]
    assert items[0]["tags"] == ["生产", "web"]

    r = client.get("/api/v1/devices", params={"tag": "生产"})
    assert r.json()["total"] == 1
    r = client.get("/api/v1/devices", params={"tag": "测试"})
    assert r.json()["total"] == 0

    # exact match: the old implementation used substring LIKE, "生产" would wrongly match "生产基地"
    client.post("/api/v1/devices", json=make_push(hostname="S1B02DC-VL102"))
    client.put("/api/v1/devices/2/tags", json={"tags": ["生产基地"]})
    r = client.get("/api/v1/devices", params={"tag": "生产"})
    assert r.json()["total"] == 1  # only devices whose tag is exactly "生产" match


def test_import_csv_preserves_last_pushed_at(client):
    """Re-import does not backdate last_pushed_at: the unchanged branch does not refresh the last push time"""
    client.post("/api/v1/devices", json=make_push())
    original = client.get("/api/v1/devices/1").json()["last_pushed_at"]

    csv_content = client.get("/api/v1/devices/export/csv").text
    client.post(
        "/api/v1/devices/import/csv",
        files={"file": ("devices.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    after = client.get("/api/v1/devices/1").json()["last_pushed_at"]
    assert after == original


def test_disk_size_gb_normalized(client):
    """Disk push normalizes size_gb: TB converted at 1024, GB kept as-is"""
    push = make_push(
        disks=[
            {"serial_number": "S1", "type": "SSD", "size": 512, "size_unit": "GB"},
            {"serial_number": "S2", "type": "HDD", "size": 8, "size_unit": "TB"},
        ]
    )
    client.post("/api/v1/devices", json=push)
    detail = client.get("/api/v1/devices/1").json()
    sizes = {d["serial_number"]: d["size_gb"] for d in detail["disks"]}
    assert sizes["S1"] == 512
    assert sizes["S2"] == 8192


def test_batch_delete(client):
    client.post("/api/v1/devices", json=make_push())
    client.post("/api/v1/devices", json=make_push(hostname="S1B02DC-VL102"))
    r = client.post("/api/v1/devices/batch-delete", json={"ids": [1, 2, 999]})
    assert r.json()["deleted"] == [1, 2]
    assert client.get("/api/v1/devices").json()["total"] == 0


def test_history_detail(client):
    client.post("/api/v1/devices", json=make_push())
    push = make_push(mgmt={"mac": "02:00:00:00:00:01", "ip": "192.0.2.12",
                           "prefix_length": 24})
    pending_id = client.post("/api/v1/devices", json=push).json()["pending_change_id"]
    client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {"mgmt.ip": "new"}, "nic_choices": {}},
    )

    body = client.get("/api/v1/change-history/1").json()
    assert body["summary"] == "mgmt.ip: 192.0.2.11 -> 192.0.2.12"
    assert body["diff"]["fields"][0]["field"] == "mgmt.ip"


def test_export_csv(client):
    client.post("/api/v1/devices", json=make_push())
    r = client.get("/api/v1/devices/export/csv")
    assert r.status_code == 200
    assert "demo-node-01" in r.text
    assert r.text.lstrip("﻿").startswith("hostname")


def test_import_csv_roundtrip(client):
    """Exported CSV re-imported directly -> unchanged (format matches the export)"""
    client.post("/api/v1/devices", json=make_push())
    csv_content = client.get("/api/v1/devices/export/csv").text

    r = client.post(
        "/api/v1/devices/import/csv",
        files={"file": ("devices.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    body = r.json()
    assert body["unchanged"] == 1
    assert body["created"] == 0


def test_import_csv_creates_devices(client):
    csv_content = (
        "hostname,serial_number,mgmt_mac,mgmt_ip,mgmt_prefix_length,"
        "purpose,status,last_pushed_at,nics\n"
        'demo-node-02,DEMO-SN-0008,02:00:00:00:00:01,192.0.2.13,24,'
        'web 服务,active,2026-09-11T10:00:00,'
        '"eth0(02:00:00:00:00:02): 198.51.100.15/24"\n'
    )
    r = client.post(
        "/api/v1/devices/import/csv",
        files={"file": ("devices.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    body = r.json()
    assert body["created"] == 1

    # device + purpose + NIC IP imported
    detail = client.get("/api/v1/devices/1").json()
    assert detail["hostname"] == "demo-node-02"
    assert detail["purpose"] == "web 服务"
    assert detail["nics"][0]["ips"][0]["ip"] == "198.51.100.15"

    # reverse IP lookup finds the imported device
    r = client.get("/api/v1/devices", params={"search": "198.51.100.15"})
    assert r.json()["total"] == 1


def test_import_csv_conflict_goes_to_pending(client):
    client.post("/api/v1/devices", json=make_push())
    csv_content = (
        "hostname,serial_number,mgmt_mac,mgmt_ip,mgmt_prefix_length,"
        "purpose,status,last_pushed_at,nics\n"
        "demo-node-01,DEMO-SN-0001,02:00:00:00:00:01,192.0.2.12,24,,active,,\n"
    )
    r = client.post(
        "/api/v1/devices/import/csv",
        files={"file": ("devices.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    body = r.json()
    assert body["diff_created"] == 1

    # existing data unchanged, pending created
    assert client.get("/api/v1/devices/1").json()["mgmt_ip"] == "192.0.2.11"
    pendings = client.get("/api/v1/pending-changes").json()["items"]
    assert len(pendings) == 1
    assert pendings[0]["source"] == "csv_import"


def test_import_csv_skips_malformed_rows(client):
    csv_content = (
        "hostname,serial_number,mgmt_mac,mgmt_ip,mgmt_prefix_length,"
        "purpose,status,last_pushed_at,nics\n"
        ",no-hostname-here,,,,active,,\n"
        "demo-node-02,DEMO-SN-0008,02:00:00:00:00:01,192.0.2.13,24,,active,,\n"
    )
    r = client.post(
        "/api/v1/devices/import/csv",
        files={"file": ("devices.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    body = r.json()
    assert body["created"] == 1
    assert len(body["errors"]) == 1  # the row missing hostname is recorded in errors
    assert "hostname" in body["errors"][0]


def test_spa_fallback(client):
    """Frontend route refresh falls back to index.html; unknown API paths stay 404"""
    r = client.get("/devices")
    assert r.status_code == 200
    assert '<div id="app">' in r.text

    r = client.get("/conflicts")
    assert r.status_code == 200

    r = client.get("/api/v1/nonexistent")
    assert r.status_code == 404


def test_push_memory_and_cpu_end_to_end(client):
    """Push with memory/CPU: created -> visible in detail -> model diff -> resolution applied"""
    push = make_push(
        memory={
            "slots": [
                {"slot": "DIMM_A1", "manufacturer": "Samsung",
                 "part_number": "M321R8GA0BB0-CQKZJ", "type": "DDR5",
                 "size_gb": 64, "speed_mts": 4800, "serial_number": "DEMO-MEM-01"}
            ]
        },
        cpus=[
            {"slot": "CPU0", "model": "Intel(R) Xeon(R) Gold 6448Y"},
            {"slot": "CPU1", "model": "Intel(R) Xeon(R) Gold 6448Y"},
        ],
    )
    r = client.post("/api/v1/devices", json=push)
    assert r.json()["result"] == "created"

    device_id = r.json()["device_id"]
    body = client.get(f"/api/v1/devices/{device_id}").json()
    assert body["memory"][0]["slot"] == "DIMM_A1"
    assert body["memory"][0]["part_number"] == "M321R8GA0BB0-CQKZJ"
    assert body["memory"][0]["size_gb"] == 64
    assert body["memory"][0]["speed_mts"] == 4800
    assert [c["slot"] for c in body["cpus"]] == ["CPU0", "CPU1"]

    # change CPU model -> diff -> resolution adopts the new value
    push2 = make_push(
        memory=push["memory"],
        cpus=[
            {"slot": "CPU0", "model": "Intel(R) Xeon(R) Gold 6548Y"},
            {"slot": "CPU1", "model": "Intel(R) Xeon(R) Gold 6448Y"},
        ],
    )
    r = client.post("/api/v1/devices", json=push2)
    pending_id = r.json()["pending_change_id"]
    assert r.json()["result"] == "diff_created"

    r = client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {}, "nic_choices": {}, "cpu_choices": {"CPU0": "new"}},
    )
    assert r.status_code == 200
    assert r.json()["applied"] == ["CPU CPU0 model: Intel(R) Xeon(R) Gold 6448Y -> Intel(R) Xeon(R) Gold 6548Y"]

    body = client.get(f"/api/v1/devices/{device_id}").json()
    assert body["cpus"][0]["model"] == "Intel(R) Xeon(R) Gold 6548Y"


def test_push_disk_and_psu_end_to_end(client):
    """Push with disks/PSUs: created -> visible in detail -> model diff -> resolution applied"""
    push = make_push(
        disks=[
            {"serial_number": "DEMO-SN-0010", "type": "SSD",
             "manufacturer": "Samsung", "model": "990EVO",
             "size": 8, "size_unit": "TB"},
            {"serial_number": "DEMO-SN-0011", "type": "HDD",
             "manufacturer": "HGST", "model": "HUH728080ALE604",
             "size": 8, "size_unit": "TB"},
        ],
        psus=[
            {"serial_number": "DEMO-SN-0005", "manufacturer": "GreatWall",
             "model": "CRPS2700D2", "max_power_w": 2700},
        ],
    )
    r = client.post("/api/v1/devices", json=push)
    assert r.json()["result"] == "created"

    device_id = r.json()["device_id"]
    body = client.get(f"/api/v1/devices/{device_id}").json()
    assert body["disks"][0]["model"] == "990EVO"
    assert body["disks"][0]["size"] == 8
    assert body["disks"][0]["size_unit"] == "TB"
    assert [p["serial_number"] for p in body["psus"]] == ["DEMO-SN-0005"]

    # disk model change -> diff -> resolution adopts the new value
    push2 = make_push(
        disks=[
            {"serial_number": "DEMO-SN-0010", "type": "SSD",
             "manufacturer": "Samsung", "model": "990PRO",
             "size": 8, "size_unit": "TB"},
            {"serial_number": "DEMO-SN-0011", "type": "HDD",
             "manufacturer": "HGST", "model": "HUH728080ALE604",
             "size": 8, "size_unit": "TB"},
        ],
        psus=push["psus"],
    )
    r = client.post("/api/v1/devices", json=push2)
    pending_id = r.json()["pending_change_id"]
    assert r.json()["result"] == "diff_created"

    r = client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {}, "nic_choices": {}, "disk_choices": {"DEMO-SN-0010": "new"}},
    )
    assert r.status_code == 200
    assert "硬盘 DEMO-SN-0010 model: 990EVO -> 990PRO" in r.json()["applied"]

    body = client.get(f"/api/v1/devices/{device_id}").json()
    assert body["disks"][0]["model"] == "990PRO"


def test_push_open_without_login(guest):
    """Push endpoint requires no auth: collectors can push without logging in"""
    r = guest.post("/api/v1/devices", json=make_push())
    assert r.status_code == 200
    assert r.json()["result"] == "created"


def test_api_requires_login(guest):
    """Without login, all APIs except push return 401"""
    assert guest.get("/api/v1/devices").status_code == 401
    assert guest.get("/api/v1/dashboard").status_code == 401
    assert guest.get("/api/v1/pending-changes").status_code == 401
    assert guest.get("/api/v1/auth/me").json()["detail"] == "未登录"


def test_login_flow(guest):
    """Successful login issues a session cookie granting access to protected APIs; wrong password returns 401"""
    r = guest.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401
    assert guest.get("/api/v1/devices").status_code == 401

    r = guest.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    # TestClient automatically carries the session cookie issued in the previous step
    assert guest.get("/api/v1/devices").status_code == 200
    assert guest.get("/api/v1/auth/me").json()["username"] == "admin"

    guest.post("/api/v1/auth/logout")
    assert guest.get("/api/v1/devices").status_code == 401


def _login_as(client, username, password):
    return client.post("/api/v1/auth/login", json={"username": username, "password": password})


def test_user_management_crud(client):
    """admin creates a viewer user who can log in; user list/delete work"""
    r = client.post("/api/v1/users", json={"username": "ops1", "password": "ops123", "role": "viewer"})
    assert r.status_code == 200
    user_id = r.json()["id"]

    users = client.get("/api/v1/users").json()["items"]
    assert {u["username"] for u in users} >= {"admin", "ops1"}

    # the new user can log in
    assert _login_as(client, "ops1", "ops123").status_code == 200

    # reset password (switching back to admin)
    assert _login_as(client, "admin", "admin").status_code == 200
    assert client.put(f"/api/v1/users/{user_id}", json={"password": "newpass"}).status_code == 200
    assert _login_as(client, "ops1", "ops123").status_code == 401
    assert _login_as(client, "ops1", "newpass").status_code == 200
    assert _login_as(client, "admin", "admin").status_code == 200

    # delete
    assert client.delete(f"/api/v1/users/{user_id}").status_code == 200
    assert _login_as(client, "ops1", "newpass").status_code == 401


def test_last_admin_protected(client):
    """The last admin cannot be deleted or demoted"""
    admins = [u for u in client.get("/api/v1/users").json()["items"] if u["role"] == "admin"]
    admin_id = admins[0]["id"]
    assert client.delete(f"/api/v1/users/{admin_id}").status_code == 409
    assert client.put(f"/api/v1/users/{admin_id}", json={"role": "viewer"}).status_code == 409


def test_viewer_readonly_permissions(client):
    """viewer is read-only: resolve/delete/tags/user management all 403, GET works"""
    client.post("/api/v1/users", json={"username": "viewer1", "password": "v1pass", "role": "viewer"})
    client.post("/api/v1/devices", json=make_push())
    assert _login_as(client, "viewer1", "v1pass").status_code == 200

    # GET works
    assert client.get("/api/v1/devices").status_code == 200
    assert client.get("/api/v1/dashboard").status_code == 200
    assert client.get("/api/v1/auth/me").json()["role"] == "viewer"

    # write operations return 403
    assert client.post("/api/v1/pending-changes/1/resolve", json={}).status_code == 403
    assert client.delete("/api/v1/devices/1").status_code == 403
    assert client.post("/api/v1/devices/batch-delete", json={"ids": [1]}).status_code == 403
    assert client.put("/api/v1/devices/1/tags", json={"tags": ["x"]}).status_code == 403
    assert client.get("/api/v1/users").status_code == 403
    assert client.post("/api/v1/users", json={"username": "x", "password": "y"}).status_code == 403


def test_change_own_password(client):
    """Current user changes their own password: verifies the old password, available to all roles"""
    r = client.post("/api/v1/auth/change-password", json={"old_password": "wrong", "new_password": "newpass"})
    assert r.status_code == 401

    r = client.post("/api/v1/auth/change-password", json={"old_password": "admin", "new_password": "newpass"})
    assert r.status_code == 200

    # old password no longer works, new password can log in
    assert _login_as(client, "admin", "admin").status_code == 401
    assert _login_as(client, "admin", "newpass").status_code == 200


def test_system_settings_read_update(client):
    """System settings: GET/PUT, device status reacts immediately after a threshold change"""
    # default is 24 hours, API key feature off
    r = client.get("/api/v1/settings/system")
    assert r.status_code == 200
    assert r.json() == {"offline_threshold_hours": 24, "api_key_enabled": False}

    client.post("/api/v1/devices", json=make_push())

    # threshold set to 1 hour -> a push from 2 hours ago becomes suspected offline
    r = client.put("/api/v1/settings/system", json={"offline_threshold_hours": 1})
    assert r.status_code == 200
    assert r.json() == {"offline_threshold_hours": 1, "api_key_enabled": False}

    # manually backdate last_pushed_at by 2 hours -> beyond the 1 hour threshold -> suspected_offline
    from cmdb.database import get_engine_cached
    from cmdb.models import Device
    from sqlmodel import Session as S, select

    engine = get_engine_cached()
    with S(engine) as s:
        device = s.exec(select(Device)).first()
        device.last_pushed_at = utcnow() - timedelta(hours=2)
        s.add(device)
        s.commit()
    r = client.get("/api/v1/devices")
    assert r.status_code == 200
    assert r.json()["items"][0]["status"] == "suspected_offline"

    # threshold set to 72 hours -> back to active
    client.put("/api/v1/settings/system", json={"offline_threshold_hours": 72})
    r = client.get("/api/v1/devices")
    assert r.json()["items"][0]["status"] == "active"

    # invalid value -> 422
    r = client.put("/api/v1/settings/system", json={"offline_threshold_hours": 0})
    assert r.status_code == 422


def test_system_settings_viewer_forbidden(client):
    """viewer is read-only, PUT returns 403"""
    client.post(
        "/api/v1/users", json={"username": "viewer1", "password": "v1pass", "role": "viewer"}
    )
    assert _login_as(client, "viewer1", "v1pass").status_code == 200
    assert client.get("/api/v1/settings/system").status_code == 200
    assert client.put("/api/v1/settings/system", json={"offline_threshold_hours": 48}).status_code == 403


def test_device_metadata_update(client):
    """PUT /metadata: server/rack location, owner, purpose; None keeps the value, empty string clears it"""
    r = client.post("/api/v1/devices", json=make_push())
    device_id = r.json()["device_id"]

    # empty by default
    r = client.get(f"/api/v1/devices/{device_id}")
    assert r.json()["location"] is None
    assert r.json()["owner"] is None
    assert r.json()["purpose"] is None

    # set metadata
    r = client.put(
        f"/api/v1/devices/{device_id}/metadata",
        json={"location": "A栋-3F-01", "owner": "张三", "purpose": "web 服务"},
    )
    assert r.status_code == 200
    assert r.json()["location"] == "A栋-3F-01"
    assert r.json()["owner"] == "张三"
    assert r.json()["purpose"] == "web 服务"

    # a push does not change metadata
    client.post("/api/v1/devices", json=make_push())
    r = client.get(f"/api/v1/devices/{device_id}")
    assert r.json()["location"] == "A栋-3F-01"

    # None keeps the value, empty string clears it
    r = client.put(
        f"/api/v1/devices/{device_id}/metadata",
        json={"location": None, "owner": ""},
    )
    assert r.status_code == 200
    r = client.get(f"/api/v1/devices/{device_id}")
    assert r.json()["location"] == "A栋-3F-01"
    assert r.json()["owner"] is None
    assert r.json()["purpose"] == "web 服务"

    # nonexistent device -> 404
    r = client.put("/api/v1/devices/99999/metadata", json={"owner": "x"})
    assert r.status_code == 404


def test_audit_logs_recorded_and_listed(client):
    """Admin operations are recorded in audit logs, GET /audit-logs is admin-only"""
    # delete device -> audit
    r = client.post("/api/v1/devices", json=make_push())
    device_id = r.json()["device_id"]
    client.delete(f"/api/v1/devices/{device_id}")

    # update tags -> audit
    r = client.post("/api/v1/devices", json=make_push())
    device_id = r.json()["device_id"]
    client.put(f"/api/v1/devices/{device_id}/tags", json={"tags": ["prod"]})

    # user management -> audit
    client.post("/api/v1/users", json={"username": "u1", "password": "p1pass", "role": "viewer"})

    # update settings -> audit
    client.put("/api/v1/settings/system", json={"offline_threshold_hours": 48})

    r = client.get("/api/v1/audit-logs")
    assert r.status_code == 200
    items = r.json()["items"]
    actions = [i["action"] for i in items]
    assert "删除设备" in actions
    assert "更新标签" in actions
    assert "创建用户" in actions
    assert "修改系统设置" in actions
    # newest first
    assert actions[0] == "修改系统设置"
    # operator is always the logged-in admin
    assert all(i["username"] == "admin" for i in items)

    # filter by operator
    r = client.get("/api/v1/audit-logs?username=admin")
    assert r.status_code == 200
    assert all(i["username"] == "admin" for i in r.json()["items"])


def test_audit_logs_viewer_forbidden(client):
    """viewer gets 403 on audit logs, and viewer read operations are not audited"""
    client.post("/api/v1/users", json={"username": "viewer1", "password": "v1pass", "role": "viewer"})
    assert _login_as(client, "viewer1", "v1pass").status_code == 200
    assert client.get("/api/v1/audit-logs").status_code == 403
    assert client.get("/api/v1/devices").status_code == 200


def test_api_key_management(client):
    """API key CRUD: admin creates / lists (full key) / revokes; viewer gets 403"""
    # create
    r = client.post("/api/v1/api-keys", json={"name": "iagent-prod"})
    assert r.status_code == 200
    key = r.json()["key"]
    assert key.startswith("cmdb_") and len(key) == 5 + 32
    assert r.json()["prefix"] == key[:12]
    assert r.json()["last_used_at"] is None

    # empty name -> 422
    assert client.post("/api/v1/api-keys", json={"name": "  "}).status_code == 422

    # list shows the full key
    r = client.get("/api/v1/api-keys")
    assert r.status_code == 200
    assert any(k["key"] == key for k in r.json()["items"])

    # viewer is forbidden on key management
    client.post("/api/v1/users", json={"username": "viewer1", "password": "v1pass", "role": "viewer"})
    assert _login_as(client, "viewer1", "v1pass").status_code == 200
    assert client.get("/api/v1/api-keys").status_code == 403
    assert client.post("/api/v1/api-keys", json={"name": "x"}).status_code == 403

    # back to admin, revoke
    assert _login_as(client, "admin", "admin").status_code == 200
    key_id = client.get("/api/v1/api-keys").json()["items"][0]["id"]
    assert client.delete(f"/api/v1/api-keys/{key_id}").status_code == 200
    assert client.get("/api/v1/api-keys").json()["items"] == []

    # nonexistent key -> 404
    assert client.delete("/api/v1/api-keys/99999").status_code == 404

    # key management is audited
    actions = [i["action"] for i in client.get("/api/v1/audit-logs").json()["items"]]
    assert "创建 API 密钥" in actions
    assert "吊销 API 密钥" in actions


def test_api_key_auth_flow(client):
    """X-API-Key: when enabled, push requires a key, GET is allowed, writes get 403; off restores"""
    key = client.post("/api/v1/api-keys", json={"name": "k1"}).json()["key"]
    headers = {"X-API-Key": key}

    # feature off (default): push is open, the key header is ignored
    assert client.post("/api/v1/devices", json=make_push()).status_code == 200

    # enable the feature
    client.put(
        "/api/v1/settings/system",
        json={"offline_threshold_hours": 24, "api_key_enabled": True},
    )

    # push without a key -> 401
    assert client.post("/api/v1/devices", json=make_push()).status_code == 401

    # invalid key -> 401
    assert client.post("/api/v1/devices", json=make_push(), headers={"X-API-Key": "cmdb_bad"}).status_code == 401

    # valid key push -> 200
    assert client.post("/api/v1/devices", json=make_push(), headers=headers).status_code == 200

    # last_used_at is updated
    used = client.get("/api/v1/api-keys").json()["items"][0]["last_used_at"]
    assert used is not None

    # GET with the key -> 200
    assert client.get("/api/v1/devices", headers=headers).status_code == 200
    assert client.get("/api/v1/dashboard", headers=headers).status_code == 200

    # key management via key -> 403 (cookie-admin only)
    assert client.get("/api/v1/api-keys", headers=headers).status_code == 403

    # writes with the key -> 403
    device_id = client.get("/api/v1/devices").json()["items"][0]["id"]
    assert client.put(f"/api/v1/devices/{device_id}/tags", json={"tags": ["x"]}, headers=headers).status_code == 403
    assert client.delete(f"/api/v1/devices/{device_id}", headers=headers).status_code == 403

    # session cookie still works (admin), writes included
    assert client.get("/api/v1/devices").status_code == 200
    assert client.put(f"/api/v1/devices/{device_id}/tags", json={"tags": ["prod"]}).status_code == 200

    # disable -> push is open again
    client.put(
        "/api/v1/settings/system",
        json={"offline_threshold_hours": 24, "api_key_enabled": False},
    )
    assert client.post("/api/v1/devices", json=make_push()).status_code == 200

    # revoked key -> 401 after re-enabling
    client.delete(f"/api/v1/api-keys/{client.get('/api/v1/api-keys').json()['items'][0]['id']}")
    client.put(
        "/api/v1/settings/system",
        json={"offline_threshold_hours": 24, "api_key_enabled": True},
    )
    assert client.post("/api/v1/devices", json=make_push(), headers=headers).status_code == 401
