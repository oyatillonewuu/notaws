"""Docker client singleton. Initialized lazily to avoid import-time failures
when Docker is not running (e.g., during migrations or test collection)."""
import docker

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client


class _LazyClient:
    def __getattr__(self, name):
        return getattr(_get_client(), name)


docker_client = _LazyClient()
