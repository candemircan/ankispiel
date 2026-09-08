"ntfy push notifications for run/migrate reports."

import requests

from ankispiel.config import AppConfig


def notify(cfg: AppConfig, title: str, body: str, tags: str = "white_check_mark") -> None:
    if not cfg.notify.ntfy_url: return
    requests.post(cfg.notify.ntfy_url, data=body.encode("utf-8"),
        headers={"Title": title, "Tags": tags}, timeout=30).raise_for_status()
