import httpx

from core.config import get_settings

HORN_BUGLE_HISTORY = "/v1/horn-bugle-world/history"

DEFAULT_SERVER = "류트"


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        base_url=settings.mabinogi_open_api_url,
        headers={
            "accept": "application/json",
            "x-nxopen-api-key": settings.mabinogi_open_api_key,
        },
    )


def get_horn_bugle_history(server_name: str = DEFAULT_SERVER) -> dict:
    with _client() as client:
        resp = client.get(HORN_BUGLE_HISTORY, params={"server_name": server_name})
        resp.raise_for_status()
        return resp.json()
