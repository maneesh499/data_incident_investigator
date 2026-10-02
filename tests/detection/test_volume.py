from incident_investigator.detection.volume import PipelineRun, detect_volume_anomaly

def test_normal_volume():
    """Test when volume drop is within the acceptable threshold."""
    run = PipelineRun(
        pipeline_name="sales_pipeline",
        run_id="run-1",
        status="SUCCESS",
        actual_record_count=9500,
        expected_record_count=10000
    )
    result = detect_volume_anomaly(run, threshold_percentage=10.0)
    
    assert not result.is_anomaly
    assert result.volume_difference_percentage == 5.0
    assert "within acceptable limits" in result.message

def test_significant_volume_decrease():
    """Test when volume drops significantly, indicating an anomaly."""
    run = PipelineRun(
        pipeline_name="sales_pipeline",
        run_id="run-2",
        status="SUCCESS",
        actual_record_count=6200000,
        expected_record_count=10000000
    )
    result = detect_volume_anomaly(run, threshold_percentage=10.0)
    
    assert result.is_anomaly
    assert result.volume_difference_percentage == 38.0
    assert "Volume anomaly detected" in result.message

def test_missing_expected_count():
    """Test when the expected record count is not available."""
    run = PipelineRun(
        pipeline_name="sales_pipeline",
        run_id="run-3",
        status="SUCCESS",
        actual_record_count=5000,
        expected_record_count=None
    )
    result = detect_volume_anomaly(run)
    
    assert not result.is_anomaly
    assert result.volume_difference_percentage is None
    assert "No expected record count provided" in result.message

def test_expected_count_of_zero():
    """Test edge case where expected count is exactly zero."""
    run = PipelineRun(
        pipeline_name="sales_pipeline",
        run_id="run-4",
        status="SUCCESS",
        actual_record_count=10,
        expected_record_count=0
    )
    result = detect_volume_anomaly(run)
    
    assert not result.is_anomaly
    assert result.volume_difference_percentage is None
    assert "increase" in result.message

def test_actual_count_greater_than_expected():
    """Test when the pipeline processes more records than expected."""
    run = PipelineRun(
        pipeline_name="sales_pipeline",
        run_id="run-5",
        status="SUCCESS",
        actual_record_count=12000,
        expected_record_count=10000
    )
    result = detect_volume_anomaly(run)
    
    assert not result.is_anomaly
    assert result.volume_difference_percentage == -20.0
    assert "higher than expected" in result.message
