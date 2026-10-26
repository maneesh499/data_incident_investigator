import json
import pytest
from pathlib import Path
from incident_investigator.ingestion.pipeline_log_reader import read_pipeline_run_from_json
from incident_investigator.detection.volume import PipelineRun, detect_volume_anomaly

def test_valid_json_creates_pipeline_run(tmp_path):
    """Test 1: A perfectly valid JSON file should successfully create a PipelineRun."""
    # tmp_path is a built-in pytest fixture that gives us a safe, temporary folder for testing
    test_file = tmp_path / "valid_run.json"
    valid_data = {
        "pipeline_name": "orders_ingestion",
        "run_id": "run_001",
        "status": "SUCCESS",
        "actual_record_count": 6200000,
        "expected_record_count": 10000000
    }
    
    # Write the dictionary as a real JSON file to our temporary folder
    with open(test_file, "w") as f:
        json.dump(valid_data, f)
        
    # Act: Run our new code
    run = read_pipeline_run_from_json(test_file)
    
    # Assert: Verify the result is exactly what we expect
    assert isinstance(run, PipelineRun)
    assert run.pipeline_name == "orders_ingestion"
    assert run.actual_record_count == 6200000
    
    # INTEGRATION TEST: Verify our ingestion output plugs directly into our detection logic
    result = detect_volume_anomaly(run)
    assert result.is_anomaly is True
    assert result.volume_difference_percentage == 38.0

def test_missing_file_raises_error():
    """Test 2: If the file doesn't exist, it should raise a clear FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match="Pipeline log file not found"):
        read_pipeline_run_from_json("non_existent_fake_file.json")

def test_invalid_json_raises_error(tmp_path):
    """Test 3: If the file contains garbage (not real JSON), it should raise a ValueError."""
    test_file = tmp_path / "invalid.json"
    with open(test_file, "w") as f:
        f.write("{ invalid json formatting: missing quotes }") # Bad JSON syntax
        
    with pytest.raises(ValueError, match="Invalid JSON format"):
        read_pipeline_run_from_json(test_file)

def test_missing_required_field_raises_error(tmp_path):
    """Test 4: If a required field like run_id is missing, it should raise a ValueError."""
    test_file = tmp_path / "missing_field.json"
    bad_data = {
        "pipeline_name": "orders",
        "status": "SUCCESS",
        "actual_record_count": 100
        # "run_id" is missing entirely
    }
    with open(test_file, "w") as f:
        json.dump(bad_data, f)
        
    with pytest.raises(ValueError, match="Missing required field 'run_id'"):
        read_pipeline_run_from_json(test_file)

def test_invalid_record_count_raises_error(tmp_path):
    """Test 5: If a record count is negative, it should be rejected with a ValueError."""
    test_file = tmp_path / "invalid_count.json"
    bad_data = {
        "pipeline_name": "orders",
        "run_id": "run_001",
        "status": "SUCCESS",
        "actual_record_count": -500  # Negative counts are impossible in reality
    }
    with open(test_file, "w") as f:
        json.dump(bad_data, f)
        
    with pytest.raises(ValueError, match="actual_record_count cannot be negative"):
        read_pipeline_run_from_json(test_file)
