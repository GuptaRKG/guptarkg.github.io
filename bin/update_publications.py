#!/usr/bin/env python3
"""Propose new publications and refresh bibliometrics for the site.

1. Lists the journal articles on the public ORCID record.
2. Fetches Crossref metadata for DOIs missing from _bibliography/papers.bib and
   appends them as BibTeX entries.
3. Reads h-index, i10-index and citation totals from OpenAlex into _data/metrics.yml
   (needs the OPENALEX_API_KEY environment variable; skipped when absent).

Only three hosts are contacted (ORCID, Crossref, OpenAlex), over HTTPS. Changes are
written to the working tree only; the GitHub workflow opens a pull request so that
every new entry is reviewed before it is published. Standard library only.
"""
import datetime
import html
import json
import os
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ORCID = "0009-0005-6077-3122"
BIB = pathlib.Path("_bibliography/papers.bib")
METRICS = pathlib.Path("_data/metrics.yml")
PR_BODY = pathlib.Path("pr_body.md")
ALLOWED_HOSTS = {"pub.orcid.org", "api.crossref.org", "api.openalex.org"}
STOP = {"the", "a", "an", "of", "for", "and", "in", "on", "to", "with", "from", "by", "via", "using"}


def user_agent():
    contact = os.environ.get("CONTACT_EMAIL", "").strip()  # optional; enables Crossref's polite pool
    return "site-publication-updater/1.0" + (f" (mailto:{contact})" if contact else "")


def http_json(url, tries=3):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise RuntimeError(f"blocked request to {parsed.hostname}")
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"request to {parsed.hostname} failed: {type(last).__name__}")


def orcid_dois():
    data = http_json(f"https://pub.orcid.org/v3.0/{ORCID}/works")
    dois = []
    for group in data.get("group", []):
        summaries = group.get("work-summary", [])
        if not summaries or summaries[0].get("type") != "journal-article":
            continue
        for ext in group.get("external-ids", {}).get("external-id", []):
            if ext.get("external-id-type") == "doi" and ext.get("external-id-value"):
                doi = ext["external-id-value"].strip().lower()
                doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
                if doi not in dois:
                    dois.append(doi)
                break
    return dois


def existing(bib_text):
    dois = {d.strip().lower() for d in re.findall(r"doi\s*=\s*[{\"]([^}\"]+)", bib_text)}
    keys = set(re.findall(r"@\w+\{([^,\s]+),", bib_text))
    return dois, keys


def ascii_lower(text):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower())


def tex(text):
    text = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace("&", r"\&").replace("%", r"\%")


def build_entry(doi, keys):
    msg = http_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")["message"]
    if msg.get("type") != "journal-article":
        return None, f"type is '{msg.get('type')}', not journal-article"
    authors = msg.get("author") or []
    if not authors or not msg.get("title"):
        return None, "Crossref record lacks authors or title"
    parts = msg.get("issued", {}).get("date-parts") or msg.get("published", {}).get("date-parts") or [[None]]
    year = parts[0][0]
    if not year:
        return None, "Crossref record lacks a year"
    names = []
    for a in authors:
        if a.get("family"):
            names.append(f"{a['family']}, {a.get('given', '')}".rstrip(", "))
        elif a.get("name"):
            names.append("{" + a["name"] + "}")
    title = tex(msg["title"][0])
    word = next((w for w in re.findall(r"[A-Za-z]+", title) if w.lower() not in STOP and len(w) > 3), "paper")
    base = f"{ascii_lower(authors[0].get('family') or authors[0].get('name', 'anon'))}{year}{ascii_lower(word)}"
    key, n = base, 2
    while key in keys:
        key, n = f"{base}{n}", n + 1
    keys.add(key)
    journal = tex((msg.get("container-title") or [""])[0])
    abbr = tex((msg.get("short-container-title") or [journal])[0] or journal)
    fields = [("abbr", abbr), ("title", title), ("author", " and ".join(names)), ("journal", journal)]
    if msg.get("volume"):
        fields.append(("volume", msg["volume"]))
    if msg.get("issue"):
        fields.append(("number", msg["issue"]))
    pages = msg.get("page") or msg.get("article-number")
    if pages:
        fields.append(("pages", str(pages).replace("-", "--")))
    fields += [("year", str(year)), ("doi", msg.get("DOI", doi))]
    body = ",\n".join(f"  {k:<8} = {{{v}}}" for k, v in fields)
    return key, f"@article{{{key},\n{body}\n}}\n", title


def update_bib():
    text = BIB.read_text(encoding="utf-8")
    have_dois, keys = existing(text)
    added, skipped = [], []
    for doi in orcid_dois():
        if doi in have_dois:
            continue
        try:
            result = build_entry(doi, keys)
        except Exception as exc:
            skipped.append((doi, str(exc)))
            continue
        if result[0] is None:
            skipped.append((doi, result[1]))
            continue
        _key, entry, title = result
        text = text.rstrip("\n") + "\n\n" + entry
        added.append((doi, title))
    if added:
        total = len(re.findall(r"^@article\{", text, re.M))
        text = re.sub(r"(Complete journal publications \()\d+(\))", rf"\g<1>{total}\2", text, count=1)
        BIB.write_text(text, encoding="utf-8")
    return added, skipped


def update_metrics():
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if not key:
        return None, "OPENALEX_API_KEY is not set; metrics were not refreshed."
    url = f"https://api.openalex.org/authors/orcid:{ORCID}?api_key={urllib.parse.quote(key)}"
    try:
        data = http_json(url)
    except Exception as exc:
        return None, f"OpenAlex request failed ({exc})."
    stats = data.get("summary_stats", {})
    values = {
        "works_count": data.get("works_count"),
        "cited_by_count": data.get("cited_by_count"),
        "h_index": stats.get("h_index"),
        "i10_index": stats.get("i10_index"),
    }
    body = "".join(f"{k}: {v}\n" for k, v in values.items())
    previous = METRICS.read_text(encoding="utf-8") if METRICS.exists() else ""
    old_body = "".join(l + "\n" for l in previous.splitlines() if l.split(":")[0] in values)
    if body == old_body:
        return None, "OpenAlex metrics unchanged."
    header = (
        "# Generated by bin/update_publications.py from OpenAlex. Do not edit by hand.\n"
        "# OpenAlex counts differ from Google Scholar; compare before quoting them.\n"
        f"updated: {datetime.date.today().isoformat()}\nsource: OpenAlex\n"
    )
    METRICS.write_text(header + body, encoding="utf-8")
    return values, "OpenAlex metrics refreshed."


def main():
    added, skipped = update_bib()
    metrics, metrics_note = update_metrics()
    lines = ["Automated fortnightly update (ORCID, Crossref, OpenAlex). Review before merging.\n"]
    if added:
        lines.append("### New publications added to `_bibliography/papers.bib`\n")
        lines += [f"- {t} (https://doi.org/{d})" for d, t in added]
        lines.append("\nCheck author names, journal abbreviation and capitalization of each entry. "
                     "Add `selected = {true}` or a `preview` image where wanted.\n")
    if skipped:
        lines.append("### Skipped\n")
        lines += [f"- {d}: {why}" for d, why in skipped]
        lines.append("")
    lines.append("### Metrics\n")
    lines.append(f"- {metrics_note}")
    if metrics:
        lines += [f"- {k}: {v}" for k, v in metrics.items()]
    PR_BODY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(PR_BODY.read_text())
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"changed={'true' if (added or metrics) else 'false'}\n")


if __name__ == "__main__":
    sys.exit(main())
