from src.config.config import Config
from src.streaming.consumer import BatchConsumer
from src.core.update_handler import run_updates

def main():
    consumer = BatchConsumer(Config())
    consumer.run_once()

    # run incremental update actions for newly triggered batches
    run_updates(processed_folder="data/processed", baseline_window=Config().baseline_window)

if __name__ == "__main__":
    main()
