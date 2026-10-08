from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ScanVerdict:
    safe: bool
    scanner: str
    reason: str = ""


class UnsafeUploadError(ValueError):
    """Raised when an uploaded file looks dangerous or is flagged by ClamAV."""


class LocalHeuristicScanner:
    """Dependency-free safety net used before ClamAV is configured.

    This does not replace a real antivirus engine. It blocks common executable
    signatures and scripts that a web project upload should never contain.
    """

    name = "local-heuristics"

    def scan(self, content: bytes) -> ScanVerdict:
        signatures = (
            (b"MZ", "windows executable"),
            (b"\x7fELF", "linux executable"),
            (b"\xcf\xfa\xed\xfe", "mach-o executable"),
            (b"\xca\xfe\xba\xbe", "java class file"),
            (b"PK\x03\x04", None),
            (b"#!", "script with shebang"),
        )
        for signature, label in signatures:
            if label and content.startswith(signature):
                return ScanVerdict(False, self.name, f"blocked {label}")
        if b"<?php" in content[:2048]:
            return ScanVerdict(False, self.name, "blocked server-side script content")
        return ScanVerdict(True, self.name)


class ClamAvScanner:
    """Streams uploads to a ClamAV daemon for real-time scanning."""

    name = "clamav"

    def __init__(self, host: str, port: int, timeout: float = 30.0) -> None:
        self._host, self._port, self._timeout = host, port, timeout

    def scan(self, content: bytes) -> ScanVerdict:
        try:
            import clamd
        except ImportError as exc:
            raise RuntimeError("ClamAV scanning requires the clamd package") from exc
        try:
            client = clamd.ClamdNetworkSocket(self._host, self._port, self._timeout)
            result = client.instream(content)
        except Exception as exc:
            raise UnsafeUploadError("virus scan service is unavailable") from exc
        status = result.get("stream", ("ERROR", ""))[0].upper()
        if status == "OK":
            return ScanVerdict(True, self.name)
        return ScanVerdict(False, self.name, result.get("stream", ("FOUND", ""))[1] or "potential threat")


def build_upload_scanner() -> LocalHeuristicScanner | ClamAvScanner:
    host = os.getenv("CLAMAV_HOST", "").strip()
    if not host:
        return LocalHeuristicScanner()
    port = int(os.getenv("CLAMAV_PORT", "3310"))
    return ClamAvScanner(host, port, float(os.getenv("CLAMAV_TIMEOUT", "30")))


def scan_upload(scanner, content: bytes) -> ScanVerdict:
    verdict = scanner.scan(content)
    if not verdict.safe:
        raise UnsafeUploadError(verdict.reason or "uploaded file failed the security scan")
    return verdict
