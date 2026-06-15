from pydantic import BaseModel


class WSMessage(BaseModel):
    type: str
    from_device: str | None = None
    to_device: str | None = None
    payload: dict | list | str | None = None
    timestamp: float | None = None
    nonce: str | None = None


class DeviceInfo(BaseModel):
    device_id: str
    device_name: str
    connected_at: float
    is_online: bool = True
