class MissionError(Exception):
    """Public error codes never contain provider exceptions or private inputs."""

    def __init__(self, code: str, status_code: int = 503):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
