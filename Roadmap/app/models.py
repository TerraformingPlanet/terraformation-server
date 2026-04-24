"""
Roadmap Service — Pydantic models
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PhaseStatus = Literal["not-started", "pending", "done"]


class PhaseRecord(BaseModel):
    id: str
    name: str
    status: PhaseStatus = "not-started"
    completed_date: str | None = None
    tests: list[str] = Field(default_factory=list)
    validation_filter: str | None = None
    exit_criteria: str | None = None
    design_ref: str | None = None
    roadmap_anchor: str | None = None
    notes: str | None = None
    assertion_script: str | None = None
    sort_order: int = 0


class PhaseCreate(BaseModel):
    id: str
    name: str
    status: PhaseStatus = "not-started"
    tests: list[str] = Field(default_factory=list)
    validation_filter: str | None = None
    exit_criteria: str | None = None
    design_ref: str | None = None
    roadmap_anchor: str | None = None
    notes: str | None = None
    assertion_script: str | None = None


class CompletionResult(BaseModel):
    phase: PhaseRecord
    pytest_output: str | None = None
    test_files: list[str] = Field(default_factory=list)
    status: Literal["ok", "blocked", "needs_confirmation", "needs_validation"]
    message: str = ""


class SeedPhaseInput(BaseModel):
    """A single phase as it appears in roadmap.json (camelCase keys accepted)."""

    id: str
    name: str
    status: PhaseStatus = "not-started"
    completedDate: str | None = None
    tests: list[str] = Field(default_factory=list)
    validationFilter: str | None = None
    exitCriteria: str | None = None
    designRef: str | None = None
    roadmapAnchor: str | None = None
    notes: str | None = None
    assertionScript: str | None = None
    sortOrder: int = 0

    def to_record(self) -> PhaseRecord:
        return PhaseRecord(
            id=self.id,
            name=self.name,
            status=self.status,
            completed_date=self.completedDate,
            tests=self.tests,
            validation_filter=self.validationFilter,
            exit_criteria=self.exitCriteria,
            design_ref=self.designRef,
            roadmap_anchor=self.roadmapAnchor,
            notes=self.notes,
            assertion_script=self.assertionScript,
            sort_order=self.sortOrder,
        )


class SeedPayload(BaseModel):
    """Accepts the full roadmap.json shape. Unknown top-level keys are ignored."""

    phases: list[SeedPhaseInput]


class ValidationResult(BaseModel):
    """Result of running a phase assertion script."""

    phase_id: str
    status: Literal["pass", "fail", "no_script", "error"]
    exit_code: int | None = None
    output: str = ""
    assertion_script: str | None = None


class AuditEntry(BaseModel):
    """One pending/not-started phase with what needs to be validated."""

    id: str
    name: str
    status: PhaseStatus
    exit_criteria: str | None = None
    tests_to_run: list[str] = Field(default_factory=list)
    validation_filter: str | None = None
    assertion_script: str | None = None
    notes: str | None = None


class AuditResult(BaseModel):
    """Summary of all phases that still need validation."""

    total: int
    with_tests: int       # phases that have explicit test files
    visual_only: int      # phases with no tests (require Unity Play Mode or manual check)
    phases: list[AuditEntry]


class TestAllResult(BaseModel):
    """Result of running all assertion scripts across all phases."""

    total: int          # phases with an assertion_script
    passed: int
    failed: int
    no_script: int      # phases without an assertion_script (skipped)
    errors: int         # scripts that couldn't be run (file not found etc.)
    results: list[ValidationResult]


class MoveResult(BaseModel):
    """Result of a queue reorder operation."""

    moved_id: str
    queue: list[PhaseRecord]  # full ordered list after move


class SeedResult(BaseModel):
    inserted: int
    skipped: int
    total: int
