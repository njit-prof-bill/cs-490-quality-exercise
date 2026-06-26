"""Level 1 – Core grading tests (CORE-05, CORE-06, CORE-07, CORE-09)."""
from __future__ import annotations

from datetime import date

import pytest

from gradebook.calculator import compute_student_grade
from gradebook.models import (
    Assignment,
    GradeRecord,
    GradeStatus,
    GradebookData,
    Student,
)
from gradebook.reports import build_final_grades_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _student(email: str = "ada@example.com") -> Student:
    return Student(student_id="s1", first_name="Ada", last_name="Lovelace", email=email)


def _assignment(
    assignment_id: str,
    category: str,
    max_points: float,
    weight: float,
    *,
    is_extra_credit: bool = False,
    grading_mode: str = "points",
    due_date: date | None = None,
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        name=assignment_id,
        category=category,
        max_points=max_points,
        weight=weight,
        is_extra_credit=is_extra_credit,
        grading_mode=grading_mode,
        due_date=due_date,
    )


def _grade(
    assignment_id: str,
    score: float | None,
    grade_status: GradeStatus = GradeStatus.RECORDED,
    email: str = "ada@example.com",
) -> GradeRecord:
    return GradeRecord(
        student_email=email,
        assignment_id=assignment_id,
        score=score,
        grade_status=grade_status,
    )


def _data(
    assignments: list[Assignment],
    grades: list[GradeRecord],
    student: Student | None = None,
) -> GradebookData:
    s = student or _student()
    return GradebookData(
        students={s.email: s},
        assignments={a.assignment_id: a for a in assignments},
        grades=grades,
    )


# ---------------------------------------------------------------------------
# CORE-05: drop lowest quiz only when student has ≥4 non-excused quiz scores
# ---------------------------------------------------------------------------

def test_core_05_no_drop_with_fewer_than_four_quizzes() -> None:
    """With only 3 quiz scores the lowest must NOT be dropped (CORE-05)."""
    data = _data(
        assignments=[
            _assignment("Q1", "QUIZ", 20, 0.30),
            _assignment("Q2", "QUIZ", 20, 0.30),
            _assignment("Q3", "QUIZ", 20, 0.30),
            _assignment("EX1", "EXAM", 100, 0.70),
        ],
        grades=[
            _grade("Q1", 5),   # lowest
            _grade("Q2", 20),
            _grade("Q3", 20),
            _grade("EX1", 100),
        ],
    )
    result = compute_student_grade(data, _student())
    # Without drop: QUIZ earned = 5+20+20 = 45 / 60 = 75%; EXAM = 100%
    # total = 75 * 0.30 + 100 * 0.70 = 22.5 + 70 = 92.5
    assert result.numeric_grade == pytest.approx(92.5)


def test_core_05_drop_lowest_with_four_quizzes() -> None:
    """With exactly 4 non-excused quizzes the lowest MUST be dropped (CORE-05)."""
    data = _data(
        assignments=[
            _assignment("Q1", "QUIZ", 20, 0.30),
            _assignment("Q2", "QUIZ", 20, 0.30),
            _assignment("Q3", "QUIZ", 20, 0.30),
            _assignment("Q4", "QUIZ", 20, 0.30),
            _assignment("EX1", "EXAM", 100, 0.70),
        ],
        grades=[
            _grade("Q1", 0),   # lowest – must be dropped
            _grade("Q2", 20),
            _grade("Q3", 20),
            _grade("Q4", 20),
            _grade("EX1", 100),
        ],
    )
    result = compute_student_grade(data, _student())
    # After drop: QUIZ earned = 20+20+20 = 60 / 60 = 100%; EXAM = 100%
    # total = 100 * 0.30 + 100 * 0.70 = 100
    assert result.numeric_grade == pytest.approx(100.0)


def test_core_05_excused_quiz_not_counted_toward_threshold() -> None:
    """An excused quiz does not count as a non-excused score for the 4-quiz threshold (CORE-05)."""
    data = _data(
        assignments=[
            _assignment("Q1", "QUIZ", 20, 0.30),
            _assignment("Q2", "QUIZ", 20, 0.30),
            _assignment("Q3", "QUIZ", 20, 0.30),
            _assignment("Q4", "QUIZ", 20, 0.30),
            _assignment("EX1", "EXAM", 100, 0.70),
        ],
        grades=[
            _grade("Q1", 0),   # lowest
            _grade("Q2", 20),
            _grade("Q3", 20),
            # Q4 is excused – only 3 non-excused quizzes → NO drop
            _grade("Q4", None, GradeStatus.EXCUSED),
            _grade("EX1", 100),
        ],
    )
    result = compute_student_grade(data, _student())
    # No drop because only 3 non-excused quizzes.
    # QUIZ: Q4 excused so possible = 60, earned = 0+20+20 = 40 → 66.67%
    # total = 66.67% * 0.30 + 100 * 0.70 ≈ 20 + 70 = 90
    assert result.numeric_grade == pytest.approx(90.0)


# ---------------------------------------------------------------------------
# CORE-06: extra credit raises grade but is capped at 100
# ---------------------------------------------------------------------------

def test_core_06_extra_credit_raises_grade() -> None:
    """Extra credit earned points are added to the student's numeric grade (CORE-06)."""
    data = _data(
        assignments=[
            _assignment("HW1", "HOMEWORK", 100, 1.0),
            _assignment("EC1", "EXTRA_CREDIT", 5, 0.0, is_extra_credit=True),
        ],
        grades=[
            _grade("HW1", 80),
            _grade("EC1", 5),   # full 5 extra-credit points
        ],
    )
    result = compute_student_grade(data, _student())
    # HW category: 80/100 = 80%  * 1.0 = 80
    # EC: +5 raw earned points → 85
    assert result.numeric_grade == pytest.approx(85.0)


def test_core_06_extra_credit_capped_at_100() -> None:
    """Final numeric grade never exceeds 100 even with extra credit (CORE-06)."""
    data = _data(
        assignments=[
            _assignment("HW1", "HOMEWORK", 100, 1.0),
            _assignment("EC1", "EXTRA_CREDIT", 10, 0.0, is_extra_credit=True),
        ],
        grades=[
            _grade("HW1", 100),   # already 100%
            _grade("EC1", 10),    # EC would push to 110 without cap
        ],
    )
    result = compute_student_grade(data, _student())
    assert result.numeric_grade == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# CORE-07: percentages displayed to exactly two decimal places
# ---------------------------------------------------------------------------

def test_core_07_final_grades_report_two_decimal_places() -> None:
    """Grade percentages in the final grades report are formatted to 2 d.p. (CORE-07)."""
    data = _data(
        assignments=[_assignment("HW1", "HOMEWORK", 3, 1.0)],
        grades=[_grade("HW1", 1)],  # 1/3 = 33.33...%
    )
    report = build_final_grades_report(data)
    # Must have a percentage with exactly two decimal digits
    assert "33.33%" in report


# ---------------------------------------------------------------------------
# CORE-09: pass/fail assignments: PASS = full credit, FAIL = zero credit
# ---------------------------------------------------------------------------

def test_core_09_pass_earns_full_credit() -> None:
    """PASS earns the full max_points for a pass/fail assignment (CORE-09)."""
    data = _data(
        assignments=[
            _assignment("P1", "PARTICIPATION", 10, 0.20, grading_mode="passfail"),
            _assignment("HW1", "HOMEWORK", 100, 0.80),
        ],
        grades=[
            _grade("P1", 1.0),   # score=1.0 represents PASS
            _grade("HW1", 100),
        ],
    )
    result = compute_student_grade(data, _student())
    # PARTICIPATION: 10/10 = 100% * 0.20 = 20
    # HOMEWORK: 100/100 = 100% * 0.80 = 80
    # total = 100
    assert result.numeric_grade == pytest.approx(100.0)


def test_core_09_fail_earns_zero_credit() -> None:
    """FAIL earns zero points for a pass/fail assignment (CORE-09)."""
    data = _data(
        assignments=[
            _assignment("P1", "PARTICIPATION", 10, 0.20, grading_mode="passfail"),
            _assignment("HW1", "HOMEWORK", 100, 0.80),
        ],
        grades=[
            _grade("P1", 0.0),   # score=0.0 represents FAIL
            _grade("HW1", 100),
        ],
    )
    result = compute_student_grade(data, _student())
    # PARTICIPATION: 0/10 = 0% * 0.20 = 0
    # HOMEWORK: 100% * 0.80 = 80
    assert result.numeric_grade == pytest.approx(80.0)
