# mcp-server-rrhh-construccion

> **Status: scope approved by the professor, implementation starting.**
> See the full specification draft at
> [`../Proyecto1-Redes/docs/hr_server_spec_draft.md`](../Proyecto1-Redes/docs/hr_server_spec_draft.md)
> in the main project repo.

An MCP (Model Context Protocol) server that exposes HR management tools
for a construction/remodeling company: vacation balances, overtime pay
calculations, payroll summaries, and employee history — backed by a
SQLite database with simulated data. Built as the custom local MCP
server for [CC3067 Redes](https://github.com) Project 1 (UVG).

This repository is independent and public so other students can install
and use this server from their own MCP host/chatbot.

## Tools exposed

_To be completed once implemented. Draft spec:_

| Tool | Parameters | Returns |
|---|---|---|
| `get_employee` | `employee_id` or `name` | Basic employee data |
| `get_vacation_balance` | `employee_id`, `year?` | Vacation days taken / available / carried over |
| `calculate_overtime_pay` | `employee_id`, `period` | Overtime hours and pay owed |
| `get_payroll_summary` | `employee_id`, `period` | Pay breakdown for the period |
| `get_employee_history` | `employee_id` | Full employment history |
| `search_employees` | filters | List of matching employees |

## Installation

_To be completed._

## Usage examples

_To be completed._

## Data

All data is fictional/simulated — no real personal data is used.
