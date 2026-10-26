import json
from pathlib import Path
from typing import Union
from incident_investigator.detection.volume import PipelineRun

def read_pipeline_run_from_json(file_path: Union[str, Path]) -> PipelineRun:
    """
    Reads a pipeline execution log from a JSON file and parses it into a PipelineRun object.
    
    Args:
        file_path: The path to the JSON file.
        
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON is invalid, missing required fields, or contains invalid data.
        
    Returns:
        PipelineRun: The parsed data model.
    """
    path = Path(file_path)
    
    # 1. Check if the file actually exists
    if not path.exists():
        raise FileNotFoundError(f"Pipeline log file not found: {file_path}")
        
    # 2. Try to read and parse the JSON string into a Python dictionary
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in file {file_path}: {str(e)}")
        
    # 3. Validate that the dictionary contains all our required fields
    required_fields = ["pipeline_name", "run_id", "status", "actual_record_count"]
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field '{field}' in JSON file: {file_path}")
            
    # 4. Validate that the numbers make sense (e.g., they aren't strings or negative)
    try:
        actual_count = int(data["actual_record_count"])
    except (ValueError, TypeError):
        raise ValueError(f"actual_record_count must be a valid integer, got: {data['actual_record_count']}")
        
    if actual_count < 0:
        raise ValueError("actual_record_count cannot be negative")
        
    # expected_record_count is optional, so we use .get() which returns None if the key doesn't exist
    expected_count = data.get("expected_record_count")
    if expected_count is not None:
        try:
            expected_count = int(expected_count)
        except (ValueError, TypeError):
            raise ValueError(f"expected_record_count must be a valid integer, got: {expected_count}")
            
        if expected_count < 0:
            raise ValueError("expected_record_count cannot be negative")

    # 5. Convert the raw dictionary into our typed PipelineRun dataclass
    return PipelineRun(
        pipeline_name=str(data["pipeline_name"]),
        run_id=str(data["run_id"]),
        status=str(data["status"]),
        actual_record_count=actual_count,
        expected_record_count=expected_count
    )
