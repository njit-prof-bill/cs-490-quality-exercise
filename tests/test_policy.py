"""
Level 4 Policy and Rule Behavior Tests
Tests named after requirement IDs from grading-policy.md
"""
from __future__ import annotations

from datetime import date

import pytest

from gradebook.calculator import compute_student_grade
from gradebook.grades import parse_grade_value
from gradebook.importer import import_assignments
from gradebook.models import (
    Assignment,
    GradebookData,
    GradeRecord,
    GradeStatus,
    Student,
    StudentStatus,
    ValidationIssue,
)
from gradebook.policies import apply_late_policy, validate_category_weights


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_student(email: str = "test@njit.edu") -> Student:
    return Student(student_id=email, first_name="Test", last_name="Student", email=email)


def make_assignment(
    assignment_id: str = "HW1",
    category: str = "HOMEWORK",
    max_points: float = 100.0,
    weight: float = 1.0,
    due_date: date | None = date(2026, 9, 10),
    late_penalty_per_day: float = 0.10,
    min_score_floor: float | None = None,
    grading_mode: str = "points",
    is_extra_credit: bool = False,
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        name=assignment_id,
        category=category,
        max_points=max_points,
        weight=weight,
        due_date=due_date,
        late_penalty_per_day=late_penalty_per_day,
        min_score_floor=min_score_floor,
        grading_mode=grading_mode,
        is_extra_credit=is_extra_credit,
    )


def make_grade(
    email: str = "test@njit.edu",
    assignment_id: str = "HW1",
    score: float = 80.0,
    days_late: int = 0,
    status: GradeStatus = GradeStatus.RECORDED,
) -> GradeRecord:
    return GradeRecord(
        student_email=email,
        assignment_id=assignment_id,
        score=score,
        grade_status=status,
        days_late=days_late,
        source_row=2,
    )


def simple_data(
    students: list[Student],
    assignments: list[Assignment],
    grades: list[GradeRecord],
) -> GradebookData:
    return GradebookData(
        students={s.email: s for s in students},
        assignments={a.assignment_id: a for a in assignments},
        grades=grades,
    )


# ---------------------------------------------------------------------------
# POLICY-01: Non-extra-credit category weights must total exactly 100
# ---------------------------------------------------------------------------

def test_policy_01_weights_total_100_valid():
    assignments = {
        "HW1": make_assignment("HW1", weight=0.60),
        "E1":  make_assignment("E1",  category="EXAM", weight=0.40),
    }
    issues = validate_category_weights(assignments)
    assert not any(i.requirement_id == "POLICY-01" for i in issues)


def test_policy_01_weights_not_totaling_100_invalid():
    assignments = {
        "HW1": make_assignment("HW1", weight=0.50),
        "E1":  make_assignment("E1",  category="EXAM", weight=0.40),
    }
    issues = validate_category_weights(assignments)
    assert any(i.requirement_id == "POLICY-01" for i in issues)


def test_policy_01_extra_credit_excluded_from_weight_check():
    """Extra credit weight=0 should not count toward the 100% total."""
    assignments = {
        "HW1": make_assignment("HW1", weight=1.0),
        "EC1": make_assignment("EC1", category="EXTRA_CREDIT", weight=0.0, is_extra_credit=True),
    }
    issues = validate_category_weights(assignments)
    assert not any(i.requirement_id == "POLICY-01" for i in issues)


# ---------------------------------------------------------------------------
# POLICY-02: Late penalty is 10% per day, capped at 3 days
# ---------------------------------------------------------------------------

def test_policy_02_late_penalty_applied():
    """1 day late on 100-point assignment at 10%/day -> score reduced by 10."""
    assignment = make_assignment(max_points=100.0, late_penalty_per_day=0.10)
    record = make_grade(score=80.0, days_late=1)
    result = apply_late_policy(record, assignment)
    assert result == pytest.approx(70.0)


def test_policy_02_late_penalty_three_days():
    """3 days late -> penalty capped at 3 days: 100 * 0.10 * 3 = 30 points off."""
    assignment = make_assignment(max_points=100.0, late_penalty_per_day=0.10)
    record = make_grade(score=80.0, days_late=3)
    result = apply_late_policy(record, assignment)
    assert result == pytest.approx(50.0)


def test_policy_02_late_penalty_capped_at_three_days():
    """4 days late -> penalty capped at 3 days, not 4."""
    assignment = make_assignment(max_points=100.0, late_penalty_per_day=0.10)
    record_3 = make_grade(score=80.0, days_late=3)
    record_4 = make_grade(score=80.0, days_late=4)
    result_3 = apply_late_policy(record_3, assignment)
    result_4 = apply_late_policy(record_4, assignment)
    assert result_3 == pytest.approx(result_4)


def test_policy_02_no_penalty_without_due_date():
    """No due date -> no late penalty regardless of days_late."""
    assignment = make_assignment(due_date=None)
    record = make_grade(score=80.0, days_late=5)
    result = apply_late_policy(record, assignment)
    assert result == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# POLICY-03: Min score floor applied after late penalties
# ---------------------------------------------------------------------------

def test_policy_03_floor_applied_after_late_penalty():
    """Score after late penalty is 20, floor is 50 -> final score is 50."""
    assignment = make_assignment(max_points=100.0, late_penalty_per_day=0.10, min_score_floor=50.0)
    record = make_grade(score=50.0, days_late=3)  # 50 - 30 = 20, floor brings to 50
    result = apply_late_policy(record, assignment)
    assert result == pytest.approx(50.0)


def test_policy_03_floor_not_applied_when_score_above_floor():
    """Score after late penalty is 70, floor is 50 -> floor has no effect."""
    assignment = make_assignment(max_points=100.0, late_penalty_per_day=0.10, min_score_floor=50.0)
    record = make_grade(score=80.0, days_late=1)  # 80 - 10 = 70, above floor
    result = apply_late_policy(record, assignment)
    assert result == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# POLICY-04: Pass/fail is case-insensitive
# ---------------------------------------------------------------------------

def test_policy_04_pass_uppercase():
    assert parse_grade_value("PASS", "passfail") == 1.0


def test_policy_04_pass_lowercase():
    assert parse_grade_value("pass", "passfail") == 1.0


def test_policy_04_pass_mixed_case():
    assert parse_grade_value("Pass", "passfail") == 1.0


def test_policy_04_fail_uppercase():
    assert parse_grade_value("FAIL", "passfail") == 0.0


def test_policy_04_fail_lowercase():
    assert parse_grade_value("fail", "passfail") == 0.0


def test_policy_04_fail_mixed_case():
    assert parse_grade_value("Fail", "passfail") == 0.0


# ---------------------------------------------------------------------------
# POLICY-06: Excused assignments exempt from late penalties
# ---------------------------------------------------------------------------

def test_policy_06_excused_exempt_from_late_penalty():
    assignment = make_assignment(max_points=100.0, late_penalty_per_day=0.10)
    record = make_grade(score=80.0, days_late=3, status=GradeStatus.EXCUSED)
    result = apply_late_policy(record, assignment)
    assert result is None  # excused returns None, not penalized score


def test_policy_06_excused_not_counted_as_missing():
    student = make_student()
    assignment = make_assignment()
    grade = make_grade(score=None, days_late=0, status=GradeStatus.EXCUSED)
    grade = GradeRecord(
        student_email=student.email,
        assignment_id="HW1",
        score=None,
        grade_status=GradeStatus.EXCUSED,
        days_late=0,
        source_row=2,
    )
    data = simple_data([student], [assignment], [grade])
    result = compute_student_grade(data, student)
    assert "HW1" not in result.missing_assignments


# ---------------------------------------------------------------------------
# POLICY-08: No due date means no late penalty
# ---------------------------------------------------------------------------

def test_policy_08_no_due_date_no_penalty():
    assignment = make_assignment(due_date=None, late_penalty_per_day=0.10)
    record = make_grade(score=70.0, days_late=10)
    result = apply_late_policy(record, assignment)
    assert result == pytest.approx(70.0)


def test_policy_08_with_due_date_penalty_applied():
    assignment = make_assignment(due_date=date(2026, 9, 10), late_penalty_per_day=0.10)
    record = make_grade(score=70.0, days_late=1)
    result = apply_late_policy(record, assignment)
    assert result == pytest.approx(60.0)
