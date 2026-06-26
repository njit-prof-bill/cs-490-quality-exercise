from __future__ import annotations

from .models import GradeRecord, GradeStatus, ValidationIssue
from .students import normalize_email


PASS_TOKENS = {"pass", "passed", "p"}
FAIL_TOKENS = {"fail", "failed", "f"}


def parse_grade_status(value: str) -> GradeStatus:
    normalized = value.strip().lower() or GradeStatus.RECORDED.value
    if normalized == GradeStatus.MISSING.value:
        return GradeStatus.MISSING
    if normalized == GradeStatus.EXCUSED.value:
        return GradeStatus.EXCUSED
    return GradeStatus.RECORDED


def parse_grade_value(raw_value: str, grading_mode: str) -> float | None:
    if raw_value.strip() == "":
        return None
    if grading_mode == "passfail":
        # POLICY-04: case-insensitive matching
        token = raw_value.strip().lower()
        if token in PASS_TOKENS:
            return 1.0
        if token in FAIL_TOKENS:
            return 0.0
        raise ValueError(f"Invalid pass/fail token: {raw_value}")
    return float(raw_value)


def build_grade_record(
    row: dict[str, str],
    row_number: int,
    grading_mode_lookup: dict[str, str],
) -> tuple[GradeRecord | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    student_email = normalize_email(row.get("student_email", ""))
    assignment_id = row.get("assignment_id", "").strip()
    if not student_email or not assignment_id:
        issues.append(
            ValidationIssue(
                requirement_id="CSV-07",
                message="Grade row missing student_email or assignment_id.",
                row_number=row_number,
                source="grades",
            )
        )
        return None, issues
    grading_mode = grading_mode_lookup.get(assignment_id, "points")
    grade_status = parse_grade_status(row.get("status", ""))
    raw_value = row.get("score", "")
    score: float | None = None
    if grade_status != GradeStatus.EXCUSED:
        try:
            score = parse_grade_value(raw_value, grading_mode)
        except ValueError:
            issues.append(
                ValidationIssue(
                    requirement_id="CSV-07",
                    message=f"Grade row has invalid score value: {raw_value}",
                    row_number=row_number,
                    source="grades",
                )
            )
            return None, issues
    try:
        days_late = int(row.get("days_late", "0") or "0")
    except ValueError:
        issues.append(
            ValidationIssue(
                requirement_id="CSV-07",
                message="days_late must be an integer.",
                row_number=row_number,
                source="grades",
            )
        )
        return None, issues
    record = GradeRecord(
        student_email=student_email,
        assignment_id=assignment_id,
        score=score,
        grade_status=grade_status,
        days_late=days_late,
        raw_value=raw_value,
        notes=row.get("notes", "").strip(),
        source_row=row_number,
    )
    return record, issues
