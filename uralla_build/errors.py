"""Domain errors returned by validators and the future build runner."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One deterministic validation failure."""

    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}"


class ManifestError(RuntimeError):
    """The manifest cannot be loaded as a mapping."""

