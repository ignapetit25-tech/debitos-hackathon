"""Integration contracts (ABCs + schemas). All money in int cents.

The AI layer talks to the world only through these contracts. Two
implementations: `synthetic` (demo, in this repo) and the real adapter
(explicit JSON, off by default, unverified).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineItem:
    line_no: int
    procedure: str
    reason: str
    billed_cents: int
    settled_cents: int

    @property
    def debit_cents(self) -> int:
        return self.billed_cents - self.settled_cents


@dataclass(frozen=True)
class Case:
    id: str
    payer: str
    invoice: str
    lines: tuple[LineItem, ...]
    total_debit_cents: int
    status: str = "new"
    service_date: str = ""

    def validate(self) -> tuple[bool, int]:
        total = sum(r.debit_cents for r in self.lines)
        return total == self.total_debit_cents, total - self.total_debit_cents


@dataclass(frozen=True)
class Finding:
    id: str
    case_id: str
    line_no: int
    kind: str
    document: str
    page: int
    excerpt: str
    interpretation: str
    limitations: str = ""
    verified: bool = False


@dataclass(frozen=True)
class RuleRef:
    team: str
    points: int  # rule score: NOT a probability nor confidence
    phrases: tuple[str, ...]


@dataclass(frozen=True)
class Proposal:
    id: str
    case_id: str
    team: str
    rule: RuleRef
    action: str  # claim | route_human | request_extension
    explanation: str
    references: tuple[str, ...]  # which data was used
    needs_human: bool = False
    extraction_confidence: float = 1.0  # 0-1, distinct from points


@dataclass(frozen=True)
class Decision:
    proposal_id: str
    reviewer: str
    verdict: str  # approved | rejected
    note: str = ""


@dataclass
class HistoryEvent:
    seq: int
    kind: str  # extraction | validation | tool | model_call | proposal | review
    detail: str
    before: str = ""
    after: str = ""
    created_at: str = ""  # local ISO date-time of the event


class CaseStore(abc.ABC):
    @abc.abstractmethod
    def get_case(self, id: str) -> Case: ...

    @abc.abstractmethod
    def list_cases(self, filters: dict | None = None) -> list[Case]: ...

    @abc.abstractmethod
    def save_proposal(self, case_id: str, proposal: Proposal) -> None: ...


class RateService(abc.ABC):
    @abc.abstractmethod
    def get_rate(
        self, procedure: str, payer: str, date: str
    ) -> dict | None: ...


class RulesService(abc.ABC):
    @abc.abstractmethod
    def evaluate_rules(self, reason: str) -> RuleRef: ...
