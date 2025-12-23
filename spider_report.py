import re
import requests
from bs4 import BeautifulSoup

SPIDER_TERMS = [
    "spider", "spiders", "tarantula", "tarantulas",
    "arachnid", "arachnids",
    "web", "cobweb", "cobwebs",
    "eight-legged", "eight legged",
]

NEGATIVE_CONTEXT = ["spider-man", "spiderman"]

def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)

def spider_hits(text: str) -> list[str]:
    t = text.lower()
    hits = []
    for term in SPIDER_TERMS:
        if term in t:
            hits.append(term)
    # don’t throw away everything if Spider-Man appears; we just use it later to interpret
    return sorted(set(hits))

def fetch(url: str) -> str | None:
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SpiderStamp/0.1)"},
            timeout=20
        )
        if r.status_code != 200:
            return None
        return r.text
    except requests.RequestException:
        return None

def imdb_parental_guide_evidence(imdb_id: str) -> dict:
    url = f"https://www.imdb.com/title/{imdb_id}/parentalguide/"
    html = fetch(url)
    if not html:
        return {"source": "imdb_parentalguide", "url": url, "ok": False, "hits": [], "snippet": ""}

    text = clean_text(html)
    hits = spider_hits(text)

    snippet = ""
    if hits:
        m = re.search(r".{0,80}(spider|tarantula|arachnid|cobweb|web).{0,140}", text, flags=re.I)
        snippet = m.group(0) if m else ""

    return {"source": "imdb_parentalguide", "url": url, "ok": True, "hits": hits, "snippet": snippet}

def duckduckgo_snippets(query: str, max_results: int = 6) -> list[dict]:
    url = "https://duckduckgo.com/html/"
    try:
        r = requests.post(
            url,
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; SpiderStamp/0.1)"},
            timeout=20
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

def confidence_score(imdb_ev: dict, web_snips: list[dict]) -> tuple[str, int]:
    score = 0

    # strong signal: IMDb parental guide mentions spider terms
    if imdb_ev.get("ok") and imdb_ev.get("hits"):
        score += 5

    # weaker signals: multiple web snippets mention spider terms
    for s in web_snips:
        combined = f"{s.get('title','')} {s.get('snippet','')}"
        if any(term in combined.lower() for term in SPIDER_TERMS) and not any(bad in combined.lower() for bad in NEGATIVE_CONTEXT):
            score += 1

    if score >= 6:
        return "high", score
    if score >= 3:
        return "medium", score
    return "low", score

def build_report(movie: dict) -> dict:
    imdb_ev = imdb_parental_guide_evidence(movie["imdb_id"])
    query = f"\"{movie['title']}\" {movie['year']} spider scene"
    web_snips = duckduckgo_snippets(query)

    confidence, score = confidence_score(imdb_ev, web_snips)

    return {
        "movie": movie,
        "confidence": confidence,
        "score": score,
        "evidence": [imdb_ev],
        "web_mentions": web_snips,
    }
