# TPB Magnet Finder v7

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![Proxy Support](https://img.shields.io/badge/Proxy-HTTP%20%7C%20SOCKS5-green)
![Status](https://img.shields.io/badge/Status-Active-success)

TPB Magnet Finder v7 is a Python command-line utility for processing large lists of media search queries and saving suitable magnet URIs into a clean output file.

The script is designed around bulk automation. Add your search terms to `queries.txt`, run the program, and TPB Magnet Finder v7 handles proxy preparation, validation, search processing, result selection, magnet generation, and failed-query tracking automatically.

> **Use this tool only for content you are legally authorised to access, including public-domain media, freely licensed releases, open-source distributions, personal content, and other material you have permission to download.**

---

## Features

* Bulk query processing from `queries.txt`
* Clean magnet-only output
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

## How It Works

TPB Magnet Finder v7 reads each non-empty line in:

```text
queries.txt
```

as a separate search query.

For each query, the script:

1. Sends the search request through a validated proxy.
2. Parses the returned results.
3. Prefers recognised higher-quality releases.
4. Falls back to the most seeded suitable result if required.
5. Builds the magnet URI.
6. Writes the magnet to `magnets.txt`.
7. Writes unsuccessful queries to `failed.txt`.

---

## Output Files

### `magnets.txt`

Contains **only magnet URIs**.

One magnet per line.

```text
magnet:?xt=urn:btih:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX&dn=Example
magnet:?xt=urn:btih:YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY&dn=Example2
```

No movie names, comments, tabs, status messages, or additional metadata are written to this file.

---

### `failed.txt`

Contains queries that could not be successfully processed.

One query per line.

```text
Example Movie (2004)
Another Example (2012)
Unknown Title (1998)
```

This makes failed searches easy to review or retry later.

---

### `proxies.txt`

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

Before any searches begin, the program attempts to build a healthy pool of working proxies.

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

If enough previously saved proxies still work, the program can skip fresh harvesting entirely.

---

## Automatic Proxy Harvesting

If too few saved proxies survive validation, TPB Magnet Finder v7 automatically downloads fresh candidates from multiple public proxy sources.

Both:

```text
HTTP
SOCKS5
```

are supported.

Candidate lists are merged and duplicate entries are removed before testing.

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

## Multithreaded Proxy Validation

Public proxy lists often contain hundreds or thousands of dead endpoints.

Testing them sequentially would be very slow, so TPB Magnet Finder v7 validates proxies concurrently.

By default:

```text
50 proxy-checking threads
```

can run at the same time.

This value can be changed in the configuration section of the script.

---

## Minimum Working Proxy Requirement

The script will not begin search processing until a minimum number of working proxies have been found.

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

If the minimum cannot be reached, the script exits before starting searches.

---

## Proxy Persistence

Once validation finishes, working proxies are saved back to:

```text
proxies.txt
```

They are stored fastest-first.

On the next run, this saved pool is checked before any new proxy sources are contacted.

This allows a working proxy pool to be reused between sessions.

---

## Proxy Rotation

Searches are distributed across the validated proxy pool.

If a proxy starts returning connection errors, rate limits, or server failures, the request can be retried using another validated proxy.

Proxies that repeatedly fail can be disabled for the remainder of the current run.

This prevents one unreliable proxy from repeatedly delaying the search process.

---

# Result Selection

When multiple results are returned, TPB Magnet Finder v7 attempts to choose a useful release automatically.

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

This prevents the same endpoint from being tested repeatedly.

## Magnet Deduplication

Generated magnet links are tracked during the current run.

The same magnet will not be added to `magnets.txt` more than once.

---

# Progress Saving

TPB Magnet Finder v7 saves progress during execution.

After successful and failed searches, the current contents of:

```text
magnets.txt
failed.txt
```

are updated.

If the script is interrupted with `Ctrl+C`, completed results are preserved.

---

# Coloured Terminal Output

The script uses `colorama` to make terminal output easier to read.

Typical status colours are used for:

* successful operations
* informational messages
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

Verify the installation:

```bash
python --version
```

---

## 2. Install Dependencies

Run:

```bash
python -m pip install colorama "requests[socks]"
```

On some systems:

```bash
python3 -m pip install colorama "requests[socks]"
```

---

# Directory Structure

A typical project folder looks like:

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

The other files are created automatically.

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

Then run:

```bash
python tpb_magnet_finder.py
```

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
15. Preserve progress during the run
```

---

# Configuration

Important settings are located near the top of the Python script.

| Setting                             | Purpose                                                            |
| ----------------------------------- | ------------------------------------------------------------------ |
| `MIN_WORKING_PROXIES`               | Minimum number of validated proxies required before searches start |
| `MAX_PROXY_THREADS`                 | Maximum concurrent proxy validation threads                        |
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

Actual results will vary depending on network conditions and proxy availability.

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

## SOCKS proxy errors

Make sure PySocks is installed:

```bash
python -m pip install "requests[socks]"
```

---

## Fewer than 25 proxies are found

Public proxies are unreliable and frequently disappear.

Possible options:

* run the script again later
* add additional proxy sources
* increase proxy timeouts
* lower `MIN_WORKING_PROXIES`
* use a private proxy provider

---

## Searches do not start

The script intentionally refuses to begin searching unless:

```text
MIN_WORKING_PROXIES
```

working proxies have been validated.

Check the console output to see how many working proxies were found.

---

# Notes

Public proxies are inherently unreliable.

A proxy that works today may be unavailable minutes or hours later. Because of this, TPB Magnet Finder v7 continuously treats the proxy pool as disposable and rebuildable rather than assuming saved proxies will remain online permanently.

Network speed alone does not determine how fast proxy validation completes. The response time of the remote proxy servers is usually the main limiting factor.

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

Add the license you want to use for your repository here.

For example:

```text
MIT License
```

If you intend to publish the project publicly, adding a `LICENSE` file to the repository is recommended.
