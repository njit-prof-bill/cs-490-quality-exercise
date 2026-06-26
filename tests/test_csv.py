"""
Level 2 CSV and Import Tests
Tests named after requirement IDs from grading-policy.md
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

import pytest

from gradebook.assignments import build_assignment, find_duplicate_assignments
from gradebook.grades import build_grade_record, parse_grade_value
from gradebook.importer import import_assignments, import_grades, import_students, load_gradebook_data
from gradebook.models import Assignment, GradeRecord, GradeStatus, Student, ValidationIssue
from gradebook.policies import validate_grade_value
from gradebook.students import build_student, find_duplicate_students, normalize_email


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def write_csv_header_only(path: Path, fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def make_assignment(
    assignment_id: str = "HW1",
    category: str = "HOMEWORK",
    max_points: float = 100.0,
    weight: float = 1.0,
    is_extra_credit: bool = False,
) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        name=assignment_id,
        category=category,
        max_points=max_points,
        weight=weight,
        is_extra_credit=is_extra_credit,
    )


def make_grade_record(
    email: str = "test@njit.edu",
    assignment_id: str = "HW1",
    score: float = 80.0,
    status: GradeStatus = GradeStatus.RECORDED,
) -> GradeRecord:
    return GradeRecord(
        student_email=email,
        assignment_id=assignment_id,
        score=score,
        grade_status=status,
        source_row=2,
    )


# ---------------------------------------------------------------------------
# CSV-01: Email normalization (trim + lowercase)
# ---------------------------------------------------------------------------

def test_csv_01_email_lowercased():
    assert normalize_email("Alice@NJIT.EDU") == "alice@njit.edu"


def test_csv_01_email_whitespace_trimmed():
    row = {
        "student_id": "S1", "first_name": "Alice", "last_name": "A",
        "email": "  Alice@NJIT.EDU  ", "status": "active", "section": "main"
    }
    student, issues = build_student(row, 2)
    assert student is not None
    assert student.email == "alice@njit.edu"


def test_csv_01_email_normalized_on_import(tmp_path):
    students_csv = tmp_path / "students.csv"
    write_csv(students_csv, [
        {"student_id": "S1", "first_name": "Alice", "last_name": "A",
         "email": "  ALICE@NJIT.EDU  ", "status": "active", "section": "main"}
    ])
    students, _ = import_students(students_csv)
    assert "alice@njit.edu" in students


# ---------------------------------------------------------------------------
# CSV-02: Duplicate students detected by normalized email
# ---------------------------------------------------------------------------

def test_csv_02_duplicate_student_reported():
    students = [
        Student("S1", "Alice", "A", "alice@njit.edu"),
        Student("S2", "Alice", "B", "alice@njit.edu"),
    ]
    issues = find_duplicate_students(students)
    assert any(i.requirement_id == "CSV-02" for i in issues)


def test_csv_02_duplicate_detected_after_normalization(tmp_path):
    students_csv = tmp_path / "students.csv"
    write_csv(students_csv, [
        {"student_id": "S1", "first_name": "Alice", "last_name": "A",
         "email": "alice@njit.edu", "status": "active", "section": "main"},
        {"student_id": "S2", "first_name": "Alice", "last_name": "B",
         "email": "ALICE@NJIT.EDU", "status": "active", "section": "main"},
    ])
    _, issues = import_students(students_csv)
    assert any(i.requirement_id == "CSV-02" for i in issues)


# ---------------------------------------------------------------------------
# CSV-03: Duplicate assignment IDs reported
# ---------------------------------------------------------------------------

def test_csv_03_duplicate_assignment_id_reported():
    assignments = [
        make_assignment("HW1"),
        make_assignment("HW1"),
    ]
    issues = find_duplicate_assignments(assignments)
    assert any(i.requirement_id == "CSV-03" for i in issues)


# ---------------------------------------------------------------------------
# CSV-04: Score > max_points invalid unless extra credit
# ---------------------------------------------------------------------------

def test_csv_04_score_over_max_is_invalid():
    assignment = make_assignment(max_points=100.0)
    record = make_grade_record(score=105.0)
    issues = validate_grade_value(record, assignment)
    assert any(i.requirement_id == "CSV-04" for i in issues)


def test_csv_04_score_over_max_allowed_for_extra_credit():
    assignment = make_assignment(category="EXTRA_CREDIT", max_points=10.0, weight=0.0, is_extra_credit=True)
    record = make_grade_record(score=15.0)
    issues = validate_grade_value(record, assignment)
    assert not any(i.requirement_id == "CSV-04" for i in issues)


def test_csv_04_score_equal_to_max_is_valid():
    assignment = make_assignment(max_points=100.0)
    record = make_grade_record(score=100.0)
    issues = validate_grade_value(record, assignment)
    assert not any(i.requirement_id == "CSV-04" for i in issues)


# ---------------------------------------------------------------------------
# CSV-05: Negative scores are invalid
# ---------------------------------------------------------------------------

def test_csv_05_negative_score_is_invalid():
    assignment = make_assignment(max_points=100.0)
    record = make_grade_record(score=-1.0)
    issues = validate_grade_value(record, assignment)
    assert any(i.requirement_id == "CSV-05" for i in issues)


def test_csv_05_zero_score_is_valid():
    assignment = make_assignment(max_points=100.0)
    record = make_grade_record(score=0.0)
    issues = validate_grade_value(record, assignment)
    assert not any(i.requirement_id == "CSV-05" for i in issues)


# ---------------------------------------------------------------------------
# CSV-06: Header-only CSV produces a validation issue
# ---------------------------------------------------------------------------

def test_csv_06_empty_students_file_produces_issue(tmp_path):
    students_csv = tmp_path / "students.csv"
    write_csv_header_only(students_csv, ["student_id", "first_name", "last_name", "email", "status"])
    _, issues = import_students(students_csv)
    assert any(i.requirement_id == "CSV-06" for i in issues)


def test_csv_06_empty_assignments_file_produces_issue(tmp_path):
    assignments_csv = tmp_path / "assignments.csv"
    write_csv_header_only(assignments_csv, ["assignment_id", "name", "category", "max_points", "weight"])
    _, issues = import_assignments(assignments_csv)
    assert any(i.requirement_id == "CSV-06" for i in issues)


# ---------------------------------------------------------------------------
# CSV-07: Malformed rows reported, processing continues
# ---------------------------------------------------------------------------

def test_csv_07_malformed_student_row_continues(tmp_path):
    students_csv = tmp_path / "students.csv"
    write_csv(students_csv, [
        {"student_id": "", "first_name": "Bad", "last_name": "Row",
         "email": "", "status": "active", "section": "main"},
        {"student_id": "S2", "first_name": "Good", "last_name": "Student",
         "email": "good@njit.edu", "status": "active", "section": "main"},
    ])
    students, issues = import_students(students_csv)
    assert any(i.requirement_id == "CSV-07" for i in issues)
    assert "good@njit.edu" in students  # processing continued


def test_csv_07_malformed_grade_score_reported():
    row = {"student_email": "a@njit.edu", "assignment_id": "HW1",
           "score": "notanumber", "status": "recorded", "days_late": "0", "notes": ""}
    _, issues = build_grade_record(row, 2, {"HW1": "points"})
    assert any(i.requirement_id == "CSV-07" for i in issues)


# ---------------------------------------------------------------------------
# CSV-08: Unknown student/assignment in grades reported
# ---------------------------------------------------------------------------

def test_csv_08_unknown_assignment_in_grades(tmp_path):
    students_csv = tmp_path / "students.csv"
    assignments_csv = tmp_path / "assignments.csv"
    grades_csv = tmp_path / "grades.csv"

    write_csv(students_csv, [
        {"student_id": "S1", "first_name": "Alice", "last_name": "A",
         "email": "alice@njit.edu", "status": "active", "section": "main"}
    ])
    write_csv(assignments_csv, [
        {"assignment_id": "HW1", "name": "HW1", "category": "HOMEWORK",
         "max_points": "100", "weight": "1.0", "due_date": "", "drop_lowest_eligible": "",
         "is_extra_credit": "", "late_penalty_per_day": "0.10", "min_score_floor": "", "grading_mode": "points"}
    ])
    write_csv(grades_csv, [
        {"student_email": "alice@njit.edu", "assignment_id": "UNKNOWN_ASSIGNMENT",
         "score": "80", "status": "recorded", "days_late": "0", "notes": ""}
    ])

    data = load_gradebook_data(students_csv, assignments_csv, grades_csv)
    assert any(i.requirement_id == "CSV-08" for i in data.validation_issues)


def test_csv_08_unknown_student_in_grades(tmp_path):
    students_csv = tmp_path / "students.csv"
    assignments_csv = tmp_path / "assignments.csv"
    grades_csv = tmp_path / "grades.csv"

    write_csv(students_csv, [
        {"student_id": "S1", "first_name": "Alice", "last_name": "A",
         "email": "alice@njit.edu", "status": "active", "section": "main"}
    ])
    write_csv(assignments_csv, [
        {"assignment_id": "HW1", "name": "HW1", "category": "HOMEWORK",
         "max_points": "100", "weight": "1.0", "due_date": "", "drop_lowest_eligible": "",
         "is_extra_credit": "", "late_penalty_per_day": "0.10", "min_score_floor": "", "grading_mode": "points"}
    ])
    write_csv(grades_csv, [
        {"student_email": "nobody@njit.edu", "assignment_id": "HW1",
         "score": "80", "status": "recorded", "days_late": "0", "notes": ""}
    ])

    data = load_gradebook_data(students_csv, assignments_csv, grades_csv)
    assert any(i.requirement_id == "CSV-08" for i in data.validation_issues)
