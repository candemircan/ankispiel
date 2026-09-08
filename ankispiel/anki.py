import requests


class AnkiConnect:
    "Thin client for the AnkiConnect HTTP API (https://foosoft.net/projects/anki-connect/)."

    def __init__(self, url: str): self.url = url

    def invoke(self, action: str, **params):
        payload = dict(action=action, params=params, version=6)
        response = requests.post(self.url, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        if result.get("error"): raise RuntimeError(f"AnkiConnect error: {result['error']}")
        return result["result"]
