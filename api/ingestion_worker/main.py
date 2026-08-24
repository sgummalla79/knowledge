"""Entrypoint: `python -m api.ingestion_worker.main`. Not wired into any live deployment yet -- see
api/deploy/k3s/07-ingestion-worker.yaml's replicas: 0 and this repo's Release 1 plan for why.

Deliberately skips this app's usual create_app()/bootstrap path -- no Flask app, no admin/MCP
bootstrap, no gunicorn. Just configure_logging() (so this process's log lines match the API's JSON
format) and the claim-and-process loop itself.
"""

import logging
import signal

from api.config import config
from api.ingestion_worker.worker import IngestionJobWorker
from api.logging_config import configure_logging

logger = logging.getLogger(__name__)

_stop_requested = False


def _handle_sigterm(signum, frame):
    global _stop_requested
    # Checked between claims, never mid-job -- same "cancellation checked between batches, not
    # instant" convention this app's cancel_job route already documents. A job already claimed
    # runs to completion before this process exits.
    logger.info("Received SIGTERM, will stop after the current job finishes")
    _stop_requested = True


def main() -> None:
    configure_logging(config.log_level)
    signal.signal(signal.SIGTERM, _handle_sigterm)
    worker = IngestionJobWorker()
    worker.run_forever(should_stop=lambda: _stop_requested)


if __name__ == "__main__":
    main()
