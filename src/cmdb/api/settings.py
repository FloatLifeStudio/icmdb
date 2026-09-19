"""系统设置:DB 键值存储,环境变量作默认值。"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from cmdb.api.auth import current_username
from cmdb.config import settings as app_settings
from cmdb.database import get_session
from cmdb.models import SystemSetting
from cmdb.services.audit import record_audit

router = APIRouter(tags=["settings"])

OFFLINE_THRESHOLD_KEY = "offline_threshold_hours"


def get_offline_threshold_hours(session: Session) -> int:
    """疑似下线阈值(小时):DB 设置优先,回退环境变量(天 × 24)。"""
    row = session.exec(
        select(SystemSetting).where(SystemSetting.key == OFFLINE_THRESHOLD_KEY)
    ).first()
    if row and row.value and row.value.strip().isdigit():
        return int(row.value)
    return app_settings.offline_threshold_days * 24


class SystemSettingsOut(BaseModel):
    offline_threshold_hours: int


class SystemSettingsIn(BaseModel):
    offline_threshold_hours: int = Field(ge=1, le=24 * 365)


@router.get("/settings/system")
def read_system_settings(
    session: Session = Depends(get_session),
) -> SystemSettingsOut:
    return SystemSettingsOut(offline_threshold_hours=get_offline_threshold_hours(session))


@router.put("/settings/system")
def update_system_settings(
    body: SystemSettingsIn,
    request: Request,
    session: Session = Depends(get_session),
) -> SystemSettingsOut:
    old_value = get_offline_threshold_hours(session)
    row = session.exec(
        select(SystemSetting).where(SystemSetting.key == OFFLINE_THRESHOLD_KEY)
    ).first()
    if row:
        row.value = str(body.offline_threshold_hours)
    else:
        row = SystemSetting(key=OFFLINE_THRESHOLD_KEY, value=str(body.offline_threshold_hours))
    session.add(row)
    record_audit(
        session, current_username(request), "修改系统设置",
        f"疑似下线阈值 {old_value} -> {body.offline_threshold_hours} 小时",
    )
    session.commit()
    return SystemSettingsOut(offline_threshold_hours=body.offline_threshold_hours)
