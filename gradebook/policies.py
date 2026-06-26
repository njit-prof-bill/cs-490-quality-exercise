from __future__ import annotations

from collections import defaultdict

from .models import Assignment, GradeRecord, GradeStatus, ValidationIssue


def validate_category_weights(assignments: dict[str, Assignment]) -> list[ValidationIssue]:
    # POLICY-01: sum unique per-category weights (all assignments in same category share one weight)
    category_weights: dict[str, float] = {}
    for assignment in assignments.values():
        if assignment.category == "EXTRA_CREDIT":
            continue
        category_weights[assignment.category] = assignment.weight
    total_weight = sum(category_weights.values())
    issues: list[ValidationIssue] = []
    if round(total_weight, 2) != 1.0:
        issues.append(
            ValidationIssue(
                requirement_id="POLICY-01",
                message=f"Category weights must total 100. Found {total_weight:.2f}.",
                source="assignments",
            )
        )
    return issues


def validate_assignment_policy(assignment: Assignment) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if assignment.is_extra_credit and assignment.category != "EXTRA_CREDIT":
        issues.append(
            ValidationIssue(
                requirement_id="POLICY-05",
                message=f"Extra credit assignment {assignment.assignment_id} must use category EXTRA_CREDIT.",
                source="assignments",
            )
        )
    if assignment.is_extra_credit and assignment.weight != 0:
        issues.append(
            ValidationIssue(
                requirement_id="POLICY-05",
                message=f"Extra credit assignment {assignment.assignment_id} must have weight 0.",
                source="assignments",
            )
        )
    return issues


def apply_late_policy(record: GradeRecord, assignment: Assignment) -> float | None:
    if record.grade_status == GradeStatus.EXCUSED:
        return None
    if record.score is None:
        return None
    if assignment.grading_mode == "passfail":
        return assignment.max_points if record.score >= 1 else 0.0
    score = record.score
    if record.days_late > 0 and assignment.due_date is not None:
        # POLICY-02: penalty is % of earned score, capped at 3 days
        capped_days = min(record.days_late, 3)
        score -= score * assignment.late_penalty_per_day * capped_days
    if assignment.min_score_floor is not None:
        # POLICY-03: floor applied after late penalty
        score = max(score, assignment.min_score_floor)
    return score


def validate_grade_value(record: GradeRecord, assignment: Assignment) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if record.score is None or record.grade_status == GradeStatus.EXCUSED:
        return issues
    if record.score < 0:
        issues.append(
            ValidationIssue(
                requirement_id="CSV-05",
                message=f"Negative score for {record.student_email} on {record.assignment_id}.",
                row_number=record.source_row,
                source="grades",
            )
        )
    # CSV-04: score > max_points is invalid unless extra credit
    if (
        assignment.grading_mode == "points"
        and not assignment.is_extra_credit
        and record.score > assignment.max_points
    ):
        issues.append(
            ValidationIssue(
                requirement_id="CSV-04",
                message=f"Score exceeds max points for {record.assignment_id}.",
                row_number=record.source_row,
                source="grades",
            )
        )
    return issues
