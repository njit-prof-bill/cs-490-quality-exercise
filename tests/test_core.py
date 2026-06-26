"""
Level 1 Core Grading Tests
Tests named after requirement IDs from grading-policy.md
"""
from __future__ import annotations

import pytest
from gradebook.calculator import _letter_grade, compute_student_grade
from gradebook.models import (
    Assignment,
    GradebookData,
    GradeRecord,
    GradeStatus,
    Student,
    StudentStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_student(email: str = "test@njit.edu", status: StudentStatus = StudentStatus.ACTIVE) -> Student:
    return Student(
        student_id="S001",
        first_name="Test",
        last_name="Student",
        email=email,
        status=status,
    )


def make_assignment(
    assignment_id: str,
    category: str,
    max_points: float,
    weight: float,
    *,
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


def make_grade(email: str, assignment_id: str, score: float, *, source_row: int = 2) -> GradeRecord:
    return GradeRecord(
        student_email=email,
        assignment_id=assignment_id,
        score=score,
        grade_status=GradeStatus.RECORDED,
        source_row=source_row,
    )


def make_excused(email: str, assignment_id: str, *, source_row: int = 2) -> GradeRecord:
    return GradeRecord(
        student_email=email,
        assignment_id=assignment_id,
        score=None,
        grade_status=GradeStatus.EXCUSED,
        source_row=source_row,
    )


def simple_gradebook(student: Student, assignments: list[Assignment], grades: list[GradeRecord]) -> GradebookData:
    return GradebookData(
        students={student.email: student},
        assignments={a.assignment_id: a for a in assignments},
        grades=grades,
    )


# ---------------------------------------------------------------------------
# CORE-01: Weighted category averages
# ---------------------------------------------------------------------------

def test_core_01_weighted_average_single_category():
    """70/100 on a single category with weight=1.0 -> 70.0 numeric grade."""
    student = make_student()
    assignments = [make_assignment("HW1", "HOMEWORK", 100.0, 1.0)]
    grades = [make_grade(student.email, "HW1", 70.0)]
    data = simple_gradebook(student, assignments, grades)
    result = compute_student_grade(data, student)
    assert result.numeric_grade == pytest.approx(70.0)


def test_core_01_weighted_average_two_categories():
    """HOMEWORK 80/100 weight=0.5, EXAM 60/100 weight=0.5 -> (80*0.5 + 60*0.5) = 70.0"""
    student = make_student()
    assignments = [
        make_assignment("HW1", "HOMEWORK", 100.0, 0.5),
        make_assignment("E1",  "EXAM",     100.0, 0.5),
    ]
    grades = [
        make_grade(student.email, "HW1", 80.0),
        make_grade(student.email, "E1",  60.0),
    ]
    data = simple_gradebook(student, assignments, grades)
    result = compute_student_grade(data, student)
    assert result.numeric_grade == pytest.approx(70.0)


def test_core_01_points_summed_within_category():
    """Within a category, points are summed: 30+40=70 earned out of 50+50=100 -> 70%."""
    student = make_student()
    assignments = [
        make_assignment("HW1", "HOMEWORK", 50.0, 1.0),
        make_assignment("HW2", "HOMEWORK", 50.0, 1.0),
    ]
    grades = [
        make_grade(student.email, "HW1", 30.0),
        make_grade(student.email, "HW2", 40.0),
    ]
    data = simple_gradebook(student, assignments, grades)
    result = compute_student_grade(data, student)
    assert result.numeric_grade == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# CORE-02: Letter grade boundaries (no upward rounding)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score,expected", [
    (100.0, "A"),
    (93.0,  "A"),
    (92.99, "A-"),
    (90.0,  "A-"),
    (89.99, "B+"),
    (87.0,  "B+"),
    (86.99, "B"),
    (83.0,  "B"),
    (82.99, "B-"),
    (80.0,  "B-"),
    (79.99, "C+"),
    (77.0,  "C+"),
    (76.99, "C"),
    (73.0,  "C"),
    (72.99, "C-"),
    (70.0,  "C-"),
    (69.99, "D+"),
    (67.0,  "D+"),
    (66.99, "D"),
    (63.0,  "D"),
    (62.99, "D-"),
    (60.0,  "D-"),
    (59.99, "F"),
    (0.0,   "F"),
])
def test_core_02_letter_grade_boundary(score: float, expected: str):
    assert _letter_grade(score) == expected


# ---------------------------------------------------------------------------
# CORE-03: Missing grade counts as zero
# ---------------------------------------------------------------------------

def test_core_03_missing_grade_counts_as_zero():
    """No grade record for an assignment -> 0 earned points."""
    student = make_student()
    assignments = [make_assignment("HW1", "HOMEWORK", 100.0, 1.0)]
    data = simple_gradebook(student, assignments, grades=[])
    result = compute_student_grade(data, student)
    assert result.numeric_grade == pytest.approx(0.0)
    assert "HW1" in result.missing_assignments


# ---------------------------------------------------------------------------
# CORE-04: Excused assignments excluded from earned and possible points
# ---------------------------------------------------------------------------

def test_core_04_excused_excluded_from_possible_points():
    """Excused assignment should not affect the grade at all."""
    student = make_student()
    assignments = [
        make_assignment("HW1", "HOMEWORK", 100.0, 1.0),
        make_assignment("HW2", "HOMEWORK", 100.0, 1.0),
    ]
    grades = [
        make_grade(student.email, "HW1", 80.0),
        make_excused(student.email, "HW2"),
    ]
    data = simple_gradebook(student, assignments, grades)
    result = compute_student_grade(data, student)
    # Only HW1 counts: 80/100 = 80%
    assert result.numeric_grade == pytest.approx(80.0)


def test_core_04_all_excused_gives_no_penalty():
    """All assignments excused -> no grade penalty (grade should not be 0)."""
    student = make_student()
    assignments = [make_assignment("HW1", "HOMEWORK", 100.0, 1.0)]
    grades = [make_excused(student.email, "HW1")]
    data = simple_gradebook(student, assignments, grades)
    result = compute_student_grade(data, student)
    # Possible points = 0, so average_percent should be 0 (or handled gracefully), not a crash
    # and should NOT count as a missing assignment
    assert "HW1" not in result.missing_assignments


# ---------------------------------------------------------------------------
# CORE-05: Drop lowest quiz only when >= 4 non-excused quiz scores
# ---------------------------------------------------------------------------

def make_quiz_gradebook(student: Student, scores: list[float]) -> GradebookData:
    assignments = [
        make_assignment(f"Q{i+1}", "QUIZ", 10.0, 1.0)
        for i in range(len(scores))
    ]
    grades = [
        make_grade(student.email, f"Q{i+1}", s)
        for i, s in enumerate(scores)
    ]
    return simple_gradebook(student, assignments, grades)


def test_core_05_no_drop_with_three_quizzes():
    """3 quizzes: lowest NOT dropped. 2+8+10=20/30 = 66.67%"""
    student = make_student()
    data = make_quiz_gradebook(student, [2.0, 8.0, 10.0])
    result = compute_student_grade(data, student)
    assert result.numeric_grade == pytest.approx(66.67, abs=0.01)


def test_core_05_drop_lowest_with_four_quizzes():
    """4 quizzes: lowest dropped. scores=[2,8,9,10] -> drop 2 -> 8+9+10=27/30 = 90%"""
    student = make_student()
    data = make_quiz_gradebook(student, [2.0, 8.0, 9.0, 10.0])
    result = compute_student_grade(data, student)
    assert result.numeric_grade == pytest.approx(90.0, abs=0.01)


def test_core_05_drop_lowest_with_five_quizzes():
    """5 quizzes: lowest still dropped (only one drop). [2,7,8,9,10] -> drop 2 -> 34/40 = 85%"""
    student = make_student()
    data = make_quiz_gradebook(student, [2.0, 7.0, 8.0, 9.0, 10.0])
    result = compute_student_grade(data, student)
    assert result.numeric_grade == pytest.approx(85.0, abs=0.01)


# ---------------------------------------------------------------------------
# CORE-06: Extra credit can raise grade but never above 100
# ---------------------------------------------------------------------------

def test_core_06_extra_credit_raises_grade():
    """Base grade 80%, extra credit adds points -> grade > 80%."""
    student = make_student()
    assignments = [
        make_assignment("HW1", "HOMEWORK",     100.0, 1.0),
        make_assignment("EC1", "EXTRA_CREDIT",  10.0, 0.0, is_extra_credit=True),
    ]
    grades = [
        make_grade(student.email, "HW1", 80.0),
        make_grade(student.email, "EC1", 10.0),
    ]
    data = simple_gradebook(student, assignments, grades)
    result = compute_student_grade(data, student)
    assert result.numeric_grade > 80.0


def test_core_06_extra_credit_capped_at_100():
    """Grade cannot exceed 100 even with extra credit."""
    student = make_student()
    assignments = [
        make_assignment("HW1", "HOMEWORK",     100.0, 1.0),
        make_assignment("EC1", "EXTRA_CREDIT",  50.0, 0.0, is_extra_credit=True),
    ]
    grades = [
        make_grade(student.email, "HW1", 100.0),
        make_grade(student.email, "EC1",  50.0),
    ]
    data = simple_gradebook(student, assignments, grades)
    result = compute_student_grade(data, student)
    assert result.numeric_grade <= 100.0


# ---------------------------------------------------------------------------
# CORE-08: Most recent grade row wins
# ---------------------------------------------------------------------------

def test_core_08_latest_grade_replaces_earlier():
    """Two grade rows for same student+assignment: last one in the list wins."""
    student = make_student()
    assignments = [make_assignment("HW1", "HOMEWORK", 100.0, 1.0)]
    grades = [
        make_grade(student.email, "HW1", 50.0, source_row=2),
        make_grade(student.email, "HW1", 90.0, source_row=3),  # most recent
    ]
    data = simple_gradebook(student, assignments, grades)
    result = compute_student_grade(data, student)
    assert result.numeric_grade == pytest.approx(90.0)