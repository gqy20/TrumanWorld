class TickInProgressError(RuntimeError):
    """Raised when another worker is already advancing the same run."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"A tick is already in progress for run {run_id}")
        self.run_id = run_id
