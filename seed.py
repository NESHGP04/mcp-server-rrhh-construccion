"""Builds the SQLite database with 100% fictional data for a made-up
construction/remodeling company ("Constructora El Pilar").

Run directly to (re)create the database from scratch:

    python seed.py [path/to/hr.db]

The MCP server also calls `build_database()` automatically the first
time it starts if the database file doesn't exist yet, so classmates
who install this server don't have to run this manually.
"""

from __future__ import annotations

import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DEFAULT_DB_PATH = Path(__file__).parent / "hr.db"

ROLES_AND_RATES = [
    ("Albañil", 45.0),
    ("Maestro de obra", 65.0),
    ("Ingeniero residente", 110.0),
    ("Electricista", 55.0),
    ("Plomero", 52.0),
    ("Operador de maquinaria", 60.0),
    ("Supervisor de seguridad", 58.0),
    ("Administrativo de RRHH", 48.0),
    ("Contador", 70.0),
]

FIRST_NAMES = [
    "Carlos", "María", "José", "Ana", "Luis", "Sofía", "Miguel", "Gabriela",
    "Pedro", "Lucía", "Diego", "Valeria", "Jorge", "Camila", "Andrés", "Paola",
]
LAST_NAMES = [
    "García", "Morales", "López", "Hernández", "Ramírez", "Pérez", "Gómez",
    "Castillo", "Rodríguez", "Vásquez", "Girón", "Alvarado",
]

TERMINATION_REASONS = [
    ("Renuncia voluntaria", 4.5, "Buen desempeño; se fue por una mejor oferta."),
    ("Fin de contrato de obra", 4.0, "Contrato por proyecto; terminó junto con la obra."),
    ("Despido por bajo rendimiento", 2.0, "Incumplimiento reiterado de plazos."),
    ("Reestructuración de proyecto", 3.8, "Reducción de personal al cerrar un proyecto."),
]


def _random_date(rng: random.Random, start: date, end: date) -> date:
    days = (end - start).days
    return start + timedelta(days=rng.randint(0, max(days, 0)))


def build_database(db_path: Path | str = DEFAULT_DB_PATH, seed: int = 42) -> None:
    db_path = Path(db_path)
    if db_path.exists():
        db_path.unlink()

    rng = random.Random(seed)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    today = date(2026, 8, 28)  # matches the project's "today" for consistent demos
    employees = []
    used_names: set[str] = set()

    for emp_id in range(1, 17):
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                used_names.add(name)
                break
        role, base_rate = rng.choice(ROLES_AND_RATES)
        rate = round(base_rate * rng.uniform(0.9, 1.15), 2)
        hire_date = _random_date(rng, date(2018, 1, 1), date(2025, 6, 1))

        # ~25% of employees are former employees (for the reference-letter use case)
        is_former = emp_id <= 4
        if is_former:
            termination_date = _random_date(
                rng, max(hire_date + timedelta(days=180), date(2025, 6, 1)), today
            )
            status = "inactive"
        else:
            termination_date = None
            status = "active"

        employees.append(
            {
                "id": emp_id,
                "name": name,
                "role": role,
                "hourly_rate": rate,
                "hire_date": hire_date.isoformat(),
                "termination_date": termination_date.isoformat() if termination_date else None,
                "status": status,
            }
        )

    conn.executemany(
        "INSERT INTO employees (id, name, role, hourly_rate, hire_date, termination_date, status) "
        "VALUES (:id, :name, :role, :hourly_rate, :hire_date, :termination_date, :status)",
        employees,
    )

    # --- vacation ledger: ~15 days/year accrual (prorated for hire year), some taken ---
    vacation_rows = []
    for emp in employees:
        hire_year = int(emp["hire_date"][:4])
        last_year = (
            int(emp["termination_date"][:4]) if emp["termination_date"] else today.year
        )
        for year in range(max(hire_year, today.year - 2), last_year + 1):
            if year == hire_year:
                months_worked = 12 - int(emp["hire_date"][5:7]) + 1
                accrued = round(15 * months_worked / 12, 1)
            else:
                accrued = 15.0
            taken = round(min(accrued, rng.uniform(0, accrued * 0.8)), 1)
            vacation_rows.append((emp["id"], year, accrued, taken))

    conn.executemany(
        "INSERT INTO vacation_ledger (employee_id, year, days_accrued, days_taken) VALUES (?, ?, ?, ?)",
        vacation_rows,
    )

    # --- time entries: last 2 full months, active employees only, workdays only ---
    time_rows = []
    active_employees = [e for e in employees if e["status"] == "active"]
    period_start = date(2026, 7, 1)
    period_end = date(2026, 8, 28)
    day = period_start
    while day <= period_end:
        if day.weekday() < 6:  # skip Sundays
            for emp in active_employees:
                if rng.random() < 0.08:  # occasional absence
                    continue
                overtime = 0.0
                shift = "day"
                if rng.random() < 0.2:
                    shift = rng.choice(["day", "night", "holiday"])
                    overtime = round(rng.uniform(1, 4), 1)
                time_rows.append((emp["id"], day.isoformat(), 8.0, overtime, shift))
        day += timedelta(days=1)

    conn.executemany(
        "INSERT INTO time_entries (employee_id, date, hours_worked, overtime_hours, shift_type) "
        "VALUES (?, ?, ?, ?, ?)",
        time_rows,
    )

    # --- employment history: every former employee gets a full record; a couple
    #     of active employees also get a prior-role entry to show role changes ---
    history_rows = []
    for emp in employees:
        if emp["status"] == "inactive":
            reason, rating, notes = rng.choice(TERMINATION_REASONS)
            history_rows.append(
                (
                    emp["id"],
                    emp["hire_date"],
                    emp["termination_date"],
                    emp["role"],
                    notes,
                    rating,
                    reason,
                )
            )
        elif rng.random() < 0.3:
            # Simulate an earlier role before their current one.
            mid_date = _random_date(
                rng, date.fromisoformat(emp["hire_date"]), today - timedelta(days=200)
            )
            history_rows.append(
                (
                    emp["id"],
                    emp["hire_date"],
                    mid_date.isoformat(),
                    "Ayudante general",
                    "Rol inicial antes de su promoción.",
                    round(rng.uniform(3.5, 5.0), 1),
                    None,
                )
            )
            history_rows.append(
                (emp["id"], mid_date.isoformat(), None, emp["role"], "Rol actual.", None, None)
            )

    conn.executemany(
        "INSERT INTO employment_history "
        "(employee_id, start_date, end_date, role, notes, performance_rating, termination_reason) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        history_rows,
    )

    conn.commit()
    conn.close()
    print(f"Base de datos creada en {db_path} con {len(employees)} empleados ficticios.")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB_PATH
    build_database(target)
