import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# --- CORE vs SUPPORT TERMS ---
CORE_SPIDER_TERMS = [
       # generic
    "spider",
    "spiders",

    # common spider types
    "tarantula",
    "tarantulas",
    "wolf spider",
    "jumping spider",
    "trapdoor spider",
    "orb weaver",
    "orb-weaver",
    "funnel web spider",
    "funnel-web spider",
    "black widow",
    "brown recluse",

    # scientific / biological
    "arachnid",
    "arachnids",

    # fantasy / movie-specific (important)
    "giant spider",
    "cave spider",
    "forest spider",
    "underground spider",

    # franchise-specific spiders
    "acromantula",
    "acromantulas",
    "aragog",
    "shelob",
    "ungoliant",
    "Aragog",
]

# Only count if CORE terms exist (prevents “web” false positives)
SUPPORT_TERMS = [
    "cobweb", "cobwebs",
    "webs", "webbed", "webbing",
]

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

NEGATIVE_CONTEXT = ["spider-man", "spiderman"]

PREFERRED_DOMAINS = {
    "imdb.com": 5,
    "wikipedia.org": 4,
    "commonsensemedia.org": 3,
    "doesthedogdie.com": 3,
}

USER_AGENT = "Mozilla/5.0 (compatible; SpiderStamp/0.4)"


def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def extract_hits(text: str) -> tuple[list[str], list[str]]:
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
        return {"source": "imdb_parentalguide", "url": url, "ok": False,
                "core_hits": [], "support_hits": [], "snippets": [], "severity": 0}

    text = clean_text(html)
    core, support = extract_hits(text)

    # No CORE = treat as no spider evidence
    if not core:
        return {"source": "imdb_parentalguide", "url": url, "ok": True,
                "core_hits": [], "support_hits": [], "snippets": [], "severity": 0}

    hits_for_snips = core + support
    snips = extract_context_snippets(text, hits_for_snips)
    sev = severity_score(" ".join(snips)) if snips else 0

    return {"source": "imdb_parentalguide", "url": url, "ok": True,
            "core_hits": core, "support_hits": support, "snippets": snips, "severity": sev}


def wikipedia_evidence(movie_title: str, movie_year: str) -> dict:
    """
    Wikipedia summary via REST API (no key). Much more stable than scraping.
    """
    candidates = [
        f"{movie_title} (film)",
        f"{movie_title} ({movie_year} film)",
        movie_title,
    ]

    for cand in candidates:
        slug = cand.replace(" ", "_")
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"

        try:
            r = requests.get(api_url, headers={"User-Agent": USER_AGENT}, timeout=20)
            if r.status_code != 200:
                continue
            data = r.json()
        except Exception:
            continue

        extract = (data.get("extract") or "").strip()
        page_url = (data.get("content_urls", {}) or {}).get("desktop", {}).get("page", "")

        if not extract:
            continue

        core, support = extract_hits(extract)
        if not core:
            return {"source": "wikipedia", "url": page_url, "ok": True,
                    "core_hits": [], "support_hits": [], "snippets": [], "severity": 0}

        hits_for_snips = core + support
        snips = extract_context_snippets(extract, hits_for_snips, window=200, max_snips=3)
        sev = severity_score(" ".join(snips)) + 2  # small trust bonus

        return {"source": "wikipedia", "url": page_url, "ok": True,
                "core_hits": core, "support_hits": support, "snippets": snips, "severity": sev}

    return {"source": "wikipedia", "url": "", "ok": False,
            "core_hits": [], "support_hits": [], "snippets": [], "severity": 0}


def search_and_fetch_evidence(movie_title: str, movie_year: str, max_pages: int = 12) -> list[dict]:
    """
    Multi-query search -> fetch pages -> accept only CORE spider pages.
    """
    queries = [
        f"\"{movie_title}\" {movie_year} spider scene",
        f"\"{movie_title}\" {movie_year} tarantula scene",
        f"\"{movie_title}\" {movie_year} arachnid scene",
        f"\"{movie_title}\" {movie_year} parental guide spider",
        f"\"{movie_title}\" {movie_year} does the dog die spider",
        f"\"{movie_title}\" {movie_year} imdb parental guide spider",
    ]

    raw_results = []
    for q in queries:
        raw_results.extend(duckduckgo_results(q, max_results=6))
        time.sleep(0.2)

    seen = set()
    results = []
    for r in raw_results:
        u = r.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        results.append(r)

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

        # key: require CORE terms
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
        })

    return evidences


def score_confidence(imdb_ev: dict, wiki_ev: dict, web_evs: list[dict]) -> tuple[str, int]:
    score = 0

    # Strong signals
    if imdb_ev.get("ok") and imdb_ev.get("core_hits"):
        score += 7
        score += min(3, imdb_ev.get("severity", 0) // 2)

    if wiki_ev.get("ok") and wiki_ev.get("core_hits"):
        score += 4
        score += min(2, wiki_ev.get("severity", 0) // 2)

    # Independent web pages with core hits
    score += min(6, len(web_evs))

    # Severity language boosts
    sev_sum = sum(e.get("severity", 0) for e in web_evs)
    score += min(6, sev_sum // 3)

    if score >= 12:
        return ("high", score)
    if score >= 6:
        return ("medium", score)
    return ("low", score)


def build_report(movie: dict) -> dict:
    imdb_ev = imdb_parental_guide_evidence(movie["imdb_id"])
    wiki_ev = wikipedia_evidence(movie["title"], movie["year"])
    web_evs = search_and_fetch_evidence(movie["title"], movie["year"], max_pages=12)

    confidence, score = score_confidence(imdb_ev, wiki_ev, web_evs)

    sev_total = imdb_ev.get("severity", 0) + wiki_ev.get("severity", 0) + sum(e.get("severity", 0) for e in web_evs)
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
        "evidence": [imdb_ev, wiki_ev],
        "web_evidence": web_evs,
    }
