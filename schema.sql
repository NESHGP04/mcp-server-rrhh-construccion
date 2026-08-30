-- Schema for the HR MCP server's SQLite database.
-- All data is fictional (see seed.py) — no real employees.

CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL,
    hourly_rate     REAL NOT NULL,          -- in fictional local currency units
    hire_date       TEXT NOT NULL,          -- ISO date YYYY-MM-DD
    termination_date TEXT,                  -- NULL while active
    status          TEXT NOT NULL CHECK (status IN ('active', 'inactive'))
);

-- One row per employee per calendar year: how many vacation days they
-- accrued that year and how many they've taken. "Available" and
-- "carried over from previous years" are computed by the server, not
-- stored directly.
CREATE TABLE IF NOT EXISTS vacation_ledger (
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    year            INTEGER NOT NULL,
    days_accrued    REAL NOT NULL,
    days_taken      REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (employee_id, year)
);

-- One row per work day. overtime_hours is the portion of that day's
-- hours that counts as overtime (already excluded from hours_worked).
-- shift_type affects the overtime multiplier applied when calculating pay.
CREATE TABLE IF NOT EXISTS time_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL REFERENCES employees(id),
    date            TEXT NOT NULL,          -- ISO date YYYY-MM-DD
    hours_worked    REAL NOT NULL,          -- regular hours that day
    overtime_hours  REAL NOT NULL DEFAULT 0,
    shift_type      TEXT NOT NULL CHECK (shift_type IN ('day', 'night', 'holiday'))
);

-- Full employment history, including past roles/assignments and, for
-- former employees, why they left and how they performed — this is what
-- powers the "write a reference letter" use case.
CREATE TABLE IF NOT EXISTS employment_history (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id         INTEGER NOT NULL REFERENCES employees(id),
    start_date          TEXT NOT NULL,
    end_date            TEXT,
    role                TEXT NOT NULL,
    notes               TEXT,
    performance_rating  REAL,               -- 1.0 to 5.0, NULL if not evaluated
    termination_reason  TEXT                -- NULL while active / not applicable
);

CREATE INDEX IF NOT EXISTS idx_vacation_employee ON vacation_ledger(employee_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_employee_date ON time_entries(employee_id, date);
CREATE INDEX IF NOT EXISTS idx_history_employee ON employment_history(employee_id);
