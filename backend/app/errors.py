"""Typed errors. `code` is what the frontend translates into a friendly message."""


class JobError(Exception):
    code = "internal"

    def __init__(self, detail: str = ""):
        super().__init__(detail or self.code)
        self.detail = detail


class UnsupportedFile(JobError):
    code = "unsupported"


class FileTooLarge(JobError):
    code = "too_large"


class TooLong(JobError):
    code = "too_long"


class CorruptFile(JobError):
    code = "corrupt"


class ExtractFailed(JobError):
    code = "extract_failed"


class SeparationFailed(JobError):
    code = "separation_failed"


class FFmpegFailed(JobError):
    code = "ffmpeg_failed"


class DiskFull(JobError):
    code = "disk_full"


class Timeout(JobError):
    code = "timeout"


class Cancelled(JobError):
    code = "cancelled"
