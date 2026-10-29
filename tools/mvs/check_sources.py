#!/usr/bin/env python3
"""Re-fetch and verify the predicate source table in a markdown document.

Usage: python3 -I tools/mvs/check_sources.py --doc docs/mvs-media.md \
           --require S1,S2,S3

Every table row whose first cell is S<digits><optional letter> carries:
id | element | url | fetched | raw_sha256 | excerpt_id | excerpt | class

A row passes only when the cited immutable revision is fetched live, its
SHA-256 equals raw_sha256, the whitespace-normalized excerpt occurs in the
whitespace-normalized fetched text, and the fetch date is not earlier than
MIN_FETCHED.  A network failure is a failure, never a skip.  Output names only
S-ids and failure kinds.  Python standard library only.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

MIN_FETCHED = "2026-10-12"
ROW_RE = re.compile(r"^\s*\|\s*(S\d+[A-Za-z]?)\s*\|")
OLDID_RE = re.compile(r"^\d+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
WIKI_HOST = "wiki.neogeodev.org"
RAW_HOST = "raw.githubusercontent.com"
USER_AGENT = "glueyneo-source-check/1"
TIMEOUT = 30


def normalize(text):
    return " ".join(text.split())


def parse_rows(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = ROW_RE.match(line)
            if not match:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append((match.group(1), cells))
    return rows


def http_get(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise OSError("status %d" % response.status)
        return response.read()


def fetch_wiki(query):
    title = query.get("title", [""])[0].replace("_", " ")
    oldid = query.get("oldid", [""])[0]
    if not OLDID_RE.match(oldid):
        return None, "url_not_immutable"
    api = (
        "https://%s/api.php?action=query&prop=revisions&revids=%s"
        "&rvprop=ids|content&rvslots=main&format=json" % (WIKI_HOST, oldid)
    )
    try:
        data = json.loads(http_get(api).decode("utf-8"))
        page = list(data["query"]["pages"].values())[0]
        revision = page["revisions"][0]
        if str(revision["revid"]) != oldid:
            return None, "revid_mismatch"
        if title and page.get("title") != title:
            return None, "title_mismatch"
        content = revision["slots"]["main"]["*"]
    except (OSError, ValueError, KeyError, IndexError, urllib.error.URLError):
        return None, "fetch_failed"
    return content.encode("utf-8"), None


def fetch_raw(parts):
    segments = parts.path.split("/")
    # /<owner>/<repo>/<40-hex commit>/<path...>
    if len(segments) < 5 or not COMMIT_RE.match(segments[3]):
        return None, "url_not_immutable"
    try:
        return http_get(parts.geturl()), None
    except (OSError, urllib.error.URLError):
        return None, "fetch_failed"


def fetch(url, cache):
    if url in cache:
        return cache[url]
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc
    if parts.scheme != "https":
        result = (None, "url_scheme")
    elif host == WIKI_HOST:
        result = fetch_wiki(urllib.parse.parse_qs(parts.query))
    elif host == RAW_HOST:
        result = fetch_raw(parts)
    else:
        result = (None, "url_host")
    cache[url] = result
    return result


def check_row(cells, cache):
    if len(cells) != 8:
        return "columns"
    _id, _element, url, fetched, digest, excerpt_id, excerpt, _cls = cells
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fetched) or fetched < MIN_FETCHED:
        return "fetched_date"
    if not re.match(r"^[0-9a-f]{64}$", digest):
        return "digest_format"
    if not excerpt_id or not excerpt:
        return "empty_cell"
    body, failure = fetch(url, cache)
    if failure:
        return failure
    if hashlib.sha256(body).hexdigest() != digest:
        return "digest_mismatch"
    text = normalize(body.decode("utf-8", errors="replace"))
    if normalize(excerpt) not in text:
        return "excerpt_absent"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", required=True)
    parser.add_argument("--require", required=True)
    args = parser.parse_args()
    required = [r for r in args.require.split(",") if r]
    rows = parse_rows(args.doc)
    cache = {}
    failures = []
    seen = set()
    for sid, cells in rows:
        if sid in seen:
            failures.append((sid, "duplicate"))
        seen.add(sid)
        kind = check_row(cells, cache)
        if kind:
            failures.append((sid, kind))
    for sid in required:
        if sid not in seen:
            failures.append((sid, "missing"))
    for sid, kind in failures:
        print("%s %s" % (sid, kind))
    if failures:
        return 1
    print("sources ok: %d rows" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
