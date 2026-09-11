"""API 端到端测试:推送、列表、详情、裁决、删除、疑似下线。"""

from datetime import timedelta
from sqlmodel import Session, select

from cmdb.models import Device, utcnow


def make_push(**overrides) -> dict:
    """构造基础推送体,可按字段覆盖。"""
    base = {
        "hostname": "S1A01DC-VL101",
        "serial_number": "PF4ABC123456",
        "mgmt": {
            "mac": "AA:BB:CC:DD:EE:01",
            "ip": "192.168.10.101",
            "prefix_length": 24,
        },
        "nics": [
            {"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
             "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]},
            {"name": "eth1", "mac": "AA:BB:CC:DD:EE:03",
             "ips": [{"ip": "10.10.2.101", "prefix_length": 24}]},
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
    push = make_push(mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
                           "prefix_length": 24})
    r = client.post("/api/v1/devices", json=push)
    body = r.json()
    assert body["result"] == "diff_created"
    assert body["pending_change_id"] is not None


def test_push_invalid_payload_422(client):
    r = client.post("/api/v1/devices", json={"nics": []})
    assert r.status_code == 422


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
    assert detail["hostname"] == "S1A01DC-VL101"
    assert detail["nics"][0]["ips"][0]["ip"] == "10.10.1.101"


def test_list_search_and_status_filter(client, engine):
    client.post("/api/v1/devices", json=make_push())

    r = client.get("/api/v1/devices", params={"search": "nomatch"})
    assert r.json()["total"] == 0
    r = client.get("/api/v1/devices", params={"search": "S1A01DC"})
    assert r.json()["total"] == 1

    # 手动把 last_pushed_at 推到 4 天前 -> suspected_offline
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
    push = make_push(mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
                           "prefix_length": 24},
                     nics=[{"name": "eth0", "mac": "AA:BB:CC:DD:EE:02",
                            "ips": [{"ip": "10.10.1.101", "prefix_length": 24}]}])
    pending_id = client.post("/api/v1/devices", json=push).json()["pending_change_id"]

    # 待裁决列表
    items = client.get("/api/v1/pending-changes").json()["items"]
    assert len(items) == 1 and items[0]["id"] == pending_id

    # diff 详情
    detail = client.get(f"/api/v1/pending-changes/{pending_id}").json()
    assert detail["payload"]["mgmt"]["ip"] == "192.168.10.200"
    fields = {f["field"] for f in detail["diff"]["fields"]}
    assert fields == {"mgmt.ip"}

    # 裁决:mgmt.ip 用新值,eth1 删除
    r = client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {"mgmt.ip": "new"}, "nic_choices": {"eth1": "new"}},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "applied"

    # 设备数据已按裁决更新
    device = client.get("/api/v1/devices/1").json()
    assert device["mgmt_ip"] == "192.168.10.200"
    assert [n["name"] for n in device["nics"]] == ["eth0"]

    # 重复裁决 -> 409
    r = client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {}, "nic_choices": {}},
    )
    assert r.status_code == 409


def test_resolve_discard(client):
    client.post("/api/v1/devices", json=make_push())
    push = make_push(mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
                           "prefix_length": 24})
    pending_id = client.post("/api/v1/devices", json=push).json()["pending_change_id"]

    r = client.post(
        f"/api/v1/pending-changes/{pending_id}/resolve",
        json={"field_choices": {"mgmt.ip": "old"}, "nic_choices": {}},
    )
    assert r.status_code == 200

    device = client.get("/api/v1/devices/1").json()
    assert device["mgmt_ip"] == "192.168.10.101"  # 保留原值


def test_change_history(client):
    client.post("/api/v1/devices", json=make_push())
    push = make_push(mgmt={"mac": "AA:BB:CC:DD:EE:01", "ip": "192.168.10.200",
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


def test_spa_fallback(client):
    """前端路由刷新回退 index.html;未知 API 路径保持 404。"""
    r = client.get("/devices")
    assert r.status_code == 200
    assert '<div id="app">' in r.text

    r = client.get("/conflicts")
    assert r.status_code == 200

    r = client.get("/api/v1/nonexistent")
    assert r.status_code == 404
