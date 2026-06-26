"""Level 4 – Policy and rule behavior tests (POLICY-01 through POLICY-08)."""
from __future__ import annotations

from datetime import date

import pytest

from gradebook.calculator import compute_student_grade
from gradebook.grades import parse_grade_value
from gradebook.models import (
    Assignment,
    GradeRecord,
    GradeStatus,
    GradebookData,
    Student,
    StudentStatus,
)
from gradebook.policies import apply_late_policy, validate_assignment_policy, validate_category_weights
from gradebook.reports import build_final_grades_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _student() -> Student:
    return Student(student_id="s1", first_name="Ada", last_name="L", email="ada@x.com")


def _assignment(
    assignment_id: str = "HW1",
    category: str = "HOMEWORK",
    max_points: float = 100,
    weight: float = 1.0,
    *,
    due_date: date | None = date(2025, 1, 10),
    late_penalty_per_day: float = 0.10,
    min_score_floor: float | None = None,
    grading_mode: str = "points",
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
    )


def _record(score: float, days_late: int = 0) -> GradeRecord:
    return GradeRecord(
        student_email="ada@x.com",
        assignment_id="HW1",
        score=score,
        grade_status=GradeStatus.RECORDED,
        days_late=days_late,
    )


def _data(assignments: list[Assignment], grades: list[GradeRecord]) -> GradebookData:
    s = _student()
    return GradebookData(
        students={s.email: s},
        assignments={a.assignment_id: a for a in assignments},
        grades=grades,
    )


# ---------------------------------------------------------------------------
# POLICY-01: unique category weights must sum to 100 (stored as 1.0)
# ---------------------------------------------------------------------------

def test_policy_01_valid_weights_no_issue() -> None:
    """Unique category weights summing to 1.0 produce no POLICY-01 issue."""
    assignments = {
        "HW1": _assignment("HW1", "HOMEWORK", weight=0.60),
        "HW2": _assignment("HW2", "HOMEWORK", weight=0.60),  # same category, same weight
        "EX1": _assignment("EX1", "EXAM", weight=0.40),
    }
    issues = validate_category_weights(assignments)
    req_ids = [i.requirement_id for i in issues]
    assert "POLICY-01" not in req_ids


def test_policy_01_duplicate_assignment_weights_not_double_counted() -> None:
    """Two assignments in the same category share one weight and must not be double-counted."""
    # If double-counted: 0.60 + 0.60 + 0.40 = 1.60 → triggers false POLICY-01 issue
    assignments = {
        "HW1": _assignment("HW1", "HOMEWORK", weight=0.60),
        "HW2": _assignment("HW2", "HOMEWORK", weight=0.60),
        "EX1": _assignment("EX1", "EXAM", weight=0.40),
    }
    issues = validate_category_weights(assignments)
    # The unique sum is 0.60 + 0.40 = 1.00 → valid, no issue
    assert not issues


# ---------------------------------------------------------------------------
# POLICY-02: late penalty is 10% of earned score per day, capped at 3 days
# ---------------------------------------------------------------------------

def test_policy_02_penalty_based_on_earned_score() -> None:
    """Late penalty must deduct 10% of the student's earned score (not max_points) (POLICY-02)."""
    assignment = _assignment(max_points=100, late_penalty_per_day=0.10)
    record = _record(score=80, days_late=1)
    adjusted = apply_late_policy(record, assignment)
    # 80 - 80 * 0.10 * 1 = 72
    assert adjusted == pytest.approx(72.0)


def test_policy_02_penalty_capped_at_3_days() -> None:
    """Late penalty is capped at 3 days regardless of actual days late (POLICY-02)."""
    assignment = _assignment(max_points=100, late_penalty_per_day=0.10)
    record = _record(score=80, days_late=5)
    adjusted = apply_late_policy(record, assignment)
    # Capped at 3 days: 80 - 80 * 0.10 * 3 = 80 - 24 = 56
    assert adjusted == pytest.approx(56.0)


# ---------------------------------------------------------------------------
# POLICY-03: min_score_floor is applied after late penalties
# ---------------------------------------------------------------------------

def test_policy_03_floor_applied_after_late_penalty() -> None:
    """The score floor is enforced after the late penalty, not before (POLICY-03)."""
    assignment = _assignment(max_points=100, late_penalty_per_day=0.10, min_score_floor=50)
    # Score 55, 3 days late: 55 - 55*0.30 = 38.5 → floor kicks in → 50
    record = _record(score=55, days_late=3)
    adjusted = apply_late_policy(record, assignment)
    assert adjusted == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# POLICY-04: pass/fail tokens are case-insensitive
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("token", ["PASS", "Pass", "pass", "passed", "PASSED"])
def test_policy_04_pass_tokens_case_insensitive(token: str) -> None:
    """Any casing of PASS must be recognised as a passing grade (POLICY-04)."""
    score = parse_grade_value(token, "passfail")
    assert score == pytest.approx(1.0)


@pytest.mark.parametrize("token", ["FAIL", "Fail", "fail", "failed", "FAILED"])
def test_policy_04_fail_tokens_case_insensitive(token: str) -> None:
    """Any casing of FAIL must be recognised as a failing grade (POLICY-04)."""
    score = parse_grade_value(token, "passfail")
    assert score == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# POLICY-08: no due_date → no late penalty
# ---------------------------------------------------------------------------

def test_policy_08_no_due_date_no_penalty() -> None:
    """Assignments with no due date must never incur a late penalty (POLICY-08)."""
    assignment = _assignment(due_date=None, late_penalty_per_day=0.10)
    record = _record(score=80, days_late=3)
    adjusted = apply_late_policy(record, assignment)
    assert adjusted == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# POLICY-05: extra credit must be in EXTRA_CREDIT category with weight 0
# ---------------------------------------------------------------------------

def test_policy_05_ec_wrong_category_produces_issue() -> None:
    """An extra credit assignment not in EXTRA_CREDIT category must produce a POLICY-05 issue."""
    a = Assignment(
        assignment_id="EC1", name="EC1",
        category="HOMEWORK",  # wrong category
        max_points=10, weight=0.0, is_extra_credit=True,
    )
    issues = validate_assignment_policy(a)
    req_ids = [i.requirement_id for i in issues]
    assert "POLICY-05" in req_ids


def test_policy_05_ec_nonzero_weight_produces_issue() -> None:
    """An extra credit assignment with non-zero weight must produce a POLICY-05 issue."""
    a = Assignment(
        assignment_id="EC1", name="EC1",
        category="EXTRA_CREDIT",
        max_points=10, weight=0.05,  # non-zero weight
        is_extra_credit=True,
    )
    issues = validate_assignment_policy(a)
    req_ids = [i.requirement_id for i in issues]
    assert "POLICY-05" in req_ids


def test_policy_05_valid_ec_assignment_no_issue() -> None:
    """A properly configured extra credit assignment produces no POLICY-05 issue."""
    a = Assignment(
        assignment_id="EC1", name="EC1",
        category="EXTRA_CREDIT",
        max_points=10, weight=0.0,
        is_extra_credit=True,
    )
    assert not validate_assignment_policy(a)


# ---------------------------------------------------------------------------
# POLICY-06: excused assignments exempt from late penalty and missing-as-zero
# ---------------------------------------------------------------------------

def test_policy_06_excused_assignment_exempt_from_late_penalty() -> None:
    """An excused assignment must not incur any late penalty (POLICY-06)."""
    assignment = _assignment(max_points=100, late_penalty_per_day=0.10)
    excused_record = GradeRecord(
        student_email="ada@x.com",
        assignment_id="HW1",
        score=None,
        grade_status=GradeStatus.EXCUSED,
        days_late=5,
    )
    result = apply_late_policy(excused_record, assignment)
    # Excused → None (not penalised)
    assert result is None


def test_policy_06_excused_assignment_excluded_from_earned_and_possible() -> None:
    """An excused assignment must not reduce the student's possible points (POLICY-06)."""
    s = Student(student_id="s1", first_name="Ada", last_name="L", email="ada@x.com")
    hw1 = _assignment("HW1", "HOMEWORK", 100, 1.0)
    hw2 = _assignment("HW2", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s},
        assignments={a.assignment_id: a for a in [hw1, hw2]},
        grades=[
            GradeRecord(student_email="ada@x.com", assignment_id="HW1", score=80, grade_status=GradeStatus.RECORDED),
            GradeRecord(student_email="ada@x.com", assignment_id="HW2", score=None, grade_status=GradeStatus.EXCUSED),
        ],
    )
    result = compute_student_grade(data, s)
    # HW2 excused → only HW1 counts; 80/100 = 80%
    assert result.numeric_grade == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# POLICY-07: withdrawn students receive no letter grade in reports that exclude them
# ---------------------------------------------------------------------------

def test_policy_07_withdrawn_student_not_in_final_grades_report() -> None:
    """A withdrawn student must not appear in the final grades report (POLICY-07)."""
    s_active = Student(student_id="s1", first_name="Alice", last_name="A",
                       email="alice@x.com", status=StudentStatus.ACTIVE)
    s_withdrawn = Student(student_id="s2", first_name="Derek", last_name="D",
                          email="derek@x.com", status=StudentStatus.WITHDRAWN)
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s for s in [s_active, s_withdrawn]},
        assignments={hw.assignment_id: hw},
        grades=[
            GradeRecord(student_email="alice@x.com", assignment_id="HW1", score=80, grade_status=GradeStatus.RECORDED),
            GradeRecord(student_email="derek@x.com", assignment_id="HW1", score=100, grade_status=GradeStatus.RECORDED),
        ],
    )
    report = build_final_grades_report(data)
    assert "derek" not in report
