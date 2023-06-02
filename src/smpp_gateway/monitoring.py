import logging
import queue
import threading
import time

logger = logging.getLogger(__name__)


class HealthchecksIoWorker:
    """
    Worker class to ping healthchecks.io from a separate thread (avoids holding
    up the main loop in case of connectivity issues).
    """

    SUCCESS = 1
    FAIL = 2

    def __init__(self, uuid):
        # Only attempt import if healthchecks.io is enabled
        from healthchecks_io import Client

        self.queue = queue.Queue()
        self.client = Client()
        self.uuid = uuid
        threading.Thread(target=self._worker_thread, daemon=True).start()

    def _worker_thread(self):
        from healthchecks_io.client.exceptions import HCAPIError

        last_success_time = 0
        while True:
            item = self.queue.get()
            try:
                if item == HealthchecksIoWorker.SUCCESS:
                    # Skip success_ping if less than a minute has passed since the last one
                    # (the highest frequency possible in healthchecks.io / cron syntax).
                    if last_success_time + 60 < time.time():
                        logger.debug(f"Sending success_ping for {self.uuid}")
                        self.client.success_ping(uuid=self.uuid)
                        last_success_time = time.time()
                    else:
                        logger.debug(f"Skipping success_ping for {self.uuid}")
                elif item == HealthchecksIoWorker.FAIL:
                    logger.debug(f"Sending fail_ping for {self.uuid}")
                    self.client.fail_ping(uuid=self.uuid)
                else:
                    raise ValueError(f"Unknown task: {item}")
            except HCAPIError:
                logger.warn("Failed to ping healthchecks.io API", exc_info=True)
            self.queue.task_done()

    def success_ping(self):
        self.queue.put(HealthchecksIoWorker.SUCCESS)

    def fail_ping(self):
        self.queue.put(HealthchecksIoWorker.FAIL)

    def join(self):
        # Block until all tasks are done.
        self.queue.join()
