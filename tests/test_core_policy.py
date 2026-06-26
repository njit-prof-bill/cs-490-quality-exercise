from __future__ import annotations

import pytest

from gradebook.calculator import _letter_grade, compute_student_grade
from gradebook.models import Assignment, GradeRecord, GradeStatus, GradebookData, Student


def _student() -> Student:
    return Student(
        student_id="s1",
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
    )


def _assignment(assignment_id: str, category: str, max_points: float, weight: float) -> Assignment:
    return Assignment(
        assignment_id=assignment_id,
        name=assignment_id,
        category=category,
        max_points=max_points,
        weight=weight,
    )


def _grade(assignment_id: str, score: float | None, grade_status: GradeStatus = GradeStatus.RECORDED) -> GradeRecord:
    return GradeRecord(
        student_email="ada@example.com",
        assignment_id=assignment_id,
        score=score,
        grade_status=grade_status,
    )


def _data(assignments: list[Assignment], grades: list[GradeRecord]) -> GradebookData:
    student = _student()
    return GradebookData(
        students={student.email: student},
        assignments={assignment.assignment_id: assignment for assignment in assignments},
        grades=grades,
    )


def test_core_01() -> None:
    data = _data(
        assignments=[
            _assignment("HW1", "HOMEWORK", 50, 0.60),
            _assignment("HW2", "HOMEWORK", 150, 0.60),
            _assignment("EX1", "EXAM", 100, 0.40),
        ],
        grades=[
            _grade("HW1", 50),
            _grade("HW2", 75),
            _grade("EX1", 100),
        ],
    )

    result = compute_student_grade(data, _student())

    assert result.numeric_grade == pytest.approx(77.5)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (93.0, "A"),
        (92.99, "A-"),
        (90.0, "A-"),
        (89.99, "B+"),
        (60.0, "D-"),
        (59.99, "F"),
    ],
)
def test_core_02(score: float, expected: str) -> None:
    assert _letter_grade(score) == expected


def test_core_03() -> None:
    data = _data(
        assignments=[
            _assignment("HW1", "HOMEWORK", 100, 1.0),
            _assignment("HW2", "HOMEWORK", 100, 1.0),
        ],
        grades=[_grade("HW1", 50)],
    )

    result = compute_student_grade(data, _student())

    assert result.numeric_grade == pytest.approx(25.0)
    assert result.missing_assignments == ["HW2"]


def test_core_04() -> None:
    data = _data(
        assignments=[
            _assignment("HW1", "HOMEWORK", 100, 1.0),
            _assignment("HW2", "HOMEWORK", 100, 1.0),
        ],
        grades=[
            _grade("HW1", 50),
            _grade("HW2", None, GradeStatus.EXCUSED),
        ],
    )

    result = compute_student_grade(data, _student())

    assert result.numeric_grade == pytest.approx(50.0)
    assert result.missing_assignments == []


def test_core_08() -> None:
    data = _data(
        assignments=[_assignment("HW1", "HOMEWORK", 100, 1.0)],
        grades=[
            _grade("HW1", 10),
            _grade("HW1", 90),
        ],
    )

    result = compute_student_grade(data, _student())

    assert result.numeric_grade == pytest.approx(90.0)