from dataclasses import dataclass

@dataclass
class Config:
    batch_folder: str = "data/batches"
    processed_folder: str = "data/processed"

    baseline_window: int = 5
    min_rows_in_batch: int = 10

    new_term_rate_threshold: float = 0.15
    jsd_hard_threshold: float = 0.12

    # concept drift proxy thresholds
    concept_delta_threshold: float = 0.12
    concept_bigfrac_threshold: float = 0.10

    # incremental learning thresholds
    incremental_min_term_total_count: int = 2
    incremental_min_hate_count: int = 1
    incremental_min_hate_ratio: float = 0.60