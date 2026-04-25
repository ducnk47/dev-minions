from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ExecResult:
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Devbox(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def wait_until_ready(self) -> None: ...

    @abstractmethod
    def exec(self, command: str, timeout: int = 60) -> ExecResult: ...

    @abstractmethod
    def stop(self) -> None: ...
