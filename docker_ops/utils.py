"""Shared helpers for docker_ops."""
import io


def text_to_fileobj(text: str) -> io.BytesIO:
    """Wrap a Dockerfile text body so the SDK can stream it as fileobj."""
    return io.BytesIO(text.encode("utf-8"))
