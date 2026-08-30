"""Unit tests for the HR tool functions, against a small hand-built
database (not the randomly seeded one) so the expected numbers are known
ahead of time.

Run with:  python -m pytest tests/  (or: python -m unittest discover)
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def _build_fixture_db(path: Path) -> None:
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    conn.execute(
        "INSERT INTO employees (id, name, role, hourly_rate, hire_date, termination_date, status) "
        "VALUES (1, 'Test Activo', 'Albañil', 100.0, '2023-01-01', NULL, 'active')"
    )
    conn.execute(
        "INSERT INTO employees (id, name, role, hourly_rate, hire_date, termination_date, status) "
        "VALUES (2, 'Test Ex Empleado', 'Electricista', 50.0, '2020-01-01', '2025-06-01', 'inactive')"
    )

    # Employee 1: 2025 leftover (10 accrued, 4 taken -> 6 carry-over), 2026 (15 accrued, 2 taken)
    conn.execute(
        "INSERT INTO vacation_ledger (employee_id, year, days_accrued, days_taken) VALUES (1, 2025, 10.0, 4.0)"
    )
    conn.execute(
        "INSERT INTO vacation_ledger (employee_id, year, days_accrued, days_taken) VALUES (1, 2026, 15.0, 2.0)"
    )

    # Employee 1, July 2026: 3 day-shift overtime hours, 2 night-shift overtime hours
    conn.execute(
        "INSERT INTO time_entries (employee_id, date, hours_worked, overtime_hours, shift_type) "
        "VALUES (1, '2026-07-10', 8.0, 3.0, 'day')"
    )
    conn.execute(
        "INSERT INTO time_entries (employee_id, date, hours_worked, overtime_hours, shift_type) "
        "VALUES (1, '2026-07-11', 8.0, 2.0, 'night')"
    )
    conn.execute(
        "INSERT INTO time_entries (employee_id, date, hours_worked, overtime_hours, shift_type) "
        "VALUES (1, '2026-07-12', 8.0, 0.0, 'day')"
    )

    conn.execute(
        "INSERT INTO employment_history "
        "(employee_id, start_date, end_date, role, notes, performance_rating, termination_reason) "
        "VALUES (2, '2020-01-01', '2025-06-01', 'Electricista', 'Buen trabajo', 4.5, 'Renuncia voluntaria')"
    )
    conn.commit()
    conn.close()


class HrToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path(__file__).parent / "_fixture.db"
        _build_fixture_db(self.db_path)

        import importlib
        import server as server_module

        server_module.DB_PATH = self.db_path
        self.server = importlib.reload(server_module)
        self.server.DB_PATH = self.db_path

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_get_employee_by_id(self) -> None:
        result = self.server.get_employee(employee_id=1)
        self.assertEqual(result["name"], "Test Activo")

    def test_get_employee_not_found(self) -> None:
        result = self.server.get_employee(employee_id=999)
        self.assertIn("error", result)

    def test_vacation_balance_carries_over_previous_years(self) -> None:
        result = self.server.get_vacation_balance(employee_id=1, year=2026)
        self.assertEqual(result["days_accrued_this_year"], 15.0)
        self.assertEqual(result["days_taken_this_year"], 2.0)
        self.assertEqual(result["days_carried_over_from_previous_years"], 6.0)  # 10 - 4
        self.assertEqual(result["days_available"], 19.0)  # 15 - 2 + 6

    def test_overtime_pay_applies_correct_multipliers(self) -> None:
        result = self.server.calculate_overtime_pay(employee_id=1, period="2026-07")
        # 3h day * 100 * 1.5 = 450; 2h night * 100 * 1.75 = 350
        self.assertEqual(result["breakdown_by_shift_type"]["day"]["pay"], 450.0)
        self.assertEqual(result["breakdown_by_shift_type"]["night"]["pay"], 350.0)
        self.assertEqual(result["total_overtime_pay"], 800.0)
        self.assertEqual(result["total_overtime_hours"], 5.0)

    def test_payroll_summary_adds_regular_and_overtime(self) -> None:
        result = self.server.get_payroll_summary(employee_id=1, period="2026-07")
        # regular hours: 8+8+8 = 24h * 100 = 2400; overtime 800 -> gross 3200
        self.assertEqual(result["regular_pay"], 2400.0)
        self.assertEqual(result["overtime_pay"], 800.0)
        self.assertEqual(result["gross_total"], 3200.0)

    def test_employee_history_includes_termination_reason(self) -> None:
        result = self.server.get_employee_history(employee_id=2)
        self.assertEqual(len(result["history"]), 1)
        self.assertEqual(result["history"][0]["termination_reason"], "Renuncia voluntaria")

    def test_search_employees_filters_by_status(self) -> None:
        active = self.server.search_employees(status="active")
        self.assertEqual([e["id"] for e in active], [1])


if __name__ == "__main__":
    unittest.main()
