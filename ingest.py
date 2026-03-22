#!/usr/bin/env python3
"""
ingest.py — Load Claude Code telemetry data into DuckDB.

Usage:
    python3 ingest.py
    python3 ingest.py --telemetry output/telemetry_logs.jsonl --employees output/employees.csv --db analytics.duckdb
"""

import argparse
import json
import csv
import duckdb
from datetime import datetime

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    email           TEXT PRIMARY KEY,
    full_name       TEXT,
    practice        TEXT,
    level           TEXT,
    location        TEXT
);

CREATE TABLE IF NOT EXISTS api_requests (
    event_id                TEXT,
    session_id              TEXT,
    user_email              TEXT,
    timestamp               TIMESTAMP,
    model                   TEXT,
    cost_usd                DOUBLE,
    input_tokens            INTEGER,
    output_tokens           INTEGER,
    cache_read_tokens       INTEGER,
    cache_creation_tokens   INTEGER,
    duration_ms             INTEGER,
    os_type                 TEXT,
    terminal_type           TEXT,
    client_version          TEXT
);

CREATE TABLE IF NOT EXISTS user_prompts (
    event_id        TEXT,
    session_id      TEXT,
    user_email      TEXT,
    timestamp       TIMESTAMP,
    prompt_length   INTEGER
);

CREATE TABLE IF NOT EXISTS tool_events (
    event_id        TEXT,
    session_id      TEXT,
    user_email      TEXT,
    timestamp       TIMESTAMP,
    event_type      TEXT,
    tool_name       TEXT,
    decision        TEXT,
    success         BOOLEAN,
    duration_ms     INTEGER
);

CREATE TABLE IF NOT EXISTS api_errors (
    event_id        TEXT,
    session_id      TEXT,
    user_email      TEXT,
    timestamp       TIMESTAMP,
    model           TEXT,
    error_message   TEXT,
    status_code     TEXT,
    attempt         INTEGER,
    duration_ms     INTEGER
);
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_ts(ts_str):
    """Parse ISO timestamp string to datetime."""
    try:
        return datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except Exception:
        return None

def safe_int(val, default=0):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def safe_bool(val):
    if isinstance(val, bool):
        return val
    return str(val).lower() == "true"

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_employees(conn, path):
    print(f"Loading employees from {path} ...")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((
                row["email"].strip(),
                row["full_name"].strip(),
                row["practice"].strip(),
                row["level"].strip(),
                row["location"].strip(),
            ))
    conn.executemany(
        "INSERT OR IGNORE INTO employees VALUES (?, ?, ?, ?, ?)", rows
    )
    print(f"  Inserted {len(rows)} employees.")


def load_telemetry(conn, path):
    print(f"Loading telemetry from {path} ...")

    counts = {
        "api_requests": 0,
        "user_prompts": 0,
        "tool_events": 0,
        "api_errors": 0,
        "skipped": 0,
    }

    api_requests = []
    user_prompts = []
    tool_events = []
    api_errors = []

    BATCH_SIZE = 5000  # flush to DB every N events

    def flush():
        if api_requests:
            conn.executemany(
                "INSERT INTO api_requests VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                api_requests
            )
            api_requests.clear()
        if user_prompts:
            conn.executemany(
                "INSERT INTO user_prompts VALUES (?,?,?,?,?)",
                user_prompts
            )
            user_prompts.clear()
        if tool_events:
            conn.executemany(
                "INSERT INTO tool_events VALUES (?,?,?,?,?,?,?,?,?)",
                tool_events
            )
            tool_events.clear()
        if api_errors:
            conn.executemany(
                "INSERT INTO api_errors VALUES (?,?,?,?,?,?,?,?,?)",
                api_errors
            )
            api_errors.clear()

    total_events = 0

    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                batch = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"  Warning: Could not parse line {line_num}: {e}")
                continue

            log_events = batch.get("logEvents", [])

            for log_event in log_events:
                total_events += 1

                try:
                    event = json.loads(log_event["message"])
                except (json.JSONDecodeError, KeyError):
                    counts["skipped"] += 1
                    continue

                body = event.get("body", "")
                attrs = event.get("attributes", {})
                resource = event.get("resource", {})
                scope = event.get("scope", {})

                # Common fields
                event_id    = str(log_event.get("id", ""))
                session_id  = attrs.get("session.id", "")
                user_email  = attrs.get("user.email", "")
                timestamp   = parse_ts(attrs.get("event.timestamp", ""))
                os_type     = resource.get("os.type", "")
                terminal    = attrs.get("terminal.type", "")
                version     = scope.get("version", "")

                # Route by event type
                if body == "claude_code.api_request":
                    api_requests.append((
                        event_id,
                        session_id,
                        user_email,
                        timestamp,
                        attrs.get("model", ""),
                        safe_float(attrs.get("cost_usd")),
                        safe_int(attrs.get("input_tokens")),
                        safe_int(attrs.get("output_tokens")),
                        safe_int(attrs.get("cache_read_tokens")),
                        safe_int(attrs.get("cache_creation_tokens")),
                        safe_int(attrs.get("duration_ms")),
                        os_type,
                        terminal,
                        version,
                    ))
                    counts["api_requests"] += 1

                elif body == "claude_code.user_prompt":
                    user_prompts.append((
                        event_id,
                        session_id,
                        user_email,
                        timestamp,
                        safe_int(attrs.get("prompt_length")),
                    ))
                    counts["user_prompts"] += 1

                elif body == "claude_code.tool_decision":
                    tool_events.append((
                        event_id,
                        session_id,
                        user_email,
                        timestamp,
                        "decision",
                        attrs.get("tool_name", ""),
                        attrs.get("decision", ""),
                        None,   # success — not applicable
                        None,   # duration_ms — not applicable
                    ))
                    counts["tool_events"] += 1

                elif body == "claude_code.tool_result":
                    tool_events.append((
                        event_id,
                        session_id,
                        user_email,
                        timestamp,
                        "result",
                        attrs.get("tool_name", ""),
                        None,   # decision — not applicable
                        safe_bool(attrs.get("success", False)),
                        safe_int(attrs.get("duration_ms")),
                    ))
                    counts["tool_events"] += 1

                elif body == "claude_code.api_error":
                    api_errors.append((
                        event_id,
                        session_id,
                        user_email,
                        timestamp,
                        attrs.get("model", ""),
                        attrs.get("error", ""),
                        attrs.get("status_code", ""),
                        safe_int(attrs.get("attempt")),
                        safe_int(attrs.get("duration_ms")),
                    ))
                    counts["api_errors"] += 1

                else:
                    counts["skipped"] += 1

                # Flush every BATCH_SIZE events
                total_inserted = sum(counts[k] for k in ["api_requests", "user_prompts", "tool_events", "api_errors"])
                if total_inserted % BATCH_SIZE == 0 and total_inserted > 0:
                    flush()
                    print(f"  ... flushed {total_inserted} events so far (line {line_num})")

    # Final flush
    flush()

    print(f"\n  Total raw log events processed : {total_events}")
    return counts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingest Claude Code telemetry into DuckDB")
    parser.add_argument("--telemetry",  default="output/telemetry_logs.jsonl")
    parser.add_argument("--employees",  default="output/employees.csv")
    parser.add_argument("--db",         default="analytics.duckdb")
    args = parser.parse_args()

    print(f"\n=== Claude Code Telemetry Ingestion ===")
    print(f"  Database : {args.db}")
    print(f"  Telemetry: {args.telemetry}")
    print(f"  Employees: {args.employees}\n")

    conn = duckdb.connect(args.db)
    conn.execute(SCHEMA)

    load_employees(conn, args.employees)
    counts = load_telemetry(conn, args.telemetry)

    conn.close()

    print("\n=== Ingestion Complete ===")
    print(f"  api_requests : {counts['api_requests']:,}")
    print(f"  user_prompts : {counts['user_prompts']:,}")
    print(f"  tool_events  : {counts['tool_events']:,}")
    print(f"  api_errors   : {counts['api_errors']:,}")
    print(f"  skipped      : {counts['skipped']:,}")
    print(f"\nDatabase saved to: {args.db}")
    print("You can now run your dashboard or analytics queries against it.")


if __name__ == "__main__":
    main()