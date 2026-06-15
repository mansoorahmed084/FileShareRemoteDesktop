import logging
import random
import string
import time

logger = logging.getLogger(__name__)


class PairingCode:
    def __init__(self, code: str, device_id: str, expires_at: float) -> None:
        self.code = code
        self.device_id = device_id
        self.expires_at = expires_at


class DeviceRegistry:
    def __init__(self) -> None:
        self._paired: dict[str, set[str]] = {}
        self._pending_codes: dict[str, PairingCode] = {}

    def create_pairing_code(self, device_id: str, expiry: int = 60) -> str:
        self._cleanup_expired()
        code = "".join(random.choices(string.digits, k=6))
        self._pending_codes[code] = PairingCode(
            code=code, device_id=device_id, expires_at=time.time() + expiry
        )
        logger.info("Pairing code created for device %s", device_id)
        return code

    def redeem_pairing_code(self, code: str, device_id: str) -> str | None:
        self._cleanup_expired()
        entry = self._pending_codes.pop(code, None)
        if not entry:
            return None
        if entry.device_id == device_id:
            return None

        self._add_pair(entry.device_id, device_id)
        logger.info("Devices paired: %s <-> %s", entry.device_id, device_id)
        return entry.device_id

    def is_paired(self, device_a: str, device_b: str) -> bool:
        return device_b in self._paired.get(device_a, set())

    def get_paired_devices(self, device_id: str) -> set[str]:
        return self._paired.get(device_id, set()).copy()

    def unpair(self, device_a: str, device_b: str) -> bool:
        removed = False
        if device_a in self._paired and device_b in self._paired[device_a]:
            self._paired[device_a].discard(device_b)
            removed = True
        if device_b in self._paired and device_a in self._paired[device_b]:
            self._paired[device_b].discard(device_a)
            removed = True
        return removed

    def restore_pair(self, device_a: str, device_b: str) -> None:
        self._add_pair(device_a, device_b)

    def _add_pair(self, device_a: str, device_b: str) -> None:
        self._paired.setdefault(device_a, set()).add(device_b)
        self._paired.setdefault(device_b, set()).add(device_a)

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired = [c for c, p in self._pending_codes.items() if p.expires_at < now]
        for code in expired:
            del self._pending_codes[code]


registry = DeviceRegistry()
