from dataclasses import dataclass


@dataclass(frozen=True)
class Organization:
    organization_id: str
    name: str
