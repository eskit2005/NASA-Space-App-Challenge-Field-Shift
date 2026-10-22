"""Shared errors. Stages RAISE these; the API turns each into an HTTP code.
(Problems that don't stop the pipeline go in `warnings` instead.)"""


class CropseqError(Exception):
    """Base class. http_status is what the API returns."""

    http_status = 500

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message


class InvalidInput(CropseqError):
    """Bad request data (e.g. negative budget)."""

    http_status = 422


class UpstreamUnavailable(CropseqError):
    """An external API (SoilGrids, Open-Meteo, LLM) failed or timed out."""

    http_status = 504


class NoFeasibleSequences(CropseqError):
    """Constraints removed every option. Message should say which constraint."""

    http_status = 400
