# mcp-server-rrhh-construccion

> **Status: implemented and tested.** Custom local MCP server for
> [CC3067 Redes](https://github.com/NESHGP04/Proyecto1-Redes) Project 1
> (UVG) — functional requirement #5 (own local MCP server, non-trivial).
> Scope approved by the professor beforehand; see
> [`../Proyecto1-Redes/docs/hr_server_spec_draft.md`](https://github.com/NESHGP04/Proyecto1-Redes/blob/main/docs/hr_server_spec_draft.md).

An MCP (Model Context Protocol) server that exposes HR management tools
for a **fictional** construction/remodeling company: employee lookup,
vacation balances (with carry-over from previous years), overtime pay
calculations (with shift-type multipliers), payroll summaries, and full
employment history (for reference-letter type queries) — all backed by
a small SQLite database.

This repository is independent and public so other students can install
and use this server from their own MCP host/chatbot.

## Why this isn't trivial

- A real relational data model: `employees`, `vacation_ledger`,
  `time_entries`, `employment_history` (see `schema.sql`).
- Real business logic: prorated vacation accrual + multi-year carry-over,
  overtime pay with different multipliers per shift type (day 1.5x,
  night 1.75x, holiday 2x), and aggregation across tables for payroll
  and history summaries.
- The host LLM has to combine multiple tool calls and reason over
  structured data (e.g. deciding whether a former employee's record
  supports a positive reference letter).

## Tools exposed

| Tool | Parameters | Returns |
|---|---|---|
| `get_employee` | `employee_id?: int`, `name?: str` (give one) | Basic employee record |
| `search_employees` | `status?`, `role?`, `name_contains?` | List of matching employees |
| `get_vacation_balance` | `employee_id: int`, `year?: int` (default: current year) | Days accrued/taken this year, days carried over, days available |
| `calculate_overtime_pay` | `employee_id: int`, `period: str` ("YYYY-MM") | Overtime hours/pay, broken down by shift type |
| `get_payroll_summary` | `employee_id: int`, `period: str` | Regular pay + overtime pay = gross total for the month |
| `get_employee_history` | `employee_id: int` | Full employment history: roles, dates, performance ratings, termination reason |

### Example: `get_vacation_balance(employee_id=5, year=2026)`

```json
{
  "employee_id": 5,
  "employee_name": "Pedro García",
  "year": 2026,
  "days_accrued_this_year": 15.0,
  "days_taken_this_year": 3.2,
  "days_carried_over_from_previous_years": 13.5,
  "days_available": 25.3
}
```

### Example: `calculate_overtime_pay(employee_id=5, period="2026-07")`

```json
{
  "total_overtime_hours": 18.9,
  "total_overtime_pay": 3678.98,
  "breakdown_by_shift_type": {
    "day": { "hours": 10.3, "pay": 1826.19, "multiplier": 1.5 },
    "night": { "hours": 6.1, "pay": 1261.79, "multiplier": 1.75 },
    "holiday": { "hours": 2.5, "pay": 591.0, "multiplier": 2.0 }
  },
  "employee_id": 5,
  "employee_name": "Pedro García",
  "period": "2026-07"
}
```

## Installation

Requires **Python 3.12+**.

```bash
git clone https://github.com/NESHGP04/mcp-server-rrhh-construccion.git
cd mcp-server-rrhh-construccion
python3.12 -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

The database (`hr.db`) is created automatically the first time the
server runs, seeded with ~16 fictional employees. To (re)generate it
manually instead:

```bash
python seed.py
```

## Usage

### Standalone (for testing/inspection)

```bash
source .venv/bin/activate
python server.py
```

This starts the server on stdio, exactly like any MCP host would launch
it. You normally don't run it directly — an MCP host does, as a
subprocess (see below).

### From an MCP host (e.g. Claude Desktop, or your own chatbot)

Point your host's MCP client config at this server, e.g. for Claude
Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "hr-construccion": {
      "command": "/absolute/path/to/mcp-server-rrhh-construccion/.venv/bin/python",
      "args": ["/absolute/path/to/mcp-server-rrhh-construccion/server.py"]
    }
  }
}
```

Or from Python, using the official `mcp` client SDK:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(
    command="/absolute/path/to/mcp-server-rrhh-construccion/.venv/bin/python",
    args=["/absolute/path/to/mcp-server-rrhh-construccion/server.py"],
)
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("get_vacation_balance", {"employee_id": 5})
```

### Optional: custom database location

```bash
export HR_DB_PATH=/path/to/your/hr.db
```

## Running the tests

```bash
source .venv/bin/activate
python -m unittest tests.test_tools -v
```

7 tests cover vacation carry-over math, overtime multipliers, payroll
totals, and error handling — against a small hand-built fixture database
(not the randomly seeded one), so expected numbers are known ahead of time.

## Data

All data is 100% fictional/simulated (a made-up construction company,
"Constructora El Pilar") — no real personal data is used. See `seed.py`
for how it's generated (fixed random seed, so it's reproducible).

## A note on the `mcp` SDK version

This server uses `mcp.server.mcpserver.MCPServer` (the `mcp` 2.x API).
Earlier SDK versions (1.x) called the equivalent class `FastMCP`, living
in `mcp.server.fastmcp` — if you're stuck on `mcp<2` for some other
dependency, swap the import in `server.py`
(`from mcp.server.fastmcp import FastMCP as MCPServer`); the rest of the
code is unaffected, since the decorator-based API (`@mcp.tool()`,
`mcp.run()`) is the same shape in both.
