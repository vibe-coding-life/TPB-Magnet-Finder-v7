# TPB Magnet Finder v7

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![Proxy Support](https://img.shields.io/badge/Proxy-HTTP%20%7C%20SOCKS5-green)
![Status](https://img.shields.io/badge/Status-Active-success)

TPB Magnet Finder v7 is a Python command-line utility for processing a large list of media search queries and automatically collecting suitable magnet links.

## Why?

The main purpose of TPB Magnet Finder v7 is simple:

**instead of manually searching for every title, opening each result, copying each magnet link, and adding them to qBittorrent one by one, you can give the script your entire list and let it generate a clean `magnets.txt` file containing all of the magnet links.**

You can then simply import the entire contents of `magnets.txt` into **qBittorrent** and add all of the downloads at once.

The intended workflow is:

```text
Add titles to queries.txt
        |
        v
Run TPB Magnet Finder v7
        |
        v
Automatically find suitable results
        |
        v
Generate magnets.txt
        |
        v
Import all magnet links into qBittorrent
        |
        v
Download everything without adding each title manually
```

This is particularly useful when working with dozens or hundreds of authorised downloads where manually searching for and adding every individual magnet would be repetitive and time-consuming.

> **Use this tool only for content you are legally authorised to access, including public-domain media, freely licensed releases, open-source distributions, personal content, and other material you have permission to download.**

---

# Features

* Bulk query processing from `queries.txt`
* Generates a qBittorrent-ready list of magnet links
* Clean magnet-only output
* Import many magnet links into qBittorrent at once
* Separate failed-query tracking
* HTTP proxy support
* SOCKS5 proxy support
* Up to 50 concurrent proxy validation threads
* Persistent proxy pool via `proxies.txt`
* Existing proxies tested before fresh harvesting
* Automatic proxy harvesting
* Proxy deduplication
* Proxy latency measurement
* Configurable minimum working proxy count
* Proxy rotation during searches
* Automatic disabling of repeatedly failing proxies
* Quality-aware result selection
* Seeder-based fallback selection
* Duplicate magnet prevention
* Automatic progress saving
* Colorama-powered terminal output

---

# How It Works

TPB Magnet Finder v7 reads each non-empty line in:

```text
queries.txt
```

as a separate search query.

For example:

```text
Example Movie (2004)
Another Example (2010)
Public Domain Film (1955)
Another Title (1997)
```

For each query, the script:

1. Sends the search through a validated proxy.
2. Parses the returned results.
3. Looks for a suitable quality release.
4. Prefers results with active seeders.
5. Generates the corresponding magnet URI.
6. Writes the magnet link to `magnets.txt`.
7. Writes unsuccessful searches to `failed.txt`.

Once the script has finished, `magnets.txt` can be imported into qBittorrent rather than manually adding every result individually.

---

# qBittorrent Workflow

The output format is deliberately designed to make bulk importing easy.

After TPB Magnet Finder v7 finishes, open:

```text
magnets.txt
```

The file contains one magnet URI per line:

```text
magnet:?xt=urn:btih:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX&dn=Example
magnet:?xt=urn:btih:YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY&dn=Example2
magnet:?xt=urn:btih:ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ&dn=Example3
```

You can copy or import these links into qBittorrent in bulk.

This removes the repetitive process of:

```text
Search title
-> open result
-> click magnet
-> add to qBittorrent
-> search next title
-> repeat
```

Instead:

```text
Prepare queries.txt
-> run script
-> import magnets.txt
-> done
```

---

# Output Files

## `magnets.txt`

Contains **only magnet URIs**.

One magnet per line.

```text
magnet:?xt=urn:btih:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX&dn=Example
magnet:?xt=urn:btih:YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY&dn=Example2
```

No search-query names, comments, tabs, status messages, or additional metadata are written to the file.

This makes `magnets.txt` suitable for bulk importing into applications such as qBittorrent.

---

## `failed.txt`

Contains queries that could not be successfully processed.

One query per line.

```text
Example Movie (2004)
Another Example (2012)
Unknown Title (1998)
```

This makes it easy to see which searches need to be retried or manually checked.

---

## `proxies.txt`

Contains validated HTTP and SOCKS5 proxies.

Example:

```text
http://1.2.3.4:8080
socks5://5.6.7.8:1080
http://9.10.11.12:3128
```

Only validated proxies are retained.

---

# Proxy System

One of the main features of TPB Magnet Finder v7 is its integrated proxy management system.

Before any searches begin, the program builds a healthy pool of working proxies.

---

## Saved Proxies Are Tested First

When the program starts, it checks for:

```text
proxies.txt
```

If the file exists, those proxies are loaded first.

They are:

* parsed
* normalized
* deduplicated
* validated
* measured for latency
* sorted by response speed

Dead proxies are discarded automatically.

If enough previously saved proxies still work, fresh proxy harvesting can be skipped entirely.

---

# Automatic Proxy Harvesting

If too few saved proxies survive validation, TPB Magnet Finder v7 automatically retrieves fresh candidates from multiple public proxy sources.

Both:

```text
HTTP
SOCKS5
```

are supported.

Candidate lists are combined and duplicates are removed before testing.

The program understands proxy formats such as:

```text
1.2.3.4:8080
```

as well as:

```text
http://1.2.3.4:8080
socks5://1.2.3.4:1080
```

---

# Multithreaded Proxy Validation

Public proxy lists often contain hundreds or thousands of endpoints, many of which are dead or unreliable.

Testing them sequentially would be extremely slow.

TPB Magnet Finder v7 therefore validates proxies concurrently.

By default:

```text
50 proxy-checking threads
```

can operate simultaneously.

This value can be changed in the configuration section of the script.

---

# Minimum Working Proxy Requirement

TPB Magnet Finder v7 will not begin processing search queries until a minimum number of working proxies has been validated.

Default:

```text
25 working proxies
```

Startup flow:

```text
Load proxies.txt
        |
        v
Deduplicate proxies
        |
        v
Test saved proxies
        |
        v
25+ working?
   |           |
  Yes          No
   |            |
   v            v
Continue    Harvest fresh proxies
                |
                v
          Deduplicate candidates
                |
                v
          Test with up to
             50 threads
                |
                v
          25+ working?
                |
                v
          Begin searches
```

If the minimum cannot be reached, the script exits before processing searches.

---

# Proxy Persistence

Once validation finishes, working proxies are saved back to:

```text
proxies.txt
```

They are stored fastest-first.

On the next run, this saved pool is checked before new proxy sources are contacted.

This allows working proxies to be reused between sessions.

---

# Proxy Rotation

Searches are distributed across the validated proxy pool.

If a proxy starts returning connection errors, rate limits, or server failures, the request can be retried using another validated proxy.

Proxies that repeatedly fail can be disabled for the remainder of the current run.

This prevents one unreliable endpoint from repeatedly delaying every subsequent search.

---

# Result Selection

When several results are returned, TPB Magnet Finder v7 attempts to choose a suitable release automatically.

It recognises common quality indicators including:

```text
1080p
1440p
2160p
4K
UHD
HDR
HDR10
Dolby Vision
REMUX
BluRay
BRRip
WEB-DL
WEBRip
```

Seeded results containing recognised quality indicators are preferred.

If no preferred-quality result is available, the script can fall back to another sufficiently seeded result.

---

# Duplicate Handling

Duplicate removal happens at multiple stages.

## Proxy Deduplication

Proxies are deduplicated using:

```text
protocol + IP address + port
```

This prevents the same endpoint from being unnecessarily tested multiple times.

## Magnet Deduplication

Generated magnet links are tracked during the current run.

The same magnet will not be written to `magnets.txt` more than once.

---

# Progress Saving

TPB Magnet Finder v7 saves progress throughout execution.

After successful and failed searches, the current contents of:

```text
magnets.txt
failed.txt
```

are updated.

If the script is interrupted using `Ctrl+C`, previously completed results remain saved.

---

# Coloured Terminal Output

The script uses `colorama` to make command-line output easier to follow.

Different colours are used for:

* successful operations
* information
* warnings
* failures
* proxy validation
* completed searches

This is especially useful during large proxy-validation runs.

---

# Requirements

* Python 3.10+
* `requests`
* `PySocks`
* `colorama`

---

# Installation

## 1. Install Python

Download Python from:

https://www.python.org/downloads/

On Windows, ensure Python is added to your system PATH during installation.

Verify it with:

```bash
python --version
```

---

## 2. Install Dependencies

Run:

```bash
python -m pip install colorama "requests[socks]"
```

On some Linux/macOS systems:

```bash
python3 -m pip install colorama "requests[socks]"
```

---

# Directory Structure

A typical directory looks like:

```text
TPB-Magnet-Finder/
│
├── tpb_magnet_finder.py
├── queries.txt
├── proxies.txt
├── magnets.txt
└── failed.txt
```

Initially, only these are required:

```text
tpb_magnet_finder.py
queries.txt
```

The remaining files are generated automatically.

---

# Usage

Add one search query per line to:

```text
queries.txt
```

Example:

```text
Example Movie (2004)
Another Example (2010)
Public Domain Film (1955)
```

Run:

```bash
python tpb_magnet_finder.py
```

After it completes:

```text
magnets.txt
```

contains the successful magnet links.

Import those links into qBittorrent and add the downloads in bulk instead of manually searching for and adding every title separately.

---

# Startup Process

When launched, TPB Magnet Finder v7 performs the following sequence:

```text
1. Load queries.txt
2. Load proxies.txt if it exists
3. Deduplicate saved proxies
4. Validate saved proxies
5. Check whether at least 25 working proxies remain
6. Harvest fresh HTTP/SOCKS5 proxies if required
7. Deduplicate fresh candidates
8. Test proxies with up to 50 threads
9. Save validated proxies to proxies.txt
10. Begin processing queries
11. Rotate requests across the proxy pool
12. Select suitable results
13. Save magnet links to magnets.txt
14. Save unsuccessful queries to failed.txt
15. Preserve progress throughout the run
16. Import magnets.txt into qBittorrent
```

---

# Configuration

Important settings are located near the top of the Python script.

| Setting                             | Purpose                                                            |
| ----------------------------------- | ------------------------------------------------------------------ |
| `MIN_WORKING_PROXIES`               | Minimum number of validated proxies required before searches start |
| `MAX_PROXY_THREADS`                 | Maximum concurrent proxy-validation threads                        |
| `PROXY_TEST_BATCH_SIZE`             | Number of fresh proxies tested in each batch                       |
| `MAX_SAVED_WORKING_PROXIES`         | Maximum number of validated proxies retained                       |
| `PROXY_CONNECT_TIMEOUT`             | Maximum proxy connection time                                      |
| `PROXY_READ_TIMEOUT`                | Maximum proxy response wait time                                   |
| `SEARCH_TIMEOUT`                    | Timeout for search requests                                        |
| `MIN_SEEDERS`                       | Minimum number of seeders required                                 |
| `REQUEST_DELAY`                     | Delay between search queries                                       |
| `MAX_PROXY_ATTEMPTS_PER_QUERY`      | Maximum proxy attempts for a single query                          |
| `MAX_PROXY_FAILURES_BEFORE_DISABLE` | Failures before a proxy is disabled for the current run            |

Example:

```python
MIN_WORKING_PROXIES = 25
MAX_PROXY_THREADS = 50
MIN_SEEDERS = 1
```

---

# Example Console Output

```text
============================================================================
TPB MAGNET FINDER v7
============================================================================

[INFO] Proxy validation threads : 50
[INFO] Minimum working proxies  : 25
[INFO] Saved proxy file         : proxies.txt
[INFO] Input queries            : queries.txt
[INFO] Magnet output            : magnets.txt
[INFO] Failed-query output      : failed.txt

============================================================================
CHECKING SAVED PROXIES FIRST
============================================================================

[INFO] Loaded 42 unique saved proxies from proxies.txt.
[ OK ] http://1.2.3.4:8080              341 ms
[ OK ] socks5://5.6.7.8:1080            488 ms
[ OK ] http://9.10.11.12:3128           522 ms

[ OK ] Proxy pool ready: 31 working proxies.

============================================================================
SEARCHING 20 QUERIES
============================================================================

[1/20] Example Movie (2004)
[ OK ] Example Movie 2004 1080p BluRay (132 seeds)

[2/20] Another Example (2010)
[ OK ] Another Example 2010 WEB-DL (84 seeds)
```

Actual results vary depending on network conditions, search results, and proxy availability.

---

# Troubleshooting

## `python is not recognized`

Python is either not installed or has not been added to PATH.

Install Python from:

https://www.python.org/downloads/

Then restart Command Prompt or PowerShell.

---

## `pip is not recognized`

Use:

```bash
python -m pip install colorama "requests[socks]"
```

instead of calling `pip` directly.

---

## SOCKS Proxy Errors

Make sure PySocks is installed:

```bash
python -m pip install "requests[socks]"
```

---

## Fewer Than 25 Proxies Are Found

Public proxies are inherently unreliable and frequently disappear.

Possible options include:

* run the script again later
* add additional proxy sources
* increase proxy timeouts
* lower `MIN_WORKING_PROXIES`
* use a private proxy provider

---

## Searches Do Not Start

The script intentionally refuses to begin searching unless the configured:

```text
MIN_WORKING_PROXIES
```

threshold has been reached.

Check the terminal output to see how many proxies passed validation.

---

# Notes

Public proxies are inherently unreliable.

A proxy working now may become unavailable minutes or hours later. TPB Magnet Finder v7 therefore treats the proxy pool as disposable and rebuildable rather than assuming saved proxies will remain online indefinitely.

Network connection speed is also not the only factor affecting proxy testing. The response time and reliability of individual remote proxies are usually the biggest limitations.

---

# Legal Notice

TPB Magnet Finder v7 is a general-purpose search and automation utility.

It should only be used to access material you are legally authorised to download, such as:

* public-domain media
* freely licensed media
* open-source distributions
* your own uploaded content
* content where explicit download permission has been granted

The user is responsible for ensuring that their use of the software complies with applicable laws and licensing requirements.

---

# License

Add your preferred licence to the repository.

For example:

```text
MIT License
```

If publishing the project publicly, adding a separate `LICENSE` file to the repository is recommended.
