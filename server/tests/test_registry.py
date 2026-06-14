import time
from app.registry import DeviceRegistry


def test_create_and_redeem_pairing_code():
    reg = DeviceRegistry()
    code = reg.create_pairing_code("device-a")
    assert len(code) == 6
    assert code.isdigit()

    result = reg.redeem_pairing_code(code, "device-b")
    assert result == "device-a"
    assert reg.is_paired("device-a", "device-b")
    assert reg.is_paired("device-b", "device-a")


def test_cannot_pair_with_self():
    reg = DeviceRegistry()
    code = reg.create_pairing_code("device-a")
    result = reg.redeem_pairing_code(code, "device-a")
    assert result is None


def test_expired_code_rejected():
    reg = DeviceRegistry()
    code = reg.create_pairing_code("device-a", expiry=0)
    time.sleep(0.01)
    result = reg.redeem_pairing_code(code, "device-b")
    assert result is None


def test_invalid_code_rejected():
    reg = DeviceRegistry()
    result = reg.redeem_pairing_code("000000", "device-b")
    assert result is None


def test_unpair():
    reg = DeviceRegistry()
    code = reg.create_pairing_code("device-a")
    reg.redeem_pairing_code(code, "device-b")
    assert reg.is_paired("device-a", "device-b")

    reg.unpair("device-a", "device-b")
    assert not reg.is_paired("device-a", "device-b")
    assert not reg.is_paired("device-b", "device-a")


def test_get_paired_devices():
    reg = DeviceRegistry()
    code = reg.create_pairing_code("device-a")
    reg.redeem_pairing_code(code, "device-b")
    code2 = reg.create_pairing_code("device-a")
    reg.redeem_pairing_code(code2, "device-c")

    paired = reg.get_paired_devices("device-a")
    assert "device-b" in paired
    assert "device-c" in paired
    assert len(paired) == 2
