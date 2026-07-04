from dataclasses import dataclass, field
from datetime import datetime, timedelta


class AutomaticRetryBlocked(RuntimeError):
    """目标群已发送或发送结果不确定，禁止自动重试。"""


@dataclass
class ReportState:
    business_date: str
    groups: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def empty(cls, business_date: str) -> "ReportState":
        return cls(business_date)

    def reserve(
        self,
        group: str,
        content_hash: str,
        now: datetime,
        lease_minutes: int = 15,
    ) -> None:
        current = self.groups.get(group, {})
        if current.get("status") in {"sent", "uncertain", "sending"}:
            raise AutomaticRetryBlocked(group)
        self.groups[group] = {
            "status": "sending",
            "content_hash": content_hash,
            "lease_expires_at": (
                now + timedelta(minutes=lease_minutes)
            ).isoformat(),
        }

    def mark_sent(self, group: str, now: datetime) -> None:
        self.groups[group].update(status="sent", sent_at=now.isoformat())

    def mark_failed(self, group: str, error: Exception | str) -> None:
        self.groups[group].update(status="failed", error=str(error))

    def mark_uncertain(self, group: str, error: Exception | str) -> None:
        self.groups[group].update(status="uncertain", error=str(error))

    def expire_leases(self, now: datetime) -> None:
        for value in self.groups.values():
            if (
                value.get("status") == "sending"
                and datetime.fromisoformat(value["lease_expires_at"]) < now
            ):
                value["status"] = "uncertain"
