import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# --- CORE vs SUPPORT TERMS ---
# CORE terms must be present to consider a page "spider evidence".
CORE_SPIDER_TERMS = [
    "spider", "spiders",
    "tarantula", "tarantulas",
    "arachnid", "arachnids",
    "acromantula", "acromantulas",
]

# These only count if CORE terms are present (prevents "web" false positives).
SUPPORT_TERMS = [
    "cobweb", "cobwebs",
    "webs", "webbed", "webbing",
]

# Intensity hints (pure heuristic)
SEVERITY_TERMS = {
    "close-up": 3,
    "close up": 3,
    "giant": 2,
    "huge": 2,
    "swarm": 3,
    "nest": 2,
    "crawling": 2,
    "crawls": 2,
    "jump scare": 3,
    "jumpscare": 3,
    "attacks": 2,
    "attack": 2,
    "many spiders": 3,
    "covered in webs": 3,
    "webs everywhere": 3,
}

# Avoid Spider-Man confusion
NEGATIVE_CONTEXT = [
    "spider-man", "spiderman"
]

# Prefer these domains if they show up in results
PREFERRED_DOMAINS = {
    "imdb.com": 5,
    "wikipedia.org": 3,
    "commonsensemedia.org": 3,
    "doesthedogdie.com": 3,
}

USER_AGENT = "Mozilla/5.0 (compatible; SpiderStamp/0.3)"


def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def has_negative_context(text: str) -> bool:
    t = text.lower()
    return any(bad in t for bad in NEGATIVE_CONTEXT)


def extract_hits(text: str) -> tuple[list[str], list[str]]:
    """
    Returns (core_hits, support_hits).
    support_hits is only kept if core_hits exists.
    """
    t = text.lower()
    core_hits = sorted({w for w in CORE_SPIDER_TERMS if w in t})
    support_hits = sorted({w for w in SUPPORT_TERMS if w in t})
    if core_hits:
        return core_hits, support_hits
    return core_hits, []


def extract_context_snippets(text: str, terms: list[str], window: int = 220, max_snips: int = 4) -> list[str]:
    lower = text.lower()
    snippets = []
    for term in terms:
        idx = lower.find(term)
        if idx == -1:
            continue
        start = max(0, idx - window)
        end = min(len(text), idx + len(term) + window)
        snippets.append(text[start:end].strip())
        if len(snippets) >= max_snips:
            break
    return snippets


def severity_score(text: str) -> int:
    t = text.lower()
    s = 0
    for k, w in SEVERITY_TERMS.items():
        if k in t:
            s += w
    return s


def domain_weight(url: str) -> int:
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return 0
    return PREFERRED_DOMAINS.get(host, 0)


def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        if r.status_code != 200:
            return None
        return r.text
    except requests.RequestException:
        return None


def duckduckgo_results(query: str, max_results: int = 8) -> list[dict]:
    """
    Best-effort DuckDuckGo HTML search.
    Returns list of {title, url, snippet}.
    """
    url = "https://duckduckgo.com/html/"
    try:
        r = requests.post(
            url,
            data={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        out = []
        for res in soup.select(".result")[:max_results]:
            a = res.select_one(".result__a")
            snip = res.select_one(".result__snippet")
            if not a:
                continue
            out.append({
                "title": a.get_text(" ", strip=True),
                "url": a.get("href"),
                "snippet": snip.get_text(" ", strip=True) if snip else ""
            })
        return out
    except requests.RequestException:
        return []


def imdb_parental_guide_evidence(imdb_id: str) -> dict:
    url = f"https://www.imdb.com/title/{imdb_id}/parentalguide/"
    html = fetch(url)
    if not html:
        return {
            "source": "imdb_parentalguide",
            "url": url,
            "ok": False,
            "core_hits": [],
            "support_hits": [],
            "snippets": [],
            "severity": 0,
        }

    text = clean_text(html)
    core, support = extract_hits(text)

    # If no core hits, treat as no spider evidence (prevents web-only false positives)
    if not core:
        return {
            "source": "imdb_parentalguide",
            "url": url,
            "ok": True,
            "core_hits": [],
            "support_hits": [],
            "snippets": [],
            "severity": 0,
        }

    hits_for_snips = core + support
    snips = extract_context_snippets(text, hits_for_snips)
    sev = severity_score(" ".join(snips)) if snips else 0

    return {
        "source": "imdb_parentalguide",
        "url": url,
        "ok": True,
        "core_hits": core,
        "support_hits": support,
        "snippets": snips,
        "severity": sev,
    }


def search_and_fetch_evidence(movie_title: str, movie_year: str, max_pages: int = 10) -> list[dict]:
    """
    Multi-query search -> pick URLs -> fetch pages -> extract spider evidence.
    ONLY accepts pages with CORE spider terms.
    """
    title = movie_title
    year = movie_year

    queries = [
        f"\"{title}\" {year} spider scene",
        f"\"{title}\" {year} tarantula scene",
        f"\"{title}\" {year} arachnid scene",
        f"\"{title}\" {year} acromantula scene",
        f"\"{title}\" {year} parental guide spider",
        f"\"{title}\" {year} does the dog die spider",
        f"\"{title}\" {year} imdb parental guide spider",
    ]

    raw_results = []
    for q in queries:
        raw_results.extend(duckduckgo_results(q, max_results=6))
        time.sleep(0.2)  # small politeness delay

    # Deduplicate URLs
    seen = set()
    results = []
    for r in raw_results:
        u = r.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        results.append(r)

    # Rank: prefer known domains + core terms in snippet/title; penalize Spider-Man
    def rank(item: dict) -> tuple:
        text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
        core_bonus = 1 if any(t in text for t in CORE_SPIDER_TERMS) else 0
        neg_penalty = 1 if any(b in text for b in NEGATIVE_CONTEXT) else 0
        return (domain_weight(item.get("url", "")), core_bonus, -neg_penalty)

    results.sort(key=rank, reverse=True)

    evidences = []
    for r in results[:max_pages]:
        url = r["url"]
        html = fetch(url)
        if not html:
            continue

        text = clean_text(html)
        core, support = extract_hits(text)

        # 🚨 Key change: skip pages unless CORE terms exist
        if not core:
            continue

        hits_for_snips = core + support
        snips = extract_context_snippets(text, hits_for_snips, window=240, max_snips=4)
        sev = severity_score(" ".join(snips)) + domain_weight(url)

        evidences.append({
            "source": "web_page",
            "url": url,
            "title": r.get("title", ""),
            "core_hits": core,
            "support_hits": support,
            "snippets": snips,
            "severity": sev,
            "negative_context": has_negative_context(text),
        })

    return evidences


def score_confidence(imdb_ev: dict, web_evs: list[dict]) -> tuple[str, int]:
    """
    Score based on:
    - IMDb parental guide CORE hit (strong)
    - multiple independent pages with CORE hits
    - severity language
    """
    score = 0

    # Strong signal: IMDb has core spider terms
    if imdb_ev.get("ok") and imdb_ev.get("core_hits"):
        score += 7
        score += min(3, imdb_ev.get("severity", 0) // 2)

    # Independent evidence count (core-only by construction)
    score += min(6, len(web_evs))

    # Severity language boosts
    sev_sum = sum(e.get("severity", 0) for e in web_evs)
    score += min(6, sev_sum // 3)

    # Penalize Spider-Man confusion a bit
    if any(e.get("negative_context") for e in web_evs):
        score -= 2

    if score >= 12:
        return ("high", score)
    if score >= 6:
        return ("medium", score)
    return ("low", score)


def build_report(movie: dict) -> dict:
    imdb_ev = imdb_parental_guide_evidence(movie["imdb_id"])
    web_evs = search_and_fetch_evidence(movie["title"], movie["year"], max_pages=12)

    confidence, score = score_confidence(imdb_ev, web_evs)

    # Simple severity label
    sev_total = imdb_ev.get("severity", 0) + sum(e.get("severity", 0) for e in web_evs)
    if confidence == "high" and sev_total >= 10:
        severity_label = "spider-heavy"
    elif confidence in ("medium", "high"):
        severity_label = "caution"
    else:
        severity_label = "likely-safe"

    return {
        "movie": movie,
        "confidence": confidence,
        "score": score,
        "severity": severity_label,
        "evidence": [imdb_ev],
        "web_evidence": web_evs,
    }
