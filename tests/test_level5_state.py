"""Level 5 – State and workflow tests (STATE-01, STATE-04 through STATE-08)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gradebook.cli import main
from gradebook.grades import build_grade_record
from gradebook.importer import load_gradebook_data
from gradebook.models import GradeStatus
from gradebook.reports import build_audit_report
from gradebook.storage import InMemoryStorage
from gradebook.students import build_student


# ---------------------------------------------------------------------------
# STATE-01: repeated loads into InMemoryStorage must not duplicate data
# ---------------------------------------------------------------------------

def test_state_01_repeated_load_same_files_no_duplicate_grades() -> None:
    """Loading the same files twice into InMemoryStorage must not duplicate grades (STATE-01)."""
    storage = InMemoryStorage()
    result1 = storage.load(
        "sample_data/students.csv",
        "sample_data/assignments.csv",
        "sample_data/grades.csv",
    )
    grade_count_after_first = len(result1.grades)

    result2 = storage.load(
        "sample_data/students.csv",
        "sample_data/assignments.csv",
        "sample_data/grades.csv",
    )
    assert len(result2.grades) == grade_count_after_first


def test_state_01_repeated_load_same_files_no_duplicate_issues() -> None:
    """Loading the same files twice must not duplicate validation issues (STATE-01)."""
    storage = InMemoryStorage()
    result1 = storage.load(
        "sample_data/students.csv",
        "sample_data/assignments.csv",
        "sample_data/grades.csv",
    )
    issue_count_after_first = len(result1.validation_issues)

    result2 = storage.load(
        "sample_data/students.csv",
        "sample_data/assignments.csv",
        "sample_data/grades.csv",
    )
    assert len(result2.validation_issues) == issue_count_after_first


# ---------------------------------------------------------------------------
# STATE-04: validate command exits non-zero when issues are present, zero when clean
# ---------------------------------------------------------------------------

def test_state_04_validate_exits_nonzero_when_issues_present(tmp_path: Path) -> None:
    """The validate command must exit with a non-zero code when validation issues exist (STATE-04)."""
    # Students CSV with a duplicate email → guaranteed CSV-02 issue
    students = tmp_path / "students.csv"
    students.write_text(
        textwrap.dedent("""\
        student_id,first_name,last_name,email,status,section
        S1,Alice,Smith,alice@x.com,active,A
        S2,Alice,Dup,alice@x.com,active,A
        """)
    )
    assignments = tmp_path / "assignments.csv"
    assignments.write_text(
        "assignment_id,name,category,max_points,weight,due_date,"
        "drop_lowest_eligible,is_extra_credit,late_penalty_per_day,"
        "min_score_floor,grading_mode\n"
        "HW1,HW 1,HOMEWORK,100,1.0,,,false,0.10,,points\n"
    )
    grades = tmp_path / "grades.csv"
    grades.write_text("student_email,assignment_id,score,status,days_late,notes\n")

    exit_code = main(["validate", str(students), str(assignments), str(grades)])
    assert exit_code != 0


def test_state_04_validate_exits_zero_when_no_issues(tmp_path: Path) -> None:
    """The validate command must exit with 0 when there are no validation issues (STATE-04)."""
    students = tmp_path / "students.csv"
    students.write_text(
        textwrap.dedent("""\
        student_id,first_name,last_name,email,status,section
        S1,Alice,Smith,alice@x.com,active,A
        """)
    )
    assignments = tmp_path / "assignments.csv"
    assignments.write_text(
        "assignment_id,name,category,max_points,weight,due_date,"
        "drop_lowest_eligible,is_extra_credit,late_penalty_per_day,"
        "min_score_floor,grading_mode\n"
        "HW1,HW 1,HOMEWORK,100,1.0,,,false,0.10,,points\n"
    )
    grades = tmp_path / "grades.csv"
    grades.write_text(
        textwrap.dedent("""\
        student_email,assignment_id,score,status,days_late,notes
        alice@x.com,HW1,80,recorded,0,
        """)
    )

    exit_code = main(["validate", str(students), str(assignments), str(grades)])
    assert exit_code == 0


# ---------------------------------------------------------------------------
# STATE-05: audit report includes invalid grade records
# ---------------------------------------------------------------------------

def test_state_05_audit_includes_grade_validation_issues(tmp_path: Path) -> None:
    """Audit report must include invalid grade records (e.g. unknown student) (STATE-05)."""
    students = tmp_path / "students.csv"
    students.write_text(
        textwrap.dedent("""\
        student_id,first_name,last_name,email,status,section
        S1,Alice,Smith,alice@x.com,active,A
        """)
    )
    assignments = tmp_path / "assignments.csv"
    assignments.write_text(
        "assignment_id,name,category,max_points,weight,due_date,"
        "drop_lowest_eligible,is_extra_credit,late_penalty_per_day,"
        "min_score_floor,grading_mode\n"
        "HW1,HW 1,HOMEWORK,100,1.0,,,false,0.10,,points\n"
    )
    grades = tmp_path / "grades.csv"
    grades.write_text(
        textwrap.dedent("""\
        student_email,assignment_id,score,status,days_late,notes
        ghost@x.com,HW1,80,recorded,0,unknown student
        """)
    )

    data = load_gradebook_data(students, assignments, grades)
    report = build_audit_report(data)
    # The CSV-08 issue (unknown student in grade row) must appear in the audit
    assert "CSV-08" in report


# ---------------------------------------------------------------------------
# STATE-06: unknown student status produces a validation issue and defaults to active
# ---------------------------------------------------------------------------

def test_state_06_unknown_status_produces_validation_issue() -> None:
    """An unrecognised status value must produce a STATE-06 validation issue (STATE-06)."""
    row = {
        "student_id": "S1",
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@x.com",
        "status": "zombie",  # not a valid status
        "section": "A",
    }
    student, issues = build_student(row, row_number=2)
    req_ids = [i.requirement_id for i in issues]
    assert "STATE-06" in req_ids


def test_state_06_unknown_status_defaults_to_active() -> None:
    """An unrecognised status must default the student to active status (STATE-06)."""
    from gradebook.models import StudentStatus

    row = {
        "student_id": "S1",
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@x.com",
        "status": "zombie",
        "section": "A",
    }
    student, _ = build_student(row, row_number=2)
    assert student is not None
    assert student.status == StudentStatus.ACTIVE


# ---------------------------------------------------------------------------
# STATE-07: excused grade row may omit the numeric score field
# ---------------------------------------------------------------------------

def test_state_07_excused_row_without_score_is_accepted() -> None:
    """An excused grade row with no score value must import without error (STATE-07)."""
    row = {
        "student_email": "alice@x.com",
        "assignment_id": "HW1",
        "score": "",          # omitted
        "status": "excused",
        "days_late": "0",
        "notes": "",
    }
    record, issues = build_grade_record(row, row_number=2, grading_mode_lookup={"HW1": "points"})
    assert record is not None
    assert record.grade_status == GradeStatus.EXCUSED
    assert record.score is None
    assert not issues


# ---------------------------------------------------------------------------
# STATE-08: each load_gradebook_data call returns an independent fresh snapshot
# ---------------------------------------------------------------------------

def test_state_08_each_load_returns_independent_snapshot() -> None:
    """Mutating one GradebookData snapshot must not affect a separately loaded snapshot (STATE-08)."""
    data1 = load_gradebook_data(
        "sample_data/students.csv",
        "sample_data/assignments.csv",
        "sample_data/grades.csv",
    )
    data2 = load_gradebook_data(
        "sample_data/students.csv",
        "sample_data/assignments.csv",
        "sample_data/grades.csv",
    )
    original_count = len(data2.grades)
    # Mutate data1 without affecting data2
    data1.grades.clear()
    assert len(data2.grades) == original_count
