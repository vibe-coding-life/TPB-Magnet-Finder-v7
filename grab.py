#!/usr/bin/env python3
"""
TPB Magnet Finder v7

https://github.com/vibe-coding-life

Intended for content you are authorised to download, including public-domain
and freely licensed material.

Input:
    queries.txt

Outputs:
    magnets.txt
        One magnet URI per line. Nothing else.

    failed.txt
        One failed query per line.

    proxies.txt
        Validated HTTP/SOCKS5 proxy URLs, fastest first.

Proxy behaviour:
    1. Load proxies.txt first.
    2. Deduplicate and validate saved proxies with up to 50 threads.
    3. If fewer than MIN_WORKING_PROXIES survive, harvest fresh HTTP/SOCKS5
       candidates, deduplicate them, and validate them in concurrent batches.
    4. Refuse to start searches unless at least MIN_WORKING_PROXIES are valid.
"""

from __future__ import annotations

import ipaddress
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import quote

import requests
from colorama import Fore, Style, init

try:
    import socks  # noqa: F401
except ImportError:
    print(
        "PySocks is not installed.\n"
        "Install dependencies with:\n"
        '    pip install colorama "requests[socks]"'
    )
    raise SystemExit(1)


# =============================================================================
# Configuration
# =============================================================================

TPB_API = "https://apibay.org/q.php"

INPUT_FILE = "queries.txt"
OUTPUT_FILE = "magnets.txt"
FAILED_FILE = "failed.txt"
PROXY_FILE = "proxies.txt"

# Searches will NOT start with fewer than this many validated proxies.
MIN_WORKING_PROXIES = 25

# Maximum concurrent proxy tests.
MAX_PROXY_THREADS = 50

# Fresh proxies are tested in chunks so thousands do not have to be tested
# unnecessarily once a sufficiently healthy pool has been obtained.
PROXY_TEST_BATCH_SIZE = 250

# Maximum number of validated proxies retained in proxies.txt.
# Change to None to save every working proxy found.
MAX_SAVED_WORKING_PROXIES: Optional[int] = 150

# Timeouts in seconds.
PROXY_CONNECT_TIMEOUT = 4
PROXY_READ_TIMEOUT = 7
SOURCE_TIMEOUT = 15
SEARCH_TIMEOUT = 15

# Search behaviour.
MIN_SEEDERS = 1
REQUEST_DELAY = 0.75

# Number of different proxies that can be attempted for one search.
MAX_PROXY_ATTEMPTS_PER_QUERY = 12

# Disable a proxy from the current run after this many search failures.
MAX_PROXY_FAILURES_BEFORE_DISABLE = 3

# Validate proxies against the actual search API.
PROXY_TEST_QUERY = "ubuntu"


# =============================================================================
# Public proxy sources
# =============================================================================

PROXY_SOURCES = [
    (
        "SpeedX HTTP",
        "http",
        "https://raw.githubusercontent.com/"
        "TheSpeedX/PROXY-List/master/http.txt",
    ),
    (
        "SpeedX SOCKS5",
        "socks5",
        "https://raw.githubusercontent.com/"
        "TheSpeedX/PROXY-List/master/socks5.txt",
    ),
    (
        "Monosans HTTP",
        "http",
        "https://raw.githubusercontent.com/"
        "monosans/proxy-list/main/proxies/http.txt",
    ),
    (
        "Monosans SOCKS5",
        "socks5",
        "https://raw.githubusercontent.com/"
        "monosans/proxy-list/main/proxies/socks5.txt",
    ),
    (
        "ProxyScrape HTTP",
        "http",
        "https://api.proxyscrape.com/v2/"
        "?request=getproxies"
        "&protocol=http"
        "&timeout=10000"
        "&country=all"
        "&ssl=all"
        "&anonymity=all",
    ),
    (
        "ProxyScrape SOCKS5",
        "socks5",
        "https://api.proxyscrape.com/v2/"
        "?request=getproxies"
        "&protocol=socks5"
        "&timeout=10000"
        "&country=all",
    ),
]


# =============================================================================
# Search quality matching
# =============================================================================

QUALITY_RE = re.compile(
    r"\b("
    r"1080p?|"
    r"1440p?|"
    r"2160p?|"
    r"4k|"
    r"uhd|"
    r"hdr|"
    r"hdr10\+?|"
    r"dovi|"
    r"dolby[\s._-]?vision|"
    r"remux|"
    r"blu-?ray|"
    r"bluray|"
    r"br-?rip|"
    r"brrip|"
    r"web[\s._-]?dl|"
    r"web[\s._-]?rip"
    r")\b",
    re.IGNORECASE,
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


# =============================================================================
# Colorama output
# =============================================================================

init(autoreset=True)


def heading(text: str) -> None:
    line = "=" * 76

    print()
    print(
        Fore.MAGENTA
        + Style.BRIGHT
        + line
    )

    print(
        Fore.MAGENTA
        + Style.BRIGHT
        + text
    )

    print(
        Fore.MAGENTA
        + Style.BRIGHT
        + line
    )


def info(text: str) -> None:
    print(
        f"{Fore.CYAN}[INFO]"
        f"{Style.RESET_ALL} "
        f"{text}"
    )


def good(text: str) -> None:
    print(
        f"{Fore.GREEN}[ OK ]"
        f"{Style.RESET_ALL} "
        f"{text}"
    )


def warn(text: str) -> None:
    print(
        f"{Fore.YELLOW}[WARN]"
        f"{Style.RESET_ALL} "
        f"{text}"
    )


def bad(text: str) -> None:
    print(
        f"{Fore.RED}[FAIL]"
        f"{Style.RESET_ALL} "
        f"{text}"
    )


def muted(text: str) -> None:
    print(
        f"{Fore.WHITE}"
        f"{Style.DIM}"
        f"{text}"
        f"{Style.RESET_ALL}"
    )


# =============================================================================
# Proxy models
# =============================================================================

@dataclass(frozen=True)
class Proxy:
    scheme: str
    host: str
    port: int

    @property
    def key(self) -> tuple[str, str, int]:
        return (
            self.scheme,
            self.host,
            self.port,
        )

    @property
    def url(self) -> str:
        return (
            f"{self.scheme}://"
            f"{self.host}:"
            f"{self.port}"
        )

    def requests_dict(
        self,
    ) -> dict[str, str]:

        if self.scheme == "socks5":

            # socks5h makes DNS resolution happen
            # through the SOCKS proxy.
            proxy_url = (
                f"socks5h://"
                f"{self.host}:"
                f"{self.port}"
            )

        else:

            proxy_url = (
                f"http://"
                f"{self.host}:"
                f"{self.port}"
            )

        return {
            "http": proxy_url,
            "https": proxy_url,
        }


@dataclass
class ProxyResult:
    proxy: Proxy
    working: bool
    latency_ms: float = float("inf")
    error: str = ""


# =============================================================================
# Proxy parsing
# =============================================================================

PROXY_RE = re.compile(
    r"^(?:(http|https|socks5|socks5h)://)?"
    r"([^:\s]+):"
    r"(\d{1,5})$",
    re.IGNORECASE,
)


def normalize_scheme(
    value: str,
) -> str:

    value = value.lower()

    if value in {
        "socks5",
        "socks5h",
    }:

        return "socks5"

    # Public proxy lists often call an HTTP CONNECT
    # proxy an "HTTPS proxy".
    return "http"


def parse_proxy(
    value: str,
    default_scheme: str = "http",
) -> Optional[Proxy]:

    value = value.strip()

    if not value:
        return None

    if value.startswith("#"):
        return None

    match = PROXY_RE.fullmatch(
        value
    )

    if not match:
        return None

    raw_scheme = (
        match.group(1)
        or default_scheme
    )

    host = match.group(2)

    try:

        port = int(
            match.group(3)
        )

    except ValueError:

        return None

    if not 1 <= port <= 65535:
        return None

    # Reject malformed addresses/junk.
    try:

        ip = ipaddress.ip_address(
            host
        )

    except ValueError:

        return None

    # Public sources used here contain IPv4.
    if ip.version != 4:
        return None

    return Proxy(
        scheme=normalize_scheme(
            raw_scheme
        ),
        host=str(ip),
        port=port,
    )


def dedupe_proxies(
    proxies: Iterable[Proxy],
) -> list[Proxy]:

    unique: dict[
        tuple[str, str, int],
        Proxy
    ] = {}

    for proxy in proxies:

        unique[
            proxy.key
        ] = proxy

    return list(
        unique.values()
    )


# =============================================================================
# Saved proxies.txt
# =============================================================================

def load_saved_proxies() -> list[Proxy]:

    path = Path(
        PROXY_FILE
    )

    if not path.exists():

        warn(
            f"{PROXY_FILE} "
            f"does not exist yet."
        )

        return []

    try:

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception as exc:

        bad(
            f"Could not read "
            f"{PROXY_FILE}: "
            f"{exc}"
        )

        return []

    proxies: list[Proxy] = []

    for line in text.splitlines():

        proxy = parse_proxy(
            line
        )

        if proxy is not None:

            proxies.append(
                proxy
            )

    proxies = dedupe_proxies(
        proxies
    )

    info(
        f"Loaded "
        f"{len(proxies)} "
        f"unique saved proxies "
        f"from {PROXY_FILE}."
    )

    return proxies


def save_proxy_pool(
    results: list[ProxyResult],
) -> list[ProxyResult]:

    best_by_proxy: dict[
        tuple[str, str, int],
        ProxyResult
    ] = {}

    for result in results:

        if not result.working:
            continue

        current = best_by_proxy.get(
            result.proxy.key
        )

        if (
            current is None
            or result.latency_ms
            < current.latency_ms
        ):

            best_by_proxy[
                result.proxy.key
            ] = result

    working = sorted(
        best_by_proxy.values(),
        key=lambda item: (
            item.latency_ms
        ),
    )

    if (
        MAX_SAVED_WORKING_PROXIES
        is not None
    ):

        working = working[
            :MAX_SAVED_WORKING_PROXIES
        ]

    body = "\n".join(
        result.proxy.url
        for result in working
    )

    if body:
        body += "\n"

    Path(
        PROXY_FILE
    ).write_text(
        body,
        encoding="utf-8",
    )

    good(
        f"Saved "
        f"{len(working)} "
        f"validated proxies "
        f"to {PROXY_FILE}."
    )

    return working


# =============================================================================
# Proxy harvesting
# =============================================================================

def fetch_proxy_source(
    name: str,
    default_scheme: str,
    url: str,
) -> list[Proxy]:

    try:

        response = requests.get(
            url,
            timeout=SOURCE_TIMEOUT,
            headers=HEADERS,
        )

        response.raise_for_status()

    except Exception as exc:

        bad(
            f"{name}: "
            f"{exc}"
        )

        return []

    proxies: list[Proxy] = []

    for line in (
        response.text.splitlines()
    ):

        proxy = parse_proxy(
            line,
            default_scheme=default_scheme,
        )

        if proxy is not None:

            proxies.append(
                proxy
            )

    proxies = dedupe_proxies(
        proxies
    )

    info(
        f"{name:<22} "
        f"-> "
        f"{len(proxies):>5} "
        f"candidates"
    )

    return proxies


def harvest_proxies() -> list[Proxy]:

    heading(
        "HARVESTING FRESH HTTP / SOCKS5 PROXIES"
    )

    combined: list[Proxy] = []

    workers = min(
        MAX_PROXY_THREADS,
        len(PROXY_SOURCES),
    )

    with ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = {
            executor.submit(
                fetch_proxy_source,
                name,
                scheme,
                url,
            ): name
            for (
                name,
                scheme,
                url,
            )
            in PROXY_SOURCES
        }

        for future in as_completed(
            futures
        ):

            name = futures[
                future
            ]

            try:

                combined.extend(
                    future.result()
                )

            except Exception as exc:

                bad(
                    f"{name}: "
                    f"{exc}"
                )

    combined = dedupe_proxies(
        combined
    )

    info(
        f"{len(combined)} "
        f"total unique fresh "
        f"proxy candidates."
    )

    return combined


# =============================================================================
# Requests session
# =============================================================================

def make_requests_session() -> requests.Session:

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    # Do not inherit machine/system proxy variables.
    session.trust_env = False

    return session


# =============================================================================
# Proxy testing
# =============================================================================

def test_proxy(
    proxy: Proxy,
) -> ProxyResult:

    started = time.perf_counter()

    session = make_requests_session()

    try:

        response = session.get(
            TPB_API,
            params={
                "q": PROXY_TEST_QUERY,
                "cat": "0",
            },
            proxies=(
                proxy.requests_dict()
            ),
            timeout=(
                PROXY_CONNECT_TIMEOUT,
                PROXY_READ_TIMEOUT,
            ),
        )

        latency_ms = (
            time.perf_counter()
            - started
        ) * 1000

        if response.status_code != 200:

            return ProxyResult(
                proxy=proxy,
                working=False,
                latency_ms=latency_ms,
                error=(
                    f"HTTP "
                    f"{response.status_code}"
                ),
            )

        try:

            payload = response.json()

        except ValueError:

            return ProxyResult(
                proxy=proxy,
                working=False,
                latency_ms=latency_ms,
                error="invalid JSON",
            )

        if not isinstance(
            payload,
            list,
        ):

            return ProxyResult(
                proxy=proxy,
                working=False,
                latency_ms=latency_ms,
                error="unexpected JSON",
            )

        return ProxyResult(
            proxy=proxy,
            working=True,
            latency_ms=latency_ms,
        )

    except Exception as exc:

        return ProxyResult(
            proxy=proxy,
            working=False,
            error=str(exc),
        )

    finally:

        session.close()


def test_proxy_batch(
    proxies: list[Proxy],
    label: str,
) -> list[ProxyResult]:

    if not proxies:
        return []

    workers = min(
        MAX_PROXY_THREADS,
        len(proxies),
    )

    info(
        f"Testing "
        f"{len(proxies)} "
        f"{label} proxies "
        f"with "
        f"{workers} "
        f"concurrent threads..."
    )

    results: list[
        ProxyResult
    ] = []

    working_count = 0

    with ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = {
            executor.submit(
                test_proxy,
                proxy,
            ): proxy
            for proxy in proxies
        }

        for future in as_completed(
            futures
        ):

            proxy = futures[
                future
            ]

            try:

                result = (
                    future.result()
                )

            except Exception as exc:

                result = ProxyResult(
                    proxy=proxy,
                    working=False,
                    error=str(exc),
                )

            results.append(
                result
            )

            if result.working:

                working_count += 1

                good(
                    f"{result.proxy.url:<34} "
                    f"{result.latency_ms:>7.0f} ms "
                    f"({working_count} working)"
                )

    return results


def combine_working_results(
    *result_groups: list[ProxyResult],
) -> list[ProxyResult]:

    best: dict[
        tuple[str, str, int],
        ProxyResult
    ] = {}

    for group in result_groups:

        for result in group:

            if not result.working:
                continue

            existing = best.get(
                result.proxy.key
            )

            if (
                existing is None
                or result.latency_ms
                < existing.latency_ms
            ):

                best[
                    result.proxy.key
                ] = result

    return sorted(
        best.values(),
        key=lambda item: (
            item.latency_ms
        ),
    )


# =============================================================================
# Build validated proxy pool
# =============================================================================

def build_validated_proxy_pool() -> list[ProxyResult]:

    heading(
        "CHECKING SAVED PROXIES FIRST"
    )

    saved = load_saved_proxies()

    saved_results: list[
        ProxyResult
    ] = []

    if saved:

        saved_results = (
            test_proxy_batch(
                saved,
                label="saved",
            )
        )

    working = (
        combine_working_results(
            saved_results
        )
    )

    if (
        len(working)
        >= MIN_WORKING_PROXIES
    ):

        good(
            f"{len(working)} "
            f"saved proxies are still usable; "
            f"no fresh harvest required."
        )

        return save_proxy_pool(
            working
        )

    warn(
        f"Only "
        f"{len(working)} "
        f"saved proxies survived. "
        f"Need at least "
        f"{MIN_WORKING_PROXIES}."
    )

    # -------------------------------------------------------------------------
    # Harvest replacements
    # -------------------------------------------------------------------------

    harvested = (
        harvest_proxies()
    )

    # Existing saved entries have already been tested,
    # so do not immediately retest those exact same
    # protocol/IP/port combinations.
    saved_keys = {
        proxy.key
        for proxy in saved
    }

    fresh = [
        proxy
        for proxy in harvested
        if proxy.key not in saved_keys
    ]

    random.shuffle(
        fresh
    )

    info(
        f"{len(fresh)} "
        f"fresh candidates remain "
        f"after removing duplicates "
        f"already present in "
        f"{PROXY_FILE}."
    )

    fresh_results: list[
        ProxyResult
    ] = []

    # -------------------------------------------------------------------------
    # Test fresh candidates in concurrent batches
    # -------------------------------------------------------------------------

    for offset in range(
        0,
        len(fresh),
        PROXY_TEST_BATCH_SIZE,
    ):

        batch = fresh[
            offset:
            offset + PROXY_TEST_BATCH_SIZE
        ]

        heading(
            f"VALIDATING FRESH PROXIES "
            f"{offset + 1}-"
            f"{offset + len(batch)} "
            f"OF {len(fresh)}"
        )

        batch_results = (
            test_proxy_batch(
                batch,
                label="fresh",
            )
        )

        fresh_results.extend(
            batch_results
        )

        working = (
            combine_working_results(
                saved_results,
                fresh_results,
            )
        )

        info(
            f"Current validated pool: "
            f"{len(working)} "
            f"(minimum required: "
            f"{MIN_WORKING_PROXIES})"
        )

        if (
            len(working)
            >= MIN_WORKING_PROXIES
        ):

            break

    working = (
        combine_working_results(
            saved_results,
            fresh_results,
        )
    )

    working = save_proxy_pool(
        working
    )

    if (
        len(working)
        < MIN_WORKING_PROXIES
    ):

        bad(
            f"Only "
            f"{len(working)} "
            f"working proxies were found."
        )

        bad(
            f"At least "
            f"{MIN_WORKING_PROXIES} "
            f"are required."
        )

        bad(
            "Searches will NOT start."
        )

        raise SystemExit(1)

    good(
        f"Proxy pool ready: "
        f"{len(working)} "
        f"working proxies "
        f"(minimum "
        f"{MIN_WORKING_PROXIES})."
    )

    return working


# =============================================================================
# Rotating search proxy session
# =============================================================================

class RotatingProxySession:

    def __init__(
        self,
        proxy_results: list[ProxyResult],
    ):

        self.proxy_results = list(
            proxy_results
        )

        self.index = 0

        self.failures: dict[
            tuple[str, str, int],
            int
        ] = {}

        self.disabled: set[
            tuple[str, str, int]
        ] = set()

        self.session = (
            make_requests_session()
        )

    def close(self) -> None:

        self.session.close()

    def _next_proxy(
        self,
    ) -> Optional[Proxy]:

        if not self.proxy_results:
            return None

        checked = 0

        while (
            checked
            < len(self.proxy_results)
        ):

            result = self.proxy_results[
                self.index
                % len(self.proxy_results)
            ]

            self.index += 1
            checked += 1

            if (
                result.proxy.key
                not in self.disabled
            ):

                return result.proxy

        return None

    def _record_failure(
        self,
        proxy: Proxy,
    ) -> None:

        count = (
            self.failures.get(
                proxy.key,
                0,
            )
            + 1
        )

        self.failures[
            proxy.key
        ] = count

        if (
            count
            >= MAX_PROXY_FAILURES_BEFORE_DISABLE
        ):

            self.disabled.add(
                proxy.key
            )

            warn(
                f"Disabled "
                f"{proxy.url} "
                f"after "
                f"{count} "
                f"search failures."
            )

    def active_count(
        self,
    ) -> int:

        return sum(
            1
            for result
            in self.proxy_results
            if (
                result.proxy.key
                not in self.disabled
            )
        )

    def get(
        self,
        url: str,
        **kwargs,
    ) -> requests.Response:

        kwargs.setdefault(
            "timeout",
            (
                PROXY_CONNECT_TIMEOUT,
                SEARCH_TIMEOUT,
            ),
        )

        last_error: Optional[
            Exception
        ] = None

        attempts = min(
            MAX_PROXY_ATTEMPTS_PER_QUERY,
            max(
                1,
                self.active_count(),
            ),
        )

        for _ in range(
            attempts
        ):

            proxy = (
                self._next_proxy()
            )

            if proxy is None:
                break

            try:

                response = (
                    self.session.get(
                        url,
                        proxies=(
                            proxy
                            .requests_dict()
                        ),
                        **kwargs,
                    )
                )

                # Rotate away from obvious blocks,
                # rate limits and proxy/server errors.
                if (
                    response.status_code
                    in {
                        403,
                        407,
                        408,
                        425,
                        429,
                    }
                    or response.status_code
                    >= 500
                ):

                    self._record_failure(
                        proxy
                    )

                    continue

                return response

            except (
                requests.RequestException
            ) as exc:

                last_error = exc

                self._record_failure(
                    proxy
                )

        if last_error is not None:

            raise requests.RequestException(
                "All attempted proxies "
                "failed; last error: "
                f"{last_error}"
            )

        raise requests.RequestException(
            "No active proxy could "
            "complete the request."
        )


# =============================================================================
# Magnet generation
# =============================================================================

def build_magnet(
    info_hash: str,
    name: str,
) -> str:

    return (
        "magnet:?xt=urn:btih:"
        + info_hash
        + "&dn="
        + quote(
            name,
            safe="",
        )
    )


def parse_int(
    value: object,
) -> int:

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return 0


# =============================================================================
# Search API
# =============================================================================

def search_tpb(
    session: RotatingProxySession,
    query: str,
) -> list[dict]:

    response = session.get(
        TPB_API,
        params={
            "q": query,
            "cat": "0",
        },
    )

    response.raise_for_status()

    try:

        data = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "Search endpoint returned "
            "invalid JSON."
        ) from exc

    if not isinstance(
        data,
        list,
    ):

        raise RuntimeError(
            "Search endpoint returned "
            "an unexpected response."
        )

    if not data:
        return []

    first = data[0]

    # TPB API no-results response.
    if isinstance(
        first,
        dict,
    ):

        first_id = str(
            first.get(
                "id",
                "",
            )
        ).strip()

        first_name = str(
            first.get(
                "name",
                "",
            )
        ).strip().lower()

        if (
            first_id == "0"
            or first_name
            == "no results returned"
        ):

            return []

    results: list[
        dict
    ] = []

    for item in data:

        if not isinstance(
            item,
            dict,
        ):

            continue

        name = str(
            item.get(
                "name",
                "",
            )
        ).strip()

        info_hash = str(
            item.get(
                "info_hash",
                "",
            )
        ).strip().upper()

        if not name:
            continue

        # BTIH SHA-1 hashes should be
        # exactly 40 hexadecimal characters.
        if not re.fullmatch(
            r"[A-F0-9]{40}",
            info_hash,
        ):

            continue

        seeders = parse_int(
            item.get(
                "seeders"
            )
        )

        leechers = parse_int(
            item.get(
                "leechers"
            )
        )

        size = parse_int(
            item.get(
                "size"
            )
        )

        results.append(
            {
                "name": name,
                "seeders": seeders,
                "leechers": leechers,
                "size": size,
                "is_hq": bool(
                    QUALITY_RE.search(
                        name
                    )
                ),
                "magnet": build_magnet(
                    info_hash,
                    name,
                ),
            }
        )

    return results


# =============================================================================
# Select best result
# =============================================================================

def pick_best(
    results: list[dict],
) -> Optional[dict]:

    # First preference:
    # recognised HD/HQ release with seeds.
    preferred = [
        result
        for result in results
        if (
            result["is_hq"]
            and result["seeders"]
            >= MIN_SEEDERS
        )
    ]

    if preferred:

        return max(
            preferred,
            key=lambda result: (
                result["seeders"],
                result["leechers"],
            ),
        )

    # Fallback:
    # most seeded result available.
    seeded = [
        result
        for result in results
        if (
            result["seeders"]
            >= MIN_SEEDERS
        )
    ]

    if seeded:

        return max(
            seeded,
            key=lambda result: (
                result["seeders"],
                result["leechers"],
            ),
        )

    return None


# =============================================================================
# Query input
# =============================================================================

def load_queries() -> list[str]:

    path = Path(
        INPUT_FILE
    )

    if not path.exists():

        bad(
            f"{INPUT_FILE} "
            f"was not found."
        )

        raise SystemExit(1)

    try:

        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )

    except Exception as exc:

        bad(
            f"Could not read "
            f"{INPUT_FILE}: "
            f"{exc}"
        )

        raise SystemExit(1)

    queries: list[
        str
    ] = []

    for line in (
        text.splitlines()
    ):

        value = (
            line.strip()
        )

        if not value:
            continue

        if value.startswith(
            "#"
        ):
            continue

        queries.append(
            value
        )

    if not queries:

        bad(
            f"No queries were "
            f"found in "
            f"{INPUT_FILE}."
        )

        raise SystemExit(1)

    return queries


# =============================================================================
# Output
# =============================================================================

def write_lines(
    path: str,
    lines: list[str],
) -> None:

    body = "\n".join(
        lines
    )

    if body:
        body += "\n"

    Path(
        path
    ).write_text(
        body,
        encoding="utf-8",
    )


def save_outputs(
    magnets: list[str],
    failed: list[str],
) -> None:

    # magnets.txt:
    # magnet links ONLY.
    write_lines(
        OUTPUT_FILE,
        magnets,
    )

    # failed.txt:
    # failed query names ONLY.
    write_lines(
        FAILED_FILE,
        failed,
    )


# =============================================================================
# Search runner
# =============================================================================

def run_searches(
    proxy_pool: list[ProxyResult],
) -> None:

    queries = load_queries()

    heading(
        f"SEARCHING "
        f"{len(queries)} "
        f"QUERIES"
    )

    info(
        f"Starting with "
        f"{len(proxy_pool)} "
        f"validated proxies."
    )

    info(
        f"Up to "
        f"{MAX_PROXY_ATTEMPTS_PER_QUERY} "
        f"different proxies may be "
        f"tried per query."
    )

    rotating_session = (
        RotatingProxySession(
            proxy_pool
        )
    )

    magnets: list[
        str
    ] = []

    failed: list[
        str
    ] = []

    seen_magnets: set[
        str
    ] = set()

    seen_failed: set[
        str
    ] = set()

    try:

        for (
            number,
            query,
        ) in enumerate(
            queries,
            start=1,
        ):

            print()

            print(
                Fore.WHITE
                + Style.BRIGHT
                + (
                    f"[{number}/"
                    f"{len(queries)}] "
                    f"{query}"
                )
                + Style.RESET_ALL
            )

            try:

                results = search_tpb(
                    rotating_session,
                    query,
                )

                # -------------------------------------------------------------
                # No results
                # -------------------------------------------------------------

                if not results:

                    warn(
                        "No results."
                    )

                    if (
                        query
                        not in seen_failed
                    ):

                        failed.append(
                            query
                        )

                        seen_failed.add(
                            query
                        )

                    save_outputs(
                        magnets,
                        failed,
                    )

                    continue

                # -------------------------------------------------------------
                # Pick result
                # -------------------------------------------------------------

                selected = pick_best(
                    results
                )

                if selected is None:

                    warn(
                        "Results found, "
                        "but none met "
                        "the minimum "
                        "seeder requirement."
                    )

                    if (
                        query
                        not in seen_failed
                    ):

                        failed.append(
                            query
                        )

                        seen_failed.add(
                            query
                        )

                    save_outputs(
                        magnets,
                        failed,
                    )

                    continue

                magnet = selected[
                    "magnet"
                ]

                # -------------------------------------------------------------
                # Save magnet only
                # -------------------------------------------------------------

                if (
                    magnet
                    not in seen_magnets
                ):

                    magnets.append(
                        magnet
                    )

                    seen_magnets.add(
                        magnet
                    )

                good(
                    f"{selected['name']} "
                    f"("
                    f"{selected['seeders']} "
                    f"seeds)"
                )

                muted(
                    f"Active proxies "
                    f"remaining: "
                    f"{rotating_session.active_count()}"
                )

                # Save after EVERY successful query.
                save_outputs(
                    magnets,
                    failed,
                )

            except KeyboardInterrupt:

                raise

            except Exception as exc:

                bad(
                    f"Search failed: "
                    f"{exc}"
                )

                if (
                    query
                    not in seen_failed
                ):

                    failed.append(
                        query
                    )

                    seen_failed.add(
                        query
                    )

                # Save immediately if this query fails.
                save_outputs(
                    magnets,
                    failed,
                )

            # -------------------------------------------------------------
            # Delay between searches
            # -------------------------------------------------------------

            if number < len(
                queries
            ):

                time.sleep(
                    REQUEST_DELAY
                    + random.uniform(
                        0.0,
                        0.5,
                    )
                )

    except KeyboardInterrupt:

        print()

        warn(
            "Interrupted by user. "
            "Saving current progress."
        )

    finally:

        rotating_session.close()

        save_outputs(
            magnets,
            failed,
        )

    # =========================================================================
    # Summary
    # =========================================================================

    heading(
        "FINISHED"
    )

    good(
        f"{len(magnets)} "
        f"magnet links -> "
        f"{OUTPUT_FILE}"
    )

    if failed:

        warn(
            f"{len(failed)} "
            f"failed queries -> "
            f"{FAILED_FILE}"
        )

    else:

        good(
            f"0 failed queries -> "
            f"{FAILED_FILE}"
        )

    info(
        f"{rotating_session.active_count()} "
        f"proxies remained active "
        f"at the end of the run."
    )


# =============================================================================
# Main
# =============================================================================

def main() -> None:

    heading(
        "TPB MAGNET FINDER v7"
    )

    info(
        f"Proxy validation threads : "
        f"{MAX_PROXY_THREADS}"
    )

    info(
        f"Minimum working proxies  : "
        f"{MIN_WORKING_PROXIES}"
    )

    info(
        f"Saved proxy file         : "
        f"{PROXY_FILE}"
    )

    info(
        f"Input queries            : "
        f"{INPUT_FILE}"
    )

    info(
        f"Magnet output            : "
        f"{OUTPUT_FILE}"
    )

    info(
        f"Failed-query output      : "
        f"{FAILED_FILE}"
    )

    # =========================================================================
    # Build/test proxy pool first
    # =========================================================================

    proxy_pool = (
        build_validated_proxy_pool()
    )

    # Final guard:
    # searches can NEVER begin below the required minimum.
    if (
        len(proxy_pool)
        < MIN_WORKING_PROXIES
    ):

        bad(
            f"Proxy pool contains "
            f"only "
            f"{len(proxy_pool)} "
            f"working proxies."
        )

        bad(
            f"{MIN_WORKING_PROXIES} "
            f"are required."
        )

        raise SystemExit(1)

    # =========================================================================
    # Start searches
    # =========================================================================

    run_searches(
        proxy_pool
    )


if __name__ == "__main__":
    main()
