from __future__ import annotations

from .models import Student, StudentStatus, ValidationIssue


VALID_STATUSES = {status.value for status in StudentStatus}


def normalize_email(email: str) -> str:
    return email.strip().lower()


def parse_student_status(value: str) -> StudentStatus:
    normalized = value.strip().lower() or StudentStatus.ACTIVE.value
    if normalized not in VALID_STATUSES:
        return StudentStatus.ACTIVE
    return StudentStatus(normalized)


def build_student(row: dict[str, str], row_number: int) -> tuple[Student | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    student_id = row.get("student_id", "").strip()
    first_name = row.get("first_name", "").strip()
    last_name = row.get("last_name", "").strip()
    email = row.get("email", "")
    section = row.get("section", "").strip() or "main"
    if not student_id:
        issues.append(
            ValidationIssue(
                requirement_id="CSV-07",
                message="Student row missing student_id.",
                row_number=row_number,
                source="students",
            )
        )
    if not email:
        issues.append(
            ValidationIssue(
                requirement_id="CSV-07",
                message="Student row missing email.",
                row_number=row_number,
                source="students",
            )
        )
    if issues:
        return None, issues
    raw_status = row.get("status", "").strip().lower()
    parsed_status = parse_student_status(raw_status)
    valid_statuses = {s.value for s in StudentStatus}
    if raw_status and raw_status not in valid_statuses:
        issues.append(
            ValidationIssue(
                requirement_id="STATE-06",
                message=f"Unknown student status '{raw_status}', defaulting to active.",
                row_number=row_number,
                source="students",
            )
        )
    student = Student(
        student_id=student_id,
        first_name=first_name,
        last_name=last_name,
        email=normalize_email(email),
        status=parsed_status,
        section=section,
    )
    return student, issues


def find_duplicate_students(students: list[Student]) -> list[ValidationIssue]:
    seen: set[str] = set()
    issues: list[ValidationIssue] = []
    for index, student in enumerate(students, start=2):
        if student.email in seen:
            issues.append(
                ValidationIssue(
                    requirement_id="CSV-02",
                    message=f"Duplicate student email found: {student.email}",
                    row_number=index,
                    source="students",
                )
            )
        seen.add(student.email)
    return issues
