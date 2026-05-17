from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse


_SEARCH_ENGINE_HOSTS = frozenset(
    {
        "baidu.com",
        "bing.com",
        "duckduckgo.com",
        "google.com",
        "google.co.kr",
        "naver.com",
        "search.naver.com",
        "yahoo.com",
        "yandex.com",
    }
)

_DOMAIN_RE = re.compile(
    r"(?<![\w@])((?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,})(?:/[^\s]*)?",
    re.IGNORECASE,
)

_HOST_ALIASES = {
    "allrecipe.com": frozenset({"allrecipe.com", "allrecipes.com"}),
    "allrecipes.com": frozenset({"allrecipe.com", "allrecipes.com"}),
}


def _normalize_host(host: str) -> str:
    return host.strip().lower().removeprefix("www.")


def _host_matches(host: str, allowed_host: str) -> bool:
    host = _normalize_host(host)
    allowed_host = _normalize_host(allowed_host)
    return host == allowed_host or host.endswith(f".{allowed_host}")


@dataclass(frozen=True)
class NavigationScope:
    """Navigation limits inferred from a site- or service-specific user task."""

    description: str
    allowed_hosts: frozenset[str]
    blocked_search_hosts: frozenset[str] = _SEARCH_ENGINE_HOSTS
    allowed_google_flights_paths: bool = False

    @classmethod
    def from_query(cls, query: str) -> "NavigationScope | None":
        normalized = query.lower()

        is_google_flights_task = (
            "google flight" in normalized
            or "googleflight" in normalized
            or "구글 플라이트" in normalized
        )
        if is_google_flights_task:
            return cls(
                description=(
                    "Google Flights scope: use Google Flights pages only; do not use "
                    "general Google Search results as a substitute."
                ),
                allowed_hosts=frozenset({"google.com", "flights.google.com"}),
                allowed_google_flights_paths=True,
            )

        hosts = []
        for match in _DOMAIN_RE.finditer(query):
            raw = match.group(1)
            parsed = urlparse(raw if "://" in raw else f"https://{raw}")
            if parsed.hostname:
                hosts.append(_normalize_host(parsed.hostname))

        scoped_hosts = [host for host in hosts if host not in _SEARCH_ENGINE_HOSTS]
        if not scoped_hosts:
            return None

        expanded_hosts = set(scoped_hosts)
        for host in scoped_hosts:
            expanded_hosts.update(_HOST_ALIASES.get(host, ()))
        unique_hosts = frozenset(expanded_hosts)
        host_list = ", ".join(sorted(unique_hosts))
        return cls(
            description=(
                f"Site-specific scope: complete the task inside {host_list}. "
                "Use that site's own search, filters, forms, and navigation; do not "
                "switch to external search engines unless the user explicitly asks "
                "for open-web search."
            ),
            allowed_hosts=unique_hosts,
        )

    def allows_url(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = _normalize_host(parsed.hostname or "")
        if not host:
            return True

        if self.allowed_google_flights_paths and _host_matches(host, "google.com"):
            return parsed.path.startswith("/travel/flights") or parsed.path.startswith(
                "/travel/explore"
            )

        return any(_host_matches(host, allowed) for allowed in self.allowed_hosts)

    def blocks_search_url(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = _normalize_host(parsed.hostname or "")
        if not host:
            return False

        if self.allowed_google_flights_paths and _host_matches(host, "google.com"):
            return not self.allows_url(url)

        return any(_host_matches(host, blocked) for blocked in self.blocked_search_hosts)

    def violation_message(self, url: str) -> str:
        allowed = ", ".join(sorted(self.allowed_hosts))
        if self.allowed_google_flights_paths:
            allowed = "Google Flights (google.com/travel/flights or flights.google.com)"
        return (
            f"Navigation blocked by task scope. The current task must stay within {allowed}. "
            f"Do not use external search engines or unrelated sites for this scoped task. "
            f"Blocked URL: {url}"
        )

