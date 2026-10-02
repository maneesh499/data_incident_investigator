from dataclasses import dataclass
from typing import Optional

@dataclass
class PipelineRun:
    """Represents a single execution of a data pipeline."""
    pipeline_name: str
    run_id: str
    status: str
    actual_record_count: int
    expected_record_count: Optional[int] = None

@dataclass
class VolumeAnomalyResult:
    """Represents the result of a volume anomaly check."""
    is_anomaly: bool
    volume_difference_percentage: Optional[float]
    message: str

def detect_volume_anomaly(run: PipelineRun, threshold_percentage: float = 10.0) -> VolumeAnomalyResult:
    """
    Analyzes a pipeline run to detect if the actual record count is significantly
    lower than the expected record count.
    """
    if run.expected_record_count is None:
        return VolumeAnomalyResult(
            is_anomaly=False,
            volume_difference_percentage=None,
            message="No expected record count provided; cannot perform volume comparison."
        )

    expected = run.expected_record_count
    actual = run.actual_record_count

    if expected == 0:
        if actual == 0:
            return VolumeAnomalyResult(
                is_anomaly=False,
                volume_difference_percentage=0.0,
                message="Both expected and actual record counts are 0. No volume anomaly."
            )
        else:
            return VolumeAnomalyResult(
                is_anomaly=False,
                volume_difference_percentage=None,
                message=f"Expected 0 records but got {actual}. This is an increase, not a volume drop anomaly."
            )

    # Calculate percentage decrease
    # Example: expected=100, actual=60 -> ((100 - 60) / 100) * 100 = 40% decrease
    decrease_percentage = ((expected - actual) / expected) * 100.0

    if decrease_percentage > threshold_percentage:
        return VolumeAnomalyResult(
            is_anomaly=True,
            volume_difference_percentage=round(decrease_percentage, 2),
            message=f"Volume anomaly detected! Record count dropped by {decrease_percentage:.2f}% (Expected: {expected}, Actual: {actual}). Threshold is {threshold_percentage}%."
        )
    elif decrease_percentage < 0:
        return VolumeAnomalyResult(
            is_anomaly=False,
            volume_difference_percentage=round(decrease_percentage, 2),
            message=f"Volume is higher than expected. Anomaly logic focuses on volume drop. Expected: {expected}, Actual: {actual}."
        )
    else:
        return VolumeAnomalyResult(
            is_anomaly=False,
            volume_difference_percentage=round(decrease_percentage, 2),
            message=f"Volume drop is within acceptable limits. Drop: {decrease_percentage:.2f}%. Threshold: {threshold_percentage}%."
        )
