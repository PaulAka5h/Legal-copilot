from typing import Protocol


class PasswordResetSender(Protocol):
    def send_reset(self, email: str, token: str) -> None: ...


class NotConfiguredResetSender:
    def send_reset(self, email: str, token: str) -> None:
        return None
