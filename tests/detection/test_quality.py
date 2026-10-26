"""
Unit tests for data-quality checks: null violations, duplicate keys, and freshness SLA.
"""

from datetime import datetime, timezone
import pytest
from incident_investigator.detection.quality import (
    check_null_columns,
    check_duplicate_keys,
    check_data_freshness,
    QualityCheckResult
)


# --- Tests for check_null_columns ---

def test_null_check_passes_when_no_nulls():
    records = [
        {"order_id": "ord_1", "customer_id": "cust_101", "amount": 120.50},
        {"order_id": "ord_2", "customer_id": "cust_102", "amount": 89.00},
    ]
    result = check_null_columns(records, columns=["order_id", "customer_id"])
    assert result.passed is True
    assert result.observed_value == 0.0
    assert result.severity == "INFO"
    assert "passed null check" in result.message


def test_null_check_fails_when_null_percentage_exceeds_threshold():
    records = [
        {"order_id": "ord_1", "customer_id": "cust_101", "amount": 100},
        {"order_id": "ord_2", "customer_id": None, "amount": 200},
        {"order_id": "ord_3", "customer_id": None, "amount": 300},
        {"order_id": "ord_4", "customer_id": "cust_104", "amount": 400},
    ]
    # 2 out of 4 (50%) customer_ids are null, exceeding max allowed 5%
    result = check_null_columns(records, columns=["customer_id"], max_null_percentage=5.0)
    assert result.passed is False
    assert result.observed_value == 50.0
    assert result.severity == "HIGH"
    assert "Null threshold exceeded" in result.message
    assert "customer_id" in result.details["failing_columns"]
    assert result.details["failing_columns"]["customer_id"]["null_count"] == 2


def test_null_check_allows_tolerated_percentage():
    records = [
        {"order_id": "ord_1", "phone": "123456"},
        {"order_id": "ord_2", "phone": None},
        {"order_id": "ord_3", "phone": "789012"},
        {"order_id": "ord_4", "phone": "345678"},
    ]
    # 1 out of 4 (25%) is null, tolerated threshold is 30%
    result = check_null_columns(records, columns=["phone"], max_null_percentage=30.0)
    assert result.passed is True
    assert result.observed_value == 25.0


def test_null_check_empty_records():
    result = check_null_columns([], columns=["order_id"])
    assert result.passed is True
    assert result.observed_value == 0


# --- Tests for check_duplicate_keys ---

def test_duplicate_check_passes_when_all_unique():
    records = [
        {"order_id": "ord_1", "item_id": "item_A"},
        {"order_id": "ord_2", "item_id": "item_B"},
    ]
    result = check_duplicate_keys(records, primary_key_columns=["order_id"])
    assert result.passed is True
    assert result.observed_value == 0
    assert "Zero duplicate keys found" in result.message


def test_duplicate_check_fails_on_duplicate_primary_key():
    records = [
        {"order_id": "ord_1", "item_id": "item_A", "amount": 10},
        {"order_id": "ord_2", "item_id": "item_B", "amount": 20},
        {"order_id": "ord_1", "item_id": "item_C", "amount": 15},  # duplicate order_id
    ]
    result = check_duplicate_keys(records, primary_key_columns=["order_id"])
    assert result.passed is False
    assert result.observed_value == 1
    assert result.severity == "CRITICAL"
    assert result.details["duplicate_count"] == 1
    assert {"order_id": "ord_1"} in result.details["duplicate_samples"]


def test_duplicate_check_composite_key():
    records = [
        {"order_id": "ord_1", "item_id": "item_A"},
        {"order_id": "ord_1", "item_id": "item_B"},  # same order_id, different item_id -> unique
        {"order_id": "ord_1", "item_id": "item_A"},  # duplicate composite key
    ]
    result = check_duplicate_keys(records, primary_key_columns=["order_id", "item_id"])
    assert result.passed is False
    assert result.observed_value == 1


# --- Tests for check_data_freshness ---

def test_freshness_passes_within_sla():
    latest_event = "2026-10-26T10:00:00"
    pipeline_run = "2026-10-26T11:30:00"  # 1.5 hours lag
    result = check_data_freshness(latest_event, pipeline_run, max_delay_hours=2.0)
    assert result.passed is True
    assert result.observed_value == 1.5
    assert "Data freshness SLA met" in result.message


def test_freshness_fails_when_breaching_sla():
    latest_event = "2026-10-26T04:00:00"
    pipeline_run = "2026-10-26T12:00:00"  # 8 hours lag
    result = check_data_freshness(latest_event, pipeline_run, max_delay_hours=4.0)
    assert result.passed is False
    assert result.observed_value == 8.0
    assert result.severity == "HIGH"
    assert "Data freshness SLA breached" in result.message


def test_freshness_with_datetime_objects():
    latest_event = datetime(2026, 10, 26, 10, 0, 0)
    pipeline_run = datetime(2026, 10, 26, 10, 45, 0)  # 0.75 hours lag
    result = check_data_freshness(latest_event, pipeline_run, max_delay_hours=1.0)
    assert result.passed is True
    assert result.observed_value == 0.75
