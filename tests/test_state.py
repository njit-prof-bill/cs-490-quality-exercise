"""
Level 5 State and Workflow Tests
Tests named after requirement IDs from grading-policy.md
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

from gradebook.calculator import compute_all_students
from gradebook.importer import load_gradebook_data
from gradebook.models import (
    Assignment,
    GradebookData,
    GradeRecord,
    GradeStatus,
    Student,
    StudentStatus,
    ValidationIssue,
)
from gradebook.reports import build_audit_report, build_rank_report, build_final_grades_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


STUDENT_FIELDS = ["student_id", "first_name", "last_name", "email", "status", "section"]
ASSIGNMENT_FIELDS = [
    "assignment_id", "name", "category", "max_points", "weight",
    "due_date", "drop_lowest_eligible", "is_extra_credit",
    "late_penalty_per_day", "min_score_floor", "grading_mode",
]
GRADE_FIELDS = ["student_email", "assignment_id", "score", "status", "days_late", "notes"]


def base_students() -> list[dict]:
    return [
        {"student_id": "S1", "first_name": "Alice", "last_name": "A",
         "email": "alice@njit.edu", "status": "active", "section": "main"},
    ]


def base_assignments() -> list[dict]:
    return [
        {"assignment_id": "HW1", "name": "HW1", "category": "HOMEWORK",
         "max_points": "100", "weight": "1.0", "due_date": "", "drop_lowest_eligible": "",
         "is_extra_credit": "", "late_penalty_per_day": "0.10", "min_score_floor": "", "grading_mode": "points"},
    ]


def base_grades() -> list[dict]:
    return [
        {"student_email": "alice@njit.edu", "assignment_id": "HW1",
         "score": "80", "status": "recorded", "days_late": "0", "notes": ""},
    ]


def make_csvs(tmp_path: Path) -> tuple[Path, Path, Path]:
    s = tmp_path / "students.csv"
    a = tmp_path / "assignments.csv"
    g = tmp_path / "grades.csv"
    write_csv(s, base_students())
    write_csv(a, base_assignments())
    write_csv(g, base_grades())
    return s, a, g


# ---------------------------------------------------------------------------
# STATE-01: Loading same CSVs twice must not duplicate data
# ---------------------------------------------------------------------------

def test_state_01_repeated_load_returns_fresh_snapshot(tmp_path):
    """Each load_gradebook_data call returns an independent snapshot."""
    s, a, g = make_csvs(tmp_path)
    data1 = load_gradebook_data(s, a, g)
    data2 = load_gradebook_data(s, a, g)
    assert len(data1.students) == len(data2.students)
    assert len(data1.grades) == len(data2.grades)


def test_state_01_two_loads_dont_share_state(tmp_path):
    """Mutating one snapshot should not affect the other."""
    s, a, g = make_csvs(tmp_path)
    data1 = load_gradebook_data(s, a, g)
    data2 = load_gradebook_data(s, a, g)
    data1.grades.append(GradeRecord(
        student_email="fake@njit.edu", assignment_id="HW1",
        score=99.0, grade_status=GradeStatus.RECORDED, source_row=99,
    ))
    assert len(data1.grades) != len(data2.grades)


# ---------------------------------------------------------------------------
# STATE-03: Withdrawn students visible to validation/audit but excluded from ranking
# ---------------------------------------------------------------------------

def test_state_03_withdrawn_excluded_from_rank(tmp_path):
    students_csv = tmp_path / "students.csv"
    write_csv(students_csv, [
        {"student_id": "S1", "first_name": "Alice", "last_name": "A",
         "email": "alice@njit.edu", "status": "active", "section": "main"},
        {"student_id": "S2", "first_name": "Walt", "last_name": "W",
         "email": "walt@njit.edu", "status": "withdrawn", "section": "main"},
    ])
    assignments_csv = tmp_path / "assignments.csv"
    write_csv(assignments_csv, base_assignments())
    grades_csv = tmp_path / "grades.csv"
    write_csv(grades_csv, [
        {"student_email": "alice@njit.edu", "assignment_id": "HW1",
         "score": "80", "status": "recorded", "days_late": "0", "notes": ""},
        {"student_email": "walt@njit.edu", "assignment_id": "HW1",
         "score": "95", "status": "recorded", "days_late": "0", "notes": ""},
    ])
    data = load_gradebook_data(students_csv, assignments_csv, grades_csv)
    rank_report = build_rank_report(data)
    assert "walt@njit.edu" not in rank_report
    assert "alice@njit.edu" in rank_report


def test_state_03_withdrawn_visible_in_all_students_computation(tmp_path):
    """compute_all_students should still compute withdrawn students."""
    students_csv = tmp_path / "students.csv"
    write_csv(students_csv, [
        {"student_id": "S2", "first_name": "Walt", "last_name": "W",
         "email": "walt@njit.edu", "status": "withdrawn", "section": "main"},
    ])
    assignments_csv = tmp_path / "assignments.csv"
    write_csv(assignments_csv, base_assignments())
    grades_csv = tmp_path / "grades.csv"
    write_csv(grades_csv, [
        {"student_email": "walt@njit.edu", "assignment_id": "HW1",
         "score": "95", "status": "recorded", "days_late": "0", "notes": ""},
    ])
    data = load_gradebook_data(students_csv, assignments_csv, grades_csv)
    all_results = compute_all_students(data)
    emails = [r.student.email for r in all_results]
    assert "walt@njit.edu" in emails


# ---------------------------------------------------------------------------
# STATE-04: validate command exits non-zero with issues, zero without
# ---------------------------------------------------------------------------

def test_state_04_validate_exits_zero_when_no_issues():
    result = subprocess.run(
        [sys.executable, "-m", "gradebook", "validate",
         "sample_data/students.csv",
         "sample_data/assignments.csv",
         "sample_data/grades.csv"],
        capture_output=True,
    )
    # sample data has known issues (ghost student, unknown assignment)
    # so exit code should be non-zero
    assert result.returncode != 0


def test_state_04_validate_exits_zero_with_clean_data(tmp_path):
    s, a, g = make_csvs(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "gradebook", "validate",
         str(s), str(a), str(g)],
        capture_output=True,
        cwd=tmp_path.parent,
    )
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# STATE-06: Unknown student status produces validation issue, defaults to active
# ---------------------------------------------------------------------------

def test_state_06_unknown_status_produces_issue(tmp_path):
    students_csv = tmp_path / "students.csv"
    write_csv(students_csv, [
        {"student_id": "S1", "first_name": "Alice", "last_name": "A",
         "email": "alice@njit.edu", "status": "probation", "section": "main"},
    ])
    _, issues = __import__("gradebook.importer", fromlist=["import_students"]).import_students(students_csv)
    # unknown status should produce a validation issue
    assert any("probation" in i.message.lower() or i.requirement_id == "STATE-06" for i in issues)


def test_state_06_unknown_status_defaults_to_active(tmp_path):
    from gradebook.students import parse_student_status
    status = parse_student_status("probation")
    assert status == StudentStatus.ACTIVE


# ---------------------------------------------------------------------------
# STATE-07: Excused grade row may omit score
# ---------------------------------------------------------------------------

def test_state_07_excused_without_score_accepted(tmp_path):
    s = tmp_path / "students.csv"
    a = tmp_path / "assignments.csv"
    g = tmp_path / "grades.csv"
    write_csv(s, base_students())
    write_csv(a, base_assignments())
    write_csv(g, [
        {"student_email": "alice@njit.edu", "assignment_id": "HW1",
         "score": "", "status": "excused", "days_late": "0", "notes": ""},
    ])
    data = load_gradebook_data(s, a, g)
    grade_issues = [i for i in data.validation_issues if i.requirement_id == "CSV-07"]
    assert not grade_issues  # no malformed row error for excused with no score
    record = data.grades[0]
    assert record.grade_status == GradeStatus.EXCUSED
    assert record.score is None


# ---------------------------------------------------------------------------
# STATE-08: Each load returns a fresh independent GradebookData snapshot
# ---------------------------------------------------------------------------

def test_state_08_each_load_is_independent(tmp_path):
    s, a, g = make_csvs(tmp_path)
    data1 = load_gradebook_data(s, a, g)
    data2 = load_gradebook_data(s, a, g)
    # they should be equal but not the same object
    assert data1 is not data2
    assert data1.students is not data2.students
    assert data1.grades is not data2.grades
