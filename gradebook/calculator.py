from __future__ import annotations

from collections import defaultdict
from statistics import mean

from .models import Assignment, CategorySummary, GradeRecord, GradeStatus, GradebookData, Student, StudentComputation, StudentStatus
from .policies import apply_late_policy


def _letter_grade(score: float) -> str:
    if score >= 93.0:
        return "A"
    if score >= 90.0:
        return "A-"
    if score >= 87.0:
        return "B+"
    if score >= 83.0:
        return "B"
    if score >= 80.0:
        return "B-"
    if score >= 77.0:
        return "C+"
    if score >= 73.0:
        return "C"
    if score >= 70.0:
        return "C-"
    if score >= 67.0:
        return "D+"
    if score >= 63.0:
        return "D"
    if score >= 60.0:
        return "D-"
    return "F"


def _group_records_by_student(grades: list[GradeRecord]) -> dict[str, list[GradeRecord]]:
    grouped: dict[str, list[GradeRecord]] = defaultdict(list)
    for record in grades:
        grouped[record.student_email].append(record)
    return grouped


def _latest_grade_records(records: list[GradeRecord]) -> dict[str, GradeRecord]:
    latest: dict[str, GradeRecord] = {}
    for record in records:
        latest[record.assignment_id] = record
    return latest


def _category_assignment_groups(assignments: dict[str, Assignment]) -> dict[str, list[Assignment]]:
    grouped: dict[str, list[Assignment]] = defaultdict(list)
    for assignment in assignments.values():
        grouped[assignment.category].append(assignment)
    return grouped


def _assignment_percent(record: GradeRecord | None, assignment: Assignment) -> tuple[float, float, bool]:
    if record is None:
        return 0.0, assignment.max_points, True
    if record.grade_status == GradeStatus.EXCUSED:
        return 0.0, 0.0, False
    adjusted = apply_late_policy(record, assignment)
    if adjusted is None:
        return 0.0, assignment.max_points, True
    return adjusted, assignment.max_points, False


def _drop_lowest_if_needed(category: str, assignments: list[Assignment], values: list[tuple[Assignment, float, float]]) -> list[tuple[Assignment, float, float]]:
    if category != "QUIZ":
        return values
    # CORE-05: only drop when at least 4 non-excused quiz scores (possible > 0 means not excused)
    non_excused = [v for v in values if v[2] > 0]
    if len(non_excused) < 4:
        return values
    ordered = sorted(values, key=lambda item: (item[1] / item[2]) if item[2] else 1.0)
    return ordered[1:]


def compute_student_grade(data: GradebookData, student: Student) -> StudentComputation:
    records = _group_records_by_student(data.grades).get(student.email, [])
    latest_records = _latest_grade_records(records)
    category_assignments = _category_assignment_groups(data.assignments)
    category_summaries: list[CategorySummary] = []
    missing_assignments: list[str] = []
    total = 0.0
    for category, assignments in sorted(category_assignments.items()):
        category_values: list[tuple[Assignment, float, float]] = []
        for assignment in assignments:
            record = latest_records.get(assignment.assignment_id)
            earned, possible, is_missing = _assignment_percent(record, assignment)
            if is_missing:
                missing_assignments.append(assignment.assignment_id)
            category_values.append((assignment, earned, possible))
        category_values = _drop_lowest_if_needed(category, assignments, category_values)
        earned_points = sum(value[1] for value in category_values)
        possible_points = sum(value[2] for value in category_values)
        average_percent = 0.0 if possible_points == 0 else (earned_points / possible_points) * 100
        weight = assignments[0].weight if assignments else 0.0
        category_summaries.append(
            CategorySummary(
                category=category,
                weight=weight,
                earned_points=earned_points,
                possible_points=possible_points,
                average_percent=average_percent,
            )
        )
        if category != "EXTRA_CREDIT":
            total += average_percent * weight
        else:
            # CORE-06: extra credit adds raw earned points, capped at 100 after all categories
            total += earned_points
    numeric_grade = min(total, 100.0)  # CORE-06: cap at 100
    return StudentComputation(
        student=student,
        numeric_grade=numeric_grade,
        letter_grade=_letter_grade(numeric_grade),
        category_summaries=category_summaries,
        missing_assignments=missing_assignments,
    )


def compute_all_students(data: GradebookData) -> list[StudentComputation]:
    results: list[StudentComputation] = []
    for student in data.students.values():
        if student.status == StudentStatus.WITHDRAWN:
            results.append(compute_student_grade(data, student))
            continue
        results.append(compute_student_grade(data, student))
    return results


def numeric_grades_for_active_students(data: GradebookData) -> list[float]:
    values: list[float] = []
    for result in compute_all_students(data):
        if result.student.status == StudentStatus.WITHDRAWN:
            continue
        values.append(result.numeric_grade)
    return values


def class_average(data: GradebookData) -> float:
    grades = numeric_grades_for_active_students(data)
    return 0.0 if not grades else mean(grades)


def class_median(data: GradebookData) -> float:
    grades = sorted(numeric_grades_for_active_students(data))
    if not grades:
        return 0.0
    midpoint = len(grades) // 2
    if len(grades) % 2 == 1:
        return grades[midpoint]
    # REPORT-05: even count → mean of two middle grades
    return (grades[midpoint - 1] + grades[midpoint]) / 2
