"""Level 2 – CSV and import tests (CSV-01 through CSV-08)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gradebook.assignments import find_duplicate_assignments
from gradebook.importer import import_assignments, import_students, load_gradebook_data
from gradebook.models import Assignment, GradeRecord, GradeStatus
from gradebook.policies import validate_grade_value
from gradebook.students import find_duplicate_students


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assignment(
    assignment_id: str = "HW1",
    max_points: float = 100,
    is_extra_credit: bool = False,
    grading_mode: str = "points",
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        name=assignment_id,
        category="HOMEWORK",
        max_points=max_points,
        weight=1.0,
        is_extra_credit=is_extra_credit,
        grading_mode=grading_mode,
    )


def _record(score: float, assignment_id: str = "HW1") -> GradeRecord:
    return GradeRecord(
        student_email="a@example.com",
        assignment_id=assignment_id,
        score=score,
        grade_status=GradeStatus.RECORDED,
    )


# ---------------------------------------------------------------------------
# CSV-01: email normalized by stripping whitespace and lowercasing
# ---------------------------------------------------------------------------

def test_csv_01_email_trimmed_and_lowercased() -> None:
    """Student emails must be trimmed and lowercased on import (CSV-01)."""
    from gradebook.students import build_student

    row = {
        "student_id": "S1",
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "  ALICE@Example.COM  ",
        "status": "active",
        "section": "A",
    }
    student, _ = build_student(row, row_number=2)
    assert student is not None
    assert student.email == "alice@example.com"


# ---------------------------------------------------------------------------
# CSV-04: score > max_points is invalid unless extra credit
# ---------------------------------------------------------------------------

def test_csv_04_score_exceeds_max_produces_issue() -> None:
    """A score above max_points on a regular assignment must raise a CSV-04 issue."""
    assignment = _assignment(max_points=100, is_extra_credit=False)
    record = _record(score=101)
    issues = validate_grade_value(record, assignment)
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-04" in req_ids


def test_csv_04_score_at_max_is_valid() -> None:
    """A score exactly equal to max_points is valid."""
    assignment = _assignment(max_points=100, is_extra_credit=False)
    record = _record(score=100)
    issues = validate_grade_value(record, assignment)
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-04" not in req_ids


def test_csv_04_extra_credit_above_max_is_valid() -> None:
    """Extra credit assignments are exempt from the max_points ceiling (CSV-04)."""
    assignment = _assignment(max_points=5, is_extra_credit=True)
    record = _record(score=6)
    issues = validate_grade_value(record, assignment)
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-04" not in req_ids


# ---------------------------------------------------------------------------
# CSV-06: header-only CSV must produce a validation issue
# ---------------------------------------------------------------------------

def test_csv_06_header_only_students_file_produces_issue(tmp_path: Path) -> None:
    """A students CSV with a header row but no data rows must raise a CSV-06 issue."""
    csv_file = tmp_path / "students.csv"
    csv_file.write_text("student_id,first_name,last_name,email,status,section\n")
    _, issues = import_students(csv_file)
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-06" in req_ids


def test_csv_06_header_only_full_load_produces_issue(tmp_path: Path) -> None:
    """load_gradebook_data records a CSV-06 issue when any input file has no data rows."""
    students_file = tmp_path / "students.csv"
    students_file.write_text("student_id,first_name,last_name,email,status,section\n")

    assignments_file = tmp_path / "assignments.csv"
    assignments_file.write_text(
        "assignment_id,name,category,max_points,weight,due_date,"
        "drop_lowest_eligible,is_extra_credit,late_penalty_per_day,"
        "min_score_floor,grading_mode\n"
        "HW1,Homework 1,HOMEWORK,100,1.0,,,false,0.10,,points\n"
    )

    grades_file = tmp_path / "grades.csv"
    grades_file.write_text("student_email,assignment_id,score,status,days_late,notes\n")

    data = load_gradebook_data(students_file, assignments_file, grades_file)
    req_ids = [i.requirement_id for i in data.validation_issues]
    assert "CSV-06" in req_ids


# ---------------------------------------------------------------------------
# CSV-07: malformed row must not crash – importer must continue
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# CSV-02: duplicate students detected by normalized email
# ---------------------------------------------------------------------------

def test_csv_02_duplicate_email_produces_issue() -> None:
    """Two students sharing the same normalized email must produce a CSV-02 issue (CSV-02)."""
    from gradebook.models import Student, StudentStatus

    s1 = Student(student_id="S1", first_name="Alice", last_name="A", email="alice@x.com")
    s2 = Student(student_id="S2", first_name="Alice", last_name="B", email="alice@x.com")
    issues = find_duplicate_students([s1, s2])
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-02" in req_ids


def test_csv_02_unique_emails_no_issue() -> None:
    """Students with distinct emails produce no CSV-02 issue (CSV-02)."""
    from gradebook.models import Student

    s1 = Student(student_id="S1", first_name="Alice", last_name="A", email="alice@x.com")
    s2 = Student(student_id="S2", first_name="Bob", last_name="B", email="bob@x.com")
    assert not find_duplicate_students([s1, s2])


# ---------------------------------------------------------------------------
# CSV-03: duplicate assignment IDs must be reported
# ---------------------------------------------------------------------------

def test_csv_03_duplicate_assignment_id_produces_issue() -> None:
    """Two assignments with the same ID must produce a CSV-03 issue (CSV-03)."""
    a1 = Assignment(assignment_id="HW1", name="HW1a", category="HOMEWORK", max_points=100, weight=1.0)
    a2 = Assignment(assignment_id="HW1", name="HW1b", category="HOMEWORK", max_points=100, weight=1.0)
    issues = find_duplicate_assignments([a1, a2])
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-03" in req_ids


def test_csv_03_unique_assignment_ids_no_issue() -> None:
    """Assignments with distinct IDs produce no CSV-03 issue (CSV-03)."""
    a1 = Assignment(assignment_id="HW1", name="HW1", category="HOMEWORK", max_points=100, weight=1.0)
    a2 = Assignment(assignment_id="HW2", name="HW2", category="HOMEWORK", max_points=100, weight=1.0)
    assert not find_duplicate_assignments([a1, a2])


# ---------------------------------------------------------------------------
# CSV-05: negative scores are invalid
# ---------------------------------------------------------------------------

def test_csv_05_negative_score_produces_issue() -> None:
    """A negative score must produce a CSV-05 validation issue (CSV-05)."""
    assignment = _assignment(max_points=100)
    record = _record(score=-1)
    issues = validate_grade_value(record, assignment)
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-05" in req_ids


def test_csv_05_zero_score_is_valid() -> None:
    """A score of zero must not produce a CSV-05 issue (CSV-05)."""
    assignment = _assignment(max_points=100)
    record = _record(score=0)
    issues = validate_grade_value(record, assignment)
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-05" not in req_ids


# ---------------------------------------------------------------------------
# CSV-07: malformed row must not crash – importer must continue
# ---------------------------------------------------------------------------

def test_csv_07_malformed_student_row_continues_processing(tmp_path: Path) -> None:
    """A malformed student row must be skipped without crashing; valid rows still import."""
    csv_file = tmp_path / "students.csv"
    csv_file.write_text(
        textwrap.dedent("""\
        student_id,first_name,last_name,email,status,section
        ,bad,row,,active,A
        S002,Alice,Smith,alice@example.com,active,A
        """)
    )
    students, issues = import_students(csv_file)
    # The valid row must have been imported despite the malformed one.
    assert "alice@example.com" in students
    req_ids = [i.requirement_id for i in issues]
    assert "CSV-07" in req_ids
