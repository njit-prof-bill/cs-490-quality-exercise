from __future__ import annotations

import argparse
from typing import Sequence

from .audit import audit_gradebook
from .importer import load_gradebook_data
from .reports import (
    build_category_report,
    build_final_grades_report,
    build_rank_report,
    build_student_report,
    build_validation_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gradebook", description="Gradebook from Hell"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = _add_three_file_command(subparsers, "validate", "Validate CSV files.")
    validate.set_defaults(handler=_handle_validate)

    final_grades = _add_three_file_command(
        subparsers, "final-grades", "Compute final grades."
    )
    final_grades.set_defaults(handler=_handle_final_grades)

    student_report = _add_three_file_command(
        subparsers, "student-report", "Show one student report."
    )
    student_report.add_argument("--student", required=True, help="Student email")
    student_report.set_defaults(handler=_handle_student_report)

    category_report = _add_three_file_command(
        subparsers, "category-report", "Show category summary."
    )
    category_report.set_defaults(handler=_handle_category_report)

    rank = _add_three_file_command(subparsers, "rank", "Show rankings.")
    rank.set_defaults(handler=_handle_rank)

    audit = _add_three_file_command(subparsers, "audit", "Show audit details.")
    audit.set_defaults(handler=_handle_audit)
    return parser


def _add_three_file_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    parser.add_argument("students_csv")
    parser.add_argument("assignments_csv")
    parser.add_argument("grades_csv")
    return parser


def _load(args: argparse.Namespace):
    return load_gradebook_data(args.students_csv, args.assignments_csv, args.grades_csv)


def _handle_validate(args: argparse.Namespace) -> int:
    data = _load(args)
    print(build_validation_report(data))
    return 1 if data.validation_issues else 0

def _handle_final_grades(args: argparse.Namespace) -> int:
    data = _load(args)
    print(build_final_grades_report(data))
    return 0


def _handle_student_report(args: argparse.Namespace) -> int:
    data = _load(args)
    print(build_student_report(data, args.student))
    return 0


def _handle_category_report(args: argparse.Namespace) -> int:
    data = _load(args)
    print(build_category_report(data))
    return 0


def _handle_rank(args: argparse.Namespace) -> int:
    data = _load(args)
    print(build_rank_report(data))
    return 0


def _handle_audit(args: argparse.Namespace) -> int:
    data = _load(args)
    print(audit_gradebook(data))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler")
    return handler(args)


def run(argv: Sequence[str] | None = None) -> int:
    return main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
