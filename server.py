"""HR MCP server for a (fictional) construction/remodeling company.

Exposes tools to query payroll, vacation balances, overtime pay, and
employee history from a SQLite database — see README.md for the full
tool spec and schema.sql / seed.py for the data model.

Run it directly for local testing (stdio transport, same as how an
MCP host like Claude Desktop or our own chatbot launches it):

    python server.py
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from seed import DEFAULT_DB_PATH, build_database

DB_PATH = Path(os.environ.get("HR_DB_PATH", DEFAULT_DB_PATH))

# Overtime pay multipliers by shift type (fictional policy for this demo).
OVERTIME_MULTIPLIERS = {"day": 1.5, "night": 1.75, "holiday": 2.0}

# NOTE: this was called FastMCP (mcp.server.fastmcp) in mcp 1.x — the SDK
# renamed it to MCPServer in 2.x. If you're on mcp<2, swap this import for
# `from mcp.server.fastmcp import FastMCP as MCPServer`.
mcp = MCPServer(
    "hr-construccion",
    instructions=(
        "HR tools for a construction/remodeling company: employee lookup, "
        "vacation balances, overtime pay, payroll summaries, and full "
        "employment history. All data is fictional/simulated."
    ),
)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        build_database(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _find_employee(conn: sqlite3.Connection, employee_id: int | None, name: str | None) -> sqlite3.Row | None:
    if employee_id is not None:
        return conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if name:
        return conn.execute(
            "SELECT * FROM employees WHERE name LIKE ? LIMIT 1", (f"%{name}%",)
        ).fetchone()
    return None


@mcp.tool()
def get_employee(employee_id: int | None = None, name: str | None = None) -> dict:
    """Look up an employee's basic data by id or by (partial) name.

    Provide exactly one of `employee_id` or `name`.
    """
    if employee_id is None and not name:
        return {"error": "Provide either employee_id or name."}
    conn = _connect()
    try:
        row = _find_employee(conn, employee_id, name)
        if row is None:
            return {"error": f"No employee found for employee_id={employee_id!r} name={name!r}"}
        return _row_to_dict(row)
    finally:
        conn.close()


@mcp.tool()
def search_employees(
    status: str | None = None, role: str | None = None, name_contains: str | None = None
) -> list[dict]:
    """List employees, optionally filtered by status ('active'/'inactive'), role, or name substring."""
    query = "SELECT * FROM employees WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if role:
        query += " AND role LIKE ?"
        params.append(f"%{role}%")
    if name_contains:
        query += " AND name LIKE ?"
        params.append(f"%{name_contains}%")
    conn = _connect()
    try:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


@mcp.tool()
def get_vacation_balance(employee_id: int, year: int | None = None) -> dict:
    """Vacation days for an employee: taken/accrued this year, plus carried-over days from previous years.

    If `year` is omitted, uses the current year.
    """
    import datetime

    year = year or datetime.date.today().year
    conn = _connect()
    try:
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
        if employee is None:
            return {"error": f"No employee with id {employee_id}"}

        rows = conn.execute(
            "SELECT year, days_accrued, days_taken FROM vacation_ledger "
            "WHERE employee_id = ? AND year <= ? ORDER BY year",
            (employee_id, year),
        ).fetchall()

        this_year = next((r for r in rows if r["year"] == year), None)
        carried_over = sum(
            max(r["days_accrued"] - r["days_taken"], 0.0) for r in rows if r["year"] < year
        )
        accrued_this_year = this_year["days_accrued"] if this_year else 0.0
        taken_this_year = this_year["days_taken"] if this_year else 0.0
        available = round(accrued_this_year - taken_this_year + carried_over, 1)

        return {
            "employee_id": employee_id,
            "employee_name": employee["name"],
            "year": year,
            "days_accrued_this_year": accrued_this_year,
            "days_taken_this_year": taken_this_year,
            "days_carried_over_from_previous_years": round(carried_over, 1),
            "days_available": available,
        }
    finally:
        conn.close()


def _overtime_breakdown(conn: sqlite3.Connection, employee: sqlite3.Row, period: str) -> dict:
    entries = conn.execute(
        "SELECT overtime_hours, shift_type FROM time_entries "
        "WHERE employee_id = ? AND date LIKE ? AND overtime_hours > 0",
        (employee["id"], f"{period}%"),
    ).fetchall()

    by_shift: dict[str, dict] = {}
    total_hours = 0.0
    total_pay = 0.0
    for e in entries:
        shift = e["shift_type"]
        pay = e["overtime_hours"] * employee["hourly_rate"] * OVERTIME_MULTIPLIERS[shift]
        bucket = by_shift.setdefault(shift, {"hours": 0.0, "pay": 0.0, "multiplier": OVERTIME_MULTIPLIERS[shift]})
        bucket["hours"] += e["overtime_hours"]
        bucket["pay"] += pay
        total_hours += e["overtime_hours"]
        total_pay += pay

    for bucket in by_shift.values():
        bucket["hours"] = round(bucket["hours"], 1)
        bucket["pay"] = round(bucket["pay"], 2)

    return {
        "total_overtime_hours": round(total_hours, 1),
        "total_overtime_pay": round(total_pay, 2),
        "breakdown_by_shift_type": by_shift,
    }


@mcp.tool()
def calculate_overtime_pay(employee_id: int, period: str) -> dict:
    """Overtime hours and pay owed for an employee in a given month.

    `period` must be "YYYY-MM" (e.g. "2026-07"). Multipliers: day 1.5x,
    night 1.75x, holiday 2x, applied to the employee's hourly rate.
    """
    conn = _connect()
    try:
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
        if employee is None:
            return {"error": f"No employee with id {employee_id}"}
        result = _overtime_breakdown(conn, employee, period)
        result.update({"employee_id": employee_id, "employee_name": employee["name"], "period": period})
        return result
    finally:
        conn.close()


@mcp.tool()
def get_payroll_summary(employee_id: int, period: str) -> dict:
    """Full pay breakdown for an employee in a given month: regular pay + overtime pay = gross total.

    `period` must be "YYYY-MM".
    """
    conn = _connect()
    try:
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
        if employee is None:
            return {"error": f"No employee with id {employee_id}"}

        regular_hours = conn.execute(
            "SELECT COALESCE(SUM(hours_worked), 0) AS total FROM time_entries "
            "WHERE employee_id = ? AND date LIKE ?",
            (employee_id, f"{period}%"),
        ).fetchone()["total"]

        overtime = _overtime_breakdown(conn, employee, period)
        regular_pay = round(regular_hours * employee["hourly_rate"], 2)

        return {
            "employee_id": employee_id,
            "employee_name": employee["name"],
            "period": period,
            "hourly_rate": employee["hourly_rate"],
            "regular_hours": regular_hours,
            "regular_pay": regular_pay,
            "overtime_hours": overtime["total_overtime_hours"],
            "overtime_pay": overtime["total_overtime_pay"],
            "gross_total": round(regular_pay + overtime["total_overtime_pay"], 2),
        }
    finally:
        conn.close()


@mcp.tool()
def get_employee_history(employee_id: int) -> dict:
    """Full employment history for an employee: roles held, dates, performance ratings,
    and — if they no longer work here — why they left. Useful for writing reference letters.
    """
    conn = _connect()
    try:
        employee = conn.execute("SELECT * FROM employees WHERE id = ?", (employee_id,)).fetchone()
        if employee is None:
            return {"error": f"No employee with id {employee_id}"}

        history = conn.execute(
            "SELECT start_date, end_date, role, notes, performance_rating, termination_reason "
            "FROM employment_history WHERE employee_id = ? ORDER BY start_date",
            (employee_id,),
        ).fetchall()

        return {
            "employee": _row_to_dict(employee),
            "history": [_row_to_dict(h) for h in history],
        }
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run()
