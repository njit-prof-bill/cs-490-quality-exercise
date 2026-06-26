from __future__ import annotations

from statistics import mean

from .calculator import class_average, class_median, compute_all_students, compute_student_grade
from .models import GradebookData, StudentComputation, StudentStatus


def _format_percent(value: float) -> str:
    return f"{value:.2f}%"

def build_validation_report(data: GradebookData) -> str:
    if not data.validation_issues:
        return "Validation passed with no issues."
    lines = ["Validation issues:"]
    for issue in data.validation_issues:
        where = f" row {issue.row_number}" if issue.row_number is not None else ""
        lines.append(f"- [{issue.requirement_id}] {issue.source}{where}: {issue.message}")
    return "\n".join(lines)


def build_final_grades_report(data: GradebookData) -> str:
    lines = ["Final grades:"]
    for result in sorted(compute_all_students(data), key=lambda item: item.student.email):
        if result.student.status == StudentStatus.WITHDRAWN:
            continue
        lines.append(
            f"{result.student.email} | {result.student.display_name} | {_format_percent(round(result.numeric_grade, 2))} | {result.letter_grade}"
        )
    lines.append(f"Class average: {_format_percent(class_average(data))}")
    lines.append(f"Class median: {_format_percent(class_median(data))}")
    return "\n".join(lines)


def build_student_report(data: GradebookData, student_email: str) -> str:
    student = data.students.get(student_email.lower())
    if student is None:
        return f"Student not found: {student_email}"
    result = compute_student_grade(data, student)
    lines = [
        f"Student report for {student.display_name}",
        f"Email: {student.email}",
        f"Status: {student.status.value}",
        f"Final grade: {_format_percent(result.numeric_grade)} ({result.letter_grade})",
        "Assignments:",
    ]
    latest_records = {record.assignment_id: record for record in data.grade_records_for_student(student.email)}
    for assignment_id, assignment in sorted(data.assignments.items()):
        record = latest_records.get(assignment_id)
        status = "missing" if record is None else record.grade_status.value
        raw = "-" if record is None or record.score is None else f"{record.score:g}"
        lines.append(f"- {assignment_id}: {assignment.name} | {status} | {raw}/{assignment.max_points:g}")
    if result.missing_assignments:
        lines.append("Missing assignments: " + ", ".join(sorted(result.missing_assignments)))
    return "\n".join(lines)


def build_category_report(data: GradebookData) -> str:
    results = compute_all_students(data)
    lines = ["Category report:"]
    categories = data.all_categories()
    for category in categories:
        category_scores: list[float] = []
        weight = 0.0
        for result in results:
            if result.student.status == StudentStatus.WITHDRAWN:
                continue
            for summary in result.category_summaries:
                if summary.category == category:
                    category_scores.append(summary.average_percent)
                    weight = summary.weight
        average = 0.0 if not category_scores else mean(category_scores)
        lines.append(f"{category} | weight={weight:g} | average={_format_percent(average)}")
    return "\n".join(lines)


def build_rank_report(data: GradebookData) -> str:
    results = [result for result in compute_all_students(data) if result.student.status != StudentStatus.WITHDRAWN]
    ranked = sorted(results, key=lambda item: (-item.numeric_grade, item.student.email))
    lines = ["Rankings:"]
    for index, result in enumerate(ranked, start=1):
        lines.append(
            f"{index}. {result.student.email} | {_format_percent(result.numeric_grade)} | {result.letter_grade}"
        )
    return "\n".join(lines)


def build_audit_report(data: GradebookData) -> str:
    lines = ["Audit report:"]
    if not data.validation_issues:
        lines.append("No validation issues detected.")
    else:
        for issue in data.validation_issues:
            if issue.source == "grades":
                continue
            lines.append(f"- [{issue.requirement_id}] {issue.message}")
    duplicate_grade_keys: dict[tuple[str, str], int] = {}
    for record in data.grades:
        key = (record.student_email, record.assignment_id)
        duplicate_grade_keys[key] = duplicate_grade_keys.get(key, 0) + 1
    duplicate_rows = [key for key, count in duplicate_grade_keys.items() if count > 1]
    if duplicate_rows:
        lines.append("Duplicate grade rows:")
        for email, assignment_id in duplicate_rows:
            lines.append(f"- {email} / {assignment_id}")
    return "\n".join(lines)
