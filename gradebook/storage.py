from __future__ import annotations

from .importer import load_gradebook_data
from .models import GradebookData


class InMemoryStorage:
    def __init__(self) -> None:
        self.data = GradebookData()

    def load(self, students_path: str, assignments_path: str, grades_path: str) -> GradebookData:
        # STATE-01: replace state so repeated loads of same files don't duplicate data
        self.data = load_gradebook_data(students_path, assignments_path, grades_path)
        return self.data
