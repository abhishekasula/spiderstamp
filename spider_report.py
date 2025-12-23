import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

SPIDER_TERMS = [
    "spider", "spiders", "tarantula", "tarantulas",
    "arachnid", "arachnids",
    "web", "cobweb", "cobwebs",
    "eight-legged", "eight legged",
]

# Words that suggest intensity
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

USER_AGENT = "Mozilla/5.0 (compatible; SpiderStamp/0.2)"

def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text

def spider_hits(text: str) -> list[str]:
    t = text.lower()
    hits = []
    for term in SPIDER_TERMS:
        if term in t:
            hits.append(term)
    return sorted(set(hits))

def has_negative_context(text: str) -> bool:
    t = text.lower()
    return any(bad in t for bad in NEGATIVE_CONTEXT)

def extract_context_snippets(text: str, terms: list[str], window: int = 160, max_snips: int = 5) -> list[str]:
    """
    Return up to max_snips snippets around any term hits.
    """
    lower = text.lower()
    snippets = []
    for term in terms:
        idx = lower.find(term)
        if idx == -1:
            continue
        start = max(0, idx - window)
        end = min(len(text), idx + len(term) + window)
        snip = text[start:end].strip()
        snippets.append(snip)
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
        host = urlparse(url).netloc.lower()
        host = host.replace("www.", "")
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
    Returns list of {title, url, snippet}.
    This is best-effort; DDG HTML can change.
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
        return {"source": "imdb_parentalguide", "url": url, "ok": False, "hits": [], "snippets": [], "severity": 0}

    text = clean_text(html)
    hits = spider_hits(text)
    snips = extract_context_snippets(text, hits) if hits else []
    sev = severity_score(" ".join(snips)) if snips else 0

    return {"source": "imdb_parentalguide", "url": url, "ok": True, "hits": hits, "snippets": snips, "severity": sev}

def search_and_fetch_evidence(movie_title: str, movie_year: str, max_pages: int = 8) -> list[dict]:
    """
    Multi-query search -> pick URLs -> fetch pages -> extract spider evidence.
    """
    title = movie_title
    year = movie_year

    queries = [
        f"\"{title}\" {year} spider scene",
        f"\"{title}\" {year} tarantula",
        f"\"{title}\" {year} parental guide spider",
        f"\"{title}\" {year} does the dog die spider",
        f"\"{title}\" {year} imdb parental guide spider",
        f"\"{title}\" {year} cave spider scene",
        f"\"{title}\" {year} attic spider scene",
    ]

    # Gather results across queries
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

    # Rank URLs: prefer known domains + spider words in snippet/title
    def rank(item: dict) -> tuple:
        text = (item.get("title", "") + " " + item.get("snippet", "")).lower()
        term_bonus = 1 if any(t in text for t in SPIDER_TERMS) else 0
        neg_penalty = 1 if any(b in text for b in NEGATIVE_CONTEXT) else 0
        return (domain_weight(item.get("url", "")), term_bonus, -neg_penalty)

    results.sort(key=rank, reverse=True)

    # Fetch pages & extract evidence
    evidences = []
    for r in results[:max_pages]:
        url = r["url"]
        html = fetch(url)
        if not html:
            continue

        text = clean_text(html)
        hits = spider_hits(text)
        if not hits:
            continue

        snips = extract_context_snippets(text, hits, window=220, max_snips=4)
        sev = severity_score(" ".join(snips)) + domain_weight(url)

        evidences.append({
            "source": "web_page",
            "url": url,
            "title": r.get("title", ""),
            "hits": hits,
            "snippets": snips,
            "severity": sev,
            "negative_context": has_negative_context(text),
        })

    return evidences

def score_confidence(imdb_ev: dict, web_evs: list[dict]) -> tuple[str, int]:
    """
    Score based on:
    - IMDb parental guide hit (strong)
    - multiple independent pages with hits
    - severity language
    """
    score = 0

    # Strong signal
    if imdb_ev.get("ok") and imdb_ev.get("hits"):
        score += 6
        score += min(3, imdb_ev.get("severity", 0) // 2)

    # Independent evidence count
    score += min(6, len(web_evs))  # cap

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
    web_evs = search_and_fetch_evidence(movie["title"], movie["year"], max_pages=10)

    confidence, score = score_confidence(imdb_ev, web_evs)

    # A simple severity label (purely heuristic)
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
