"""
Level 3 Reporting Tests
Tests named after requirement IDs from grading-policy.md
"""
from __future__ import annotations

import pytest

from gradebook.calculator import class_median, compute_all_students, compute_student_grade
from gradebook.models import (
    Assignment,
    GradebookData,
    GradeRecord,
    GradeStatus,
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

def make_student(
    email: str,
    first: str = "Test",
    last: str = "Student",
    status: StudentStatus = StudentStatus.ACTIVE,
) -> Student:
    return Student(
        student_id=email,
        first_name=first,
        last_name=last,
        email=email,
        status=status,
    )


def make_assignment(
    assignment_id: str,
    category: str = "HOMEWORK",
    max_points: float = 100.0,
    weight: float = 1.0,
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        name=assignment_id,
        category=category,
        max_points=max_points,
        weight=weight,
    )


def make_grade(email: str, assignment_id: str, score: float, source_row: int = 2) -> GradeRecord:
    return GradeRecord(
        student_email=email,
        assignment_id=assignment_id,
        score=score,
        grade_status=GradeStatus.RECORDED,
        source_row=source_row,
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
# REPORT-01: student-report contains required fields
# ---------------------------------------------------------------------------

def test_report_01_student_report_contains_name():
    data = simple_data(
        [make_student("alice@njit.edu", "Alice", "Nguyen")],
        [make_assignment("HW1")],
        [make_grade("alice@njit.edu", "HW1", 85.0)],
    )
    report = build_student_report(data, "alice@njit.edu")
    assert "Alice Nguyen" in report


def test_report_01_student_report_contains_email():
    data = simple_data(
        [make_student("alice@njit.edu", "Alice", "Nguyen")],
        [make_assignment("HW1")],
        [make_grade("alice@njit.edu", "HW1", 85.0)],
    )
    report = build_student_report(data, "alice@njit.edu")
    assert "alice@njit.edu" in report


def test_report_01_student_report_contains_status():
    data = simple_data(
        [make_student("alice@njit.edu")],
        [make_assignment("HW1")],
        [make_grade("alice@njit.edu", "HW1", 85.0)],
    )
    report = build_student_report(data, "alice@njit.edu")
    assert "active" in report


def test_report_01_student_report_contains_letter_grade():
    data = simple_data(
        [make_student("alice@njit.edu")],
        [make_assignment("HW1")],
        [make_grade("alice@njit.edu", "HW1", 95.0)],
    )
    report = build_student_report(data, "alice@njit.edu")
    assert "A" in report


def test_report_01_student_report_contains_assignments_section():
    data = simple_data(
        [make_student("alice@njit.edu")],
        [make_assignment("HW1")],
        [make_grade("alice@njit.edu", "HW1", 85.0)],
    )
    report = build_student_report(data, "alice@njit.edu")
    assert "Assignments:" in report


# ---------------------------------------------------------------------------
# REPORT-02: rank orders by descending grade, ties broken by email ascending
# ---------------------------------------------------------------------------

def test_report_02_rank_descending_order():
    students = [
        make_student("a@njit.edu"),
        make_student("b@njit.edu"),
    ]
    assignments = [make_assignment("HW1")]
    grades = [
        make_grade("a@njit.edu", "HW1", 70.0),
        make_grade("b@njit.edu", "HW1", 90.0),
    ]
    data = simple_data(students, assignments, grades)
    report = build_rank_report(data)
    lines = [l for l in report.splitlines() if l.startswith(("1.", "2."))]
    assert "b@njit.edu" in lines[0]  # higher grade ranked first
    assert "a@njit.edu" in lines[1]


def test_report_02_rank_tie_broken_by_email_ascending():
    students = [
        make_student("z@njit.edu"),
        make_student("a@njit.edu"),
    ]
    assignments = [make_assignment("HW1")]
    grades = [
        make_grade("z@njit.edu", "HW1", 80.0),
        make_grade("a@njit.edu", "HW1", 80.0),
    ]
    data = simple_data(students, assignments, grades)
    report = build_rank_report(data)
    lines = [l for l in report.splitlines() if l.startswith(("1.", "2."))]
    assert "a@njit.edu" in lines[0]  # alphabetically first wins tie
    assert "z@njit.edu" in lines[1]


def test_report_02_withdrawn_excluded_from_rank():
    students = [
        make_student("a@njit.edu"),
        make_student("w@njit.edu", status=StudentStatus.WITHDRAWN),
    ]
    assignments = [make_assignment("HW1")]
    grades = [
        make_grade("a@njit.edu", "HW1", 80.0),
        make_grade("w@njit.edu", "HW1", 95.0),
    ]
    data = simple_data(students, assignments, grades)
    report = build_rank_report(data)
    assert "w@njit.edu" not in report


def test_report_02_inactive_included_in_rank():
    """REPORT-02: inactive students ARE ranked (only withdrawn are excluded)."""
    students = [
        make_student("a@njit.edu"),
        make_student("i@njit.edu", status=StudentStatus.INACTIVE),
    ]
    assignments = [make_assignment("HW1")]
    grades = [
        make_grade("a@njit.edu", "HW1", 80.0),
        make_grade("i@njit.edu", "HW1", 90.0),
    ]
    data = simple_data(students, assignments, grades)
    report = build_rank_report(data)
    assert "i@njit.edu" in report


# ---------------------------------------------------------------------------
# REPORT-03: category-report shows average percentage, not average raw points
# ---------------------------------------------------------------------------

def test_report_03_category_average_is_percentage_not_raw_points():
    """
    Two students: one scores 50/100 (50%), one scores 100/100 (100%).
    Average percentage = 75%. Average raw points = 75 (same here).
    Use different max_points to distinguish: 50/50=100%, 25/50=50% -> avg=75%.
    Raw points avg = (50+25)/2 = 37.5. So report must show 75%, not 37.5%.
    """
    students = [
        make_student("a@njit.edu"),
        make_student("b@njit.edu"),
    ]
    assignments = [make_assignment("HW1", max_points=50.0)]
    grades = [
        make_grade("a@njit.edu", "HW1", 50.0),  # 100%
        make_grade("b@njit.edu", "HW1", 25.0),  # 50%
    ]
    data = simple_data(students, assignments, grades)
    report = build_category_report(data)
    assert "75.00%" in report
    assert "37.5" not in report


# ---------------------------------------------------------------------------
# REPORT-04: final-grades includes active and inactive, excludes withdrawn
# ---------------------------------------------------------------------------

def test_report_04_final_grades_includes_active():
    students = [make_student("a@njit.edu", status=StudentStatus.ACTIVE)]
    assignments = [make_assignment("HW1")]
    grades = [make_grade("a@njit.edu", "HW1", 80.0)]
    data = simple_data(students, assignments, grades)
    report = build_final_grades_report(data)
    assert "a@njit.edu" in report


def test_report_04_final_grades_includes_inactive():
    students = [make_student("i@njit.edu", status=StudentStatus.INACTIVE)]
    assignments = [make_assignment("HW1")]
    grades = [make_grade("i@njit.edu", "HW1", 80.0)]
    data = simple_data(students, assignments, grades)
    report = build_final_grades_report(data)
    assert "i@njit.edu" in report


def test_report_04_final_grades_excludes_withdrawn():
    students = [
        make_student("a@njit.edu"),
        make_student("w@njit.edu", status=StudentStatus.WITHDRAWN),
    ]
    assignments = [make_assignment("HW1")]
    grades = [
        make_grade("a@njit.edu", "HW1", 80.0),
        make_grade("w@njit.edu", "HW1", 95.0),
    ]
    data = simple_data(students, assignments, grades)
    report = build_final_grades_report(data)
    assert "w@njit.edu" not in report


# ---------------------------------------------------------------------------
# REPORT-05: class median is standard statistical median
# ---------------------------------------------------------------------------

def test_report_05_median_odd_count():
    """Odd number: median is the middle value. [60, 70, 80] -> 70."""
    students = [make_student(f"{i}@njit.edu") for i in range(3)]
    assignments = [make_assignment("HW1")]
    grades = [
        make_grade("0@njit.edu", "HW1", 60.0),
        make_grade("1@njit.edu", "HW1", 70.0),
        make_grade("2@njit.edu", "HW1", 80.0),
    ]
    data = simple_data(students, assignments, grades)
    median = class_median(data)
    assert median == pytest.approx(70.0)


def test_report_05_median_even_count():
    """Even number: median is mean of two middle values. [60, 70, 80, 90] -> 75."""
    students = [make_student(f"{i}@njit.edu") for i in range(4)]
    assignments = [make_assignment("HW1")]
    grades = [
        make_grade("0@njit.edu", "HW1", 60.0),
        make_grade("1@njit.edu", "HW1", 70.0),
        make_grade("2@njit.edu", "HW1", 80.0),
        make_grade("3@njit.edu", "HW1", 90.0),
    ]
    data = simple_data(students, assignments, grades)
    median = class_median(data)
    assert median == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# REPORT-06: class average excludes withdrawn students
# ---------------------------------------------------------------------------

def test_report_06_class_average_excludes_withdrawn():
    """Withdrawn student with 100% should not inflate the average."""
    students = [
        make_student("a@njit.edu"),
        make_student("w@njit.edu", status=StudentStatus.WITHDRAWN),
    ]
    assignments = [make_assignment("HW1")]
    grades = [
        make_grade("a@njit.edu", "HW1", 60.0),
        make_grade("w@njit.edu", "HW1", 100.0),
    ]
    data = simple_data(students, assignments, grades)
    report = build_final_grades_report(data)
    assert "60.00%" in report  # average should be 60, not 80


# ---------------------------------------------------------------------------
# REPORT-07: percentage values formatted to exactly two decimal places
# ---------------------------------------------------------------------------

def test_report_07_final_grades_two_decimal_places():
    students = [make_student("a@njit.edu")]
    assignments = [make_assignment("HW1")]
    grades = [make_grade("a@njit.edu", "HW1", 85.0)]
    data = simple_data(students, assignments, grades)
    report = build_final_grades_report(data)
    assert "85.00%" in report


def test_report_07_student_report_two_decimal_places():
    students = [make_student("a@njit.edu")]
    assignments = [make_assignment("HW1")]
    grades = [make_grade("a@njit.edu", "HW1", 85.0)]
    data = simple_data(students, assignments, grades)
    report = build_student_report(data, "a@njit.edu")
    assert "85.00%" in report


def test_report_07_rank_report_two_decimal_places():
    students = [make_student("a@njit.edu")]
    assignments = [make_assignment("HW1")]
    grades = [make_grade("a@njit.edu", "HW1", 85.0)]
    data = simple_data(students, assignments, grades)
    report = build_rank_report(data)
    assert "85.00%" in report
