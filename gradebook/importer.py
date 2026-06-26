from __future__ import annotations

import csv
from pathlib import Path

from .assignments import build_assignment, find_duplicate_assignments
from .grades import build_grade_record
from .models import Assignment, GradeRecord, GradebookData, Student, ValidationIssue
from .policies import validate_assignment_policy, validate_category_weights, validate_grade_value
from .students import build_student, find_duplicate_students


def _read_csv_rows(path: str | Path, expected_source: str) -> tuple[list[dict[str, str]], list[ValidationIssue]]:
    source = Path(path)
    issues: list[ValidationIssue] = []
    try:
        with source.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                issues.append(
                    ValidationIssue(
                        requirement_id="CSV-06",
                        message=f"{expected_source} CSV is empty.",
                        source=expected_source,
                    )
                )
                return [], issues
            rows = list(reader)
    except FileNotFoundError:
        issues.append(
            ValidationIssue(
                requirement_id="STATE-08",
                message=f"Missing file: {source}",
                source=expected_source,
            )
        )
        return [], issues
    if not rows:
        # CSV-06: header present but no data rows
        issues.append(
            ValidationIssue(
                requirement_id="CSV-06",
                message=f"{expected_source} CSV has a header but no data rows.",
                source=expected_source,
            )
        )
        return [], issues
    return rows, issues


def import_students(path: str | Path) -> tuple[dict[str, Student], list[ValidationIssue]]:
    rows, issues = _read_csv_rows(path, "students")
    students: list[Student] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            student, row_issues = build_student(row, row_number)
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    requirement_id="CSV-07",
                    message=f"Malformed student row: {exc}",
                    row_number=row_number,
                    source="students",
                )
            )
            continue  # CSV-07: skip bad row, continue processing
        issues.extend(row_issues)
        if student is not None:
            students.append(student)
    issues.extend(find_duplicate_students(students))
    return {student.email: student for student in students}, issues


def import_assignments(path: str | Path) -> tuple[dict[str, Assignment], list[ValidationIssue]]:
    rows, issues = _read_csv_rows(path, "assignments")
    assignments: list[Assignment] = []
    for row_number, row in enumerate(rows, start=2):
        assignment, row_issues = build_assignment(row, row_number)
        issues.extend(row_issues)
        if assignment is not None:
            assignments.append(assignment)
            issues.extend(validate_assignment_policy(assignment))
    issues.extend(find_duplicate_assignments(assignments))
    assignment_map = {assignment.assignment_id: assignment for assignment in assignments}
    issues.extend(validate_category_weights(assignment_map))
    return assignment_map, issues


def import_grades(path: str | Path, assignments: dict[str, Assignment]) -> tuple[list[GradeRecord], list[ValidationIssue]]:
    rows, issues = _read_csv_rows(path, "grades")
    grades: list[GradeRecord] = []
    grading_modes = {assignment.assignment_id: assignment.grading_mode for assignment in assignments.values()}
    for row_number, row in enumerate(rows, start=2):
        record, row_issues = build_grade_record(row, row_number, grading_modes)
        issues.extend(row_issues)
        if record is None:
            continue
        assignment = assignments.get(record.assignment_id)
        if assignment is None:
            issues.append(
                ValidationIssue(
                    requirement_id="CSV-08",
                    message=f"Unknown assignment {record.assignment_id}.",
                    row_number=row_number,
                    source="grades",
                )
            )
            continue
        issues.extend(validate_grade_value(record, assignment))
        grades.append(record)
    return grades, issues


def load_gradebook_data(
    students_path: str | Path,
    assignments_path: str | Path,
    grades_path: str | Path,
) -> GradebookData:
    students, student_issues = import_students(students_path)
    assignments, assignment_issues = import_assignments(assignments_path)
    grades, grade_issues = import_grades(grades_path, assignments)
    data = GradebookData(
        students=students,
        assignments=assignments,
        grades=grades,
        validation_issues=[*student_issues, *assignment_issues, *grade_issues],
    )
    data.validation_issues.extend(_cross_validate(data))
    return data


def _cross_validate(data: GradebookData) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for record in data.grades:
        if record.student_email not in data.students:
            issues.append(
                ValidationIssue(
                    requirement_id="CSV-08",
                    message=f"Unknown student {record.student_email}.",
                    row_number=record.source_row,
                    source="grades",
                )
            )
    return issues
