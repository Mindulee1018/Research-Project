from __future__ import annotations
from pathlib import Path
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from src.common.utils import load_yaml
from src.common.logging import get_logger
from src.pipeline.load_data import load_inputs
from src.pipeline.preprocess import preprocess
from src.pipeline.graph_build import build_graphs
from src.pipeline.community import detect_communities
from src.pipeline.features import build_features
from src.pipeline.scoring import compute_risk_scores
from src.pipeline.active_learning import build_moderation_queue
from src.pipeline.export import export_artifacts
from src.gnn.dataset import build_pyg_dataset
from src.gnn.train import train_graphsage, gnn_risk_scores

log = get_logger(__name__)


def run_full_pipeline(repo_root: Path):
    cfg = load_yaml(repo_root / "config" / "pipeline.yaml")

    data = preprocess(load_inputs(repo_root))
    graphs = build_graphs(data, cfg)
    comm = detect_communities(graphs)
    feats = build_features(data, graphs, comm, cfg)

    pyg_data = build_pyg_dataset(graphs, feats)
    model, _ = train_graphsage(pyg_data, epochs=50)
    feats["gnn_risk_score"] = gnn_risk_scores(model, pyg_data)

    scored = compute_risk_scores(feats, cfg)
    queue = build_moderation_queue(scored, cfg)

    export_artifacts(repo_root, data, graphs, scored, queue, comm)
    log.info("Pipeline re-run completed after file update.")


class CSVChangeHandler(FileSystemEventHandler):
    def __init__(self, repo_root: Path, target_files: list[str]):
        self.repo_root = repo_root
        self.target_files = {str(Path(f).name).lower() for f in target_files}
        self.last_run = 0

    def on_modified(self, event):
        if event.is_directory:
            return

        changed = Path(event.src_path).name.lower()
        if changed in self.target_files:
            now = time.time()

            # debounce: avoid double triggering while file is still being written
            if now - self.last_run < 3:
                return

            self.last_run = now
            log.info(f"Detected update in {changed}. Re-running pipeline...")
            try:
                run_full_pipeline(self.repo_root)
            except Exception as e:
                log.error(f"Pipeline failed after file update: {e}")


def start_watcher(repo_root: Path, watch_dir: Path, target_files: list[str]):
    event_handler = CSVChangeHandler(repo_root, target_files)
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=False)
    observer.start()
    log.info(f"Watching {watch_dir} for updates to: {target_files}")
    return observer