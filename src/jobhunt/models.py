from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Job:
    """A job posting normalised across all sources."""

    company: str          # company key from companies.yaml, e.g. "anthropic"
    source: str           # adapter name, e.g. "greenhouse"
    external_id: str      # id within the source
    title: str
    url: str
    locations: list[str] = field(default_factory=list)
    team: str | None = None
    remote: bool | None = None
    posted_at: str | None = None   # ISO 8601 when known
    apply_url: str | None = None
    description: str | None = None  # plain text when the listing provides it

    @property
    def uid(self) -> str:
        return f"{self.company}:{self.external_id}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["uid"] = self.uid
        return d
