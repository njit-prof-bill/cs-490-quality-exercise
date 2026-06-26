"""Level 3 – Reporting tests (REPORT-01 through REPORT-07)."""
from __future__ import annotations

import pytest

from gradebook.calculator import class_average, class_median
from gradebook.models import (
    Assignment,
    GradeRecord,
    GradeStatus,
    GradebookData,
    Student,
    StudentStatus,
)
from gradebook.reports import (
    build_category_report,
    build_final_grades_report,
    build_rank_report,
    build_student_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _student(email: str, status: StudentStatus = StudentStatus.ACTIVE) -> Student:
    parts = email.split("@")[0].split(".")
    first = parts[0].capitalize()
    last = (parts[1].capitalize() if len(parts) > 1 else "X")
    return Student(student_id=email, first_name=first, last_name=last, email=email, status=status)


def _assignment(
    assignment_id: str,
    category: str,
    max_points: float,
    weight: float,
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        name=assignment_id,
        category=category,
        max_points=max_points,
        weight=weight,
    )


def _grade(email: str, assignment_id: str, score: float) -> GradeRecord:
    return GradeRecord(
        student_email=email,
        assignment_id=assignment_id,
        score=score,
        grade_status=GradeStatus.RECORDED,
    )


def _two_student_data(score_a: float, score_b: float) -> GradebookData:
    """Two active students with a single 100-point homework assignment."""
    s_a = _student("alice@x.com")
    s_b = _student("bob@x.com")
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    return GradebookData(
        students={s.email: s for s in [s_a, s_b]},
        assignments={hw.assignment_id: hw},
        grades=[
            _grade("alice@x.com", "HW1", score_a),
            _grade("bob@x.com", "HW1", score_b),
        ],
    )


# ---------------------------------------------------------------------------
# REPORT-02: rank orders by descending numeric grade; ties broken by email
# ---------------------------------------------------------------------------

def test_report_02_rankings_descending_order() -> None:
    """The rank report must list higher grades first (descending) (REPORT-02)."""
    data = _two_student_data(score_a=90, score_b=80)
    report = build_rank_report(data)
    lines = [l for l in report.splitlines() if l.startswith(("1.", "2."))]
    assert lines[0].startswith("1.")
    assert "alice" in lines[0]   # 90% is rank 1
    assert lines[1].startswith("2.")
    assert "bob" in lines[1]     # 80% is rank 2


def test_report_02_tie_broken_by_email_alphabetical() -> None:
    """Equal grades are broken by ascending email (REPORT-02)."""
    s_a = _student("alice@x.com")
    s_b = _student("bob@x.com")
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s for s in [s_a, s_b]},
        assignments={hw.assignment_id: hw},
        grades=[
            _grade("alice@x.com", "HW1", 80),
            _grade("bob@x.com", "HW1", 80),
        ],
    )
    report = build_rank_report(data)
    lines = [l for l in report.splitlines() if l.startswith(("1.", "2."))]
    # alice < bob alphabetically, so alice is rank 1
    assert "alice" in lines[0]
    assert "bob" in lines[1]


def test_report_02_withdrawn_student_excluded_from_rankings() -> None:
    """Withdrawn students must not appear in the rank report (STATE-03 / REPORT-02)."""
    s_a = _student("alice@x.com", StudentStatus.ACTIVE)
    s_b = _student("derek@x.com", StudentStatus.WITHDRAWN)
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s for s in [s_a, s_b]},
        assignments={hw.assignment_id: hw},
        grades=[
            _grade("alice@x.com", "HW1", 80),
            _grade("derek@x.com", "HW1", 100),
        ],
    )
    report = build_rank_report(data)
    assert "derek" not in report


# ---------------------------------------------------------------------------
# REPORT-03: category report shows average percentage, not average raw points
# ---------------------------------------------------------------------------

def test_report_03_category_report_uses_percentages() -> None:
    """Category averages must be percentages across students, not raw points (REPORT-03)."""
    # Student A: 90/100 (90%) ; Student B: 25/100 (25%) → avg = 57.50%
    # If bug present, avg raw = (90+25)/2 = 57.5 → shows 57.5% (coincidentally same here)
    # Use different max_points to make the two differ:
    # Student A: 90/100 = 90%; Student B: 50/200 = 25% → avg percent = 57.5%
    # avg raw points = (90+50)/2 = 70 → would show 70.00% (wrong)
    s_a = _student("alice@x.com")
    s_b = _student("bob@x.com")
    hw_a = _assignment("HW1", "HOMEWORK", 100, 1.0)
    hw_b = _assignment("HW2", "HOMEWORK", 200, 1.0)
    data = GradebookData(
        students={s.email: s for s in [s_a, s_b]},
        assignments={a.assignment_id: a for a in [hw_a, hw_b]},
        grades=[
            _grade("alice@x.com", "HW1", 90),
            _grade("alice@x.com", "HW2", 0),
            _grade("bob@x.com", "HW1", 0),
            _grade("bob@x.com", "HW2", 50),
        ],
    )
    # alice: HOMEWORK = (90+0)/(100+200)*100 = 30%
    # bob:   HOMEWORK = (0+50)/(100+200)*100 = 16.67%
    # category average percent = (30+16.67)/2 = 23.33%
    # if raw points: alice=90, bob=50 → avg=70 → WRONG
    report = build_category_report(data)
    assert "23.33%" in report


# ---------------------------------------------------------------------------
# REPORT-05: median of even number of students is mean of two middle grades
# ---------------------------------------------------------------------------

def test_report_05_median_even_count() -> None:
    """For an even number of students the median is the mean of the two middle grades (REPORT-05)."""
    data = _two_student_data(score_a=70, score_b=80)
    # sorted grades: [70, 80] → median = (70+80)/2 = 75
    median = class_median(data)
    assert median == pytest.approx(75.0)


def test_report_05_median_odd_count() -> None:
    """For an odd number of students the median is the middle grade (REPORT-05)."""
    s_a = _student("a@x.com")
    s_b = _student("b@x.com")
    s_c = _student("c@x.com")
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s for s in [s_a, s_b, s_c]},
        assignments={hw.assignment_id: hw},
        grades=[
            _grade("a@x.com", "HW1", 60),
            _grade("b@x.com", "HW1", 75),
            _grade("c@x.com", "HW1", 90),
        ],
    )
    assert class_median(data) == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# REPORT-07: percentage values are formatted to exactly two decimal places
# ---------------------------------------------------------------------------

def test_report_07_format_two_decimal_places() -> None:
    """Percentage values in reports must be formatted to exactly two decimal places (REPORT-07)."""
    data = _two_student_data(score_a=100, score_b=80)
    report = build_final_grades_report(data)
    # Alice = 100.00%, Bob = 80.00%
    assert "100.00%" in report
    assert "80.00%" in report


# ---------------------------------------------------------------------------
# REPORT-01: student-report includes name, email, status, grade, letter, assignments
# ---------------------------------------------------------------------------

def test_report_01_student_report_contains_required_fields() -> None:
    """student-report must include name, email, status, numeric grade, letter grade, assignments (REPORT-01)."""
    s = _student("alice@x.com")
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s},
        assignments={hw.assignment_id: hw},
        grades=[_grade("alice@x.com", "HW1", 85)],
    )
    report = build_student_report(data, "alice@x.com")
    assert "Alice" in report          # name
    assert "alice@x.com" in report    # email
    assert "active" in report         # status
    assert "85.00%" in report         # numeric grade (2 d.p.)
    assert "B" in report              # letter grade
    assert "HW1" in report            # assignment line


# ---------------------------------------------------------------------------
# REPORT-04: final-grades includes active + inactive, excludes withdrawn
# ---------------------------------------------------------------------------

def test_report_04_inactive_student_included_in_final_grades() -> None:
    """Inactive students must appear in the final grades report (REPORT-04)."""
    s_active = _student("alice@x.com", StudentStatus.ACTIVE)
    s_inactive = _student("carla@x.com", StudentStatus.INACTIVE)
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s for s in [s_active, s_inactive]},
        assignments={hw.assignment_id: hw},
        grades=[
            _grade("alice@x.com", "HW1", 80),
            _grade("carla@x.com", "HW1", 70),
        ],
    )
    report = build_final_grades_report(data)
    assert "alice" in report
    assert "carla" in report


def test_report_04_withdrawn_student_excluded_from_final_grades() -> None:
    """Withdrawn students must not appear in the final grades report (REPORT-04)."""
    s_active = _student("alice@x.com", StudentStatus.ACTIVE)
    s_withdrawn = _student("derek@x.com", StudentStatus.WITHDRAWN)
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s for s in [s_active, s_withdrawn]},
        assignments={hw.assignment_id: hw},
        grades=[
            _grade("alice@x.com", "HW1", 80),
            _grade("derek@x.com", "HW1", 100),
        ],
    )
    report = build_final_grades_report(data)
    assert "alice" in report
    assert "derek" not in report


# ---------------------------------------------------------------------------
# REPORT-06: class average excludes withdrawn students
# ---------------------------------------------------------------------------

def test_report_06_class_average_excludes_withdrawn() -> None:
    """Class average must not include withdrawn students' grades (REPORT-06)."""
    s_a = _student("alice@x.com", StudentStatus.ACTIVE)
    s_b = _student("bob@x.com", StudentStatus.ACTIVE)
    s_w = _student("derek@x.com", StudentStatus.WITHDRAWN)
    hw = _assignment("HW1", "HOMEWORK", 100, 1.0)
    data = GradebookData(
        students={s.email: s for s in [s_a, s_b, s_w]},
        assignments={hw.assignment_id: hw},
        grades=[
            _grade("alice@x.com", "HW1", 60),
            _grade("bob@x.com", "HW1", 80),
            _grade("derek@x.com", "HW1", 100),  # withdrawn – must not count
        ],
    )
    avg = class_average(data)
    # Only alice (60) and bob (80) are included → (60+80)/2 = 70
    assert avg == pytest.approx(70.0)
