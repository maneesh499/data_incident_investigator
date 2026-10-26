"""
Data-quality detection module for deterministic validation of pipeline datasets.
Evaluates null violations, duplicate primary keys, and data freshness against SLAs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union


@dataclass
class QualityCheckResult:
    """Represents the outcome of a deterministic data quality check."""
    check_name: str
    passed: bool
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"
    observed_value: Any
    threshold: Any
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


def check_null_columns(
    records: Sequence[Dict[str, Any]],
    columns: Sequence[str],
    max_null_percentage: float = 0.0,
    severity: str = "HIGH"
) -> QualityCheckResult:
    """
    Checks that null values in critical columns do not exceed the allowed percentage.
    
    Args:
        records: List of dictionary records representing tabular data rows.
        columns: Column names to inspect for null / None / empty string values.
        max_null_percentage: Maximum allowed percentage of nulls (default 0.0%).
        severity: Incident severity to assign if this check fails.
    """
    if not records:
        return QualityCheckResult(
            check_name="null_column_check",
            passed=True,
            severity="INFO",
            observed_value=0,
            threshold=max_null_percentage,
            message="No records provided; null check skipped.",
            details={"total_records": 0}
        )

    total_records = len(records)
    column_null_counts: Dict[str, int] = {col: 0 for col in columns}

    for row in records:
        for col in columns:
            val = row.get(col)
            if val is None or val == "":
                column_null_counts[col] += 1

    failing_columns: Dict[str, Dict[str, Any]] = {}
    max_observed_percentage = 0.0

    for col, null_count in column_null_counts.items():
        pct = (null_count / total_records) * 100.0
        if pct > max_observed_percentage:
            max_observed_percentage = pct
        if pct > max_null_percentage:
            failing_columns[col] = {
                "null_count": null_count,
                "null_percentage": round(pct, 2),
                "threshold": max_null_percentage
            }

    passed = len(failing_columns) == 0
    if passed:
        message = (
            f"All critical columns ({', '.join(columns)}) passed null check. "
            f"Max observed null percentage: {max_observed_percentage:.2f}%."
        )
    else:
        message = (
            f"Null threshold exceeded in {len(failing_columns)} column(s): "
            + ", ".join(f"{c} ({info['null_percentage']}%)" for c, info in failing_columns.items())
        )

    return QualityCheckResult(
        check_name="null_column_check",
        passed=passed,
        severity=severity if not passed else "INFO",
        observed_value=round(max_observed_percentage, 2),
        threshold=max_null_percentage,
        message=message,
        details={
            "total_records": total_records,
            "failing_columns": failing_columns,
            "column_null_counts": column_null_counts
        }
    )


def check_duplicate_keys(
    records: Sequence[Dict[str, Any]],
    primary_key_columns: Sequence[str],
    severity: str = "CRITICAL"
) -> QualityCheckResult:
    """
    Checks that records have unique composite primary keys.
    
    Args:
        records: List of dictionary records representing tabular data rows.
        primary_key_columns: Column name(s) forming the unique primary key.
        severity: Incident severity if duplicates are found (default CRITICAL).
    """
    if not records or not primary_key_columns:
        return QualityCheckResult(
            check_name="duplicate_key_check",
            passed=True,
            severity="INFO",
            observed_value=0,
            threshold=0,
            message="No records or primary keys provided; duplicate check skipped.",
            details={"total_records": len(records)}
        )

    total_records = len(records)
    seen_keys: set = set()
    duplicate_samples: List[Dict[str, Any]] = []
    duplicate_count = 0

    for row in records:
        key_tuple = tuple(row.get(col) for col in primary_key_columns)
        if key_tuple in seen_keys:
            duplicate_count += 1
            if len(duplicate_samples) < 5:
                duplicate_samples.append({col: row.get(col) for col in primary_key_columns})
        else:
            seen_keys.add(key_tuple)

    passed = duplicate_count == 0
    if passed:
        message = f"Zero duplicate keys found across {total_records} records on key(s): {', '.join(primary_key_columns)}."
    else:
        message = (
            f"Found {duplicate_count} duplicate record(s) on primary key(s): {', '.join(primary_key_columns)} "
            f"out of {total_records} total records."
        )

    return QualityCheckResult(
        check_name="duplicate_key_check",
        passed=passed,
        severity=severity if not passed else "INFO",
        observed_value=duplicate_count,
        threshold=0,
        message=message,
        details={
            "total_records": total_records,
            "duplicate_count": duplicate_count,
            "primary_key_columns": list(primary_key_columns),
            "duplicate_samples": duplicate_samples
        }
    )


def _parse_timestamp(ts: Union[str, datetime]) -> datetime:
    """Helper to parse ISO-8601 strings or pass through datetime objects."""
    if isinstance(ts, datetime):
        return ts
    # Support standard ISO format (e.g. 2026-10-26T12:00:00 or with Z)
    clean_ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(clean_ts)


def check_data_freshness(
    latest_event_time: Union[str, datetime],
    pipeline_execution_time: Union[str, datetime],
    max_delay_hours: float,
    severity: str = "HIGH"
) -> QualityCheckResult:
    """
    Checks if data freshness meets SLA by comparing the latest record event timestamp
    with the pipeline execution timestamp.
    
    Args:
        latest_event_time: The maximum event timestamp observed in the arriving dataset.
        pipeline_execution_time: The timestamp when the pipeline ran.
        max_delay_hours: Maximum allowable delay in hours before flagging an incident.
        severity: Incident severity if SLA is breached.
    """
    event_dt = _parse_timestamp(latest_event_time)
    exec_dt = _parse_timestamp(pipeline_execution_time)

    # Calculate lag in hours: execution_time - latest_event_time
    lag_seconds = (exec_dt - event_dt).total_seconds()
    lag_hours = lag_seconds / 3600.0

    passed = lag_hours <= max_delay_hours

    if passed:
        message = (
            f"Data freshness SLA met. Observed lag is {lag_hours:.2f} hours "
            f"(Threshold: <= {max_delay_hours:.2f} hours)."
        )
    else:
        message = (
            f"Data freshness SLA breached! Observed lag is {lag_hours:.2f} hours, "
            f"exceeding max allowed delay of {max_delay_hours:.2f} hours."
        )

    return QualityCheckResult(
        check_name="freshness_check",
        passed=passed,
        severity=severity if not passed else "INFO",
        observed_value=round(lag_hours, 2),
        threshold=max_delay_hours,
        message=message,
        details={
            "latest_event_time": event_dt.isoformat(),
            "pipeline_execution_time": exec_dt.isoformat(),
            "lag_hours": round(lag_hours, 2),
            "max_delay_hours": max_delay_hours
        }
    )
