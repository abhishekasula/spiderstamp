import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# -----------------------------
# Detection vocabulary
# -----------------------------
CORE_SPIDER_TERMS = [
    # generic
    "spider", "spiders",
    # common
    "tarantula", "tarantulas",
    "wolf spider", "jumping spider", "trapdoor spider",
    "orb weaver", "orb-weaver",
    "funnel web spider", "funnel-web spider",
    "black widow", "brown recluse",
    # scientific
    "arachnid", "arachnids",
    # movie/fantasy-specific
    "giant spider", "cave spider", "forest spider", "underground spider",
    "acromantula", "acromantulas",
    "aragog", "shelob", "ungoliant",
]

FORCED_SPIDER_PRESENCE = {
    # imdb_id is the safest key
    "tt0417741": True,  # Harry Potter and the Half-Blood Prince (Aragog)
}


# Only count if CORE terms exist (prevents "web" false positives)
SUPPORT_TERMS = [
    "cobweb", "cobwebs",
    "webs", "webbed", "webbing",
    "egg sac", "egg sacs",
    "spinneret", "spinnerets",
]

# If these appear near the spider mention, treat as "non-threatening / deceased context"
DECEASED_CONTEXT_TERMS = [
    "dead", "died", "death",
    "corpse", "body", "carcass", "remains", "lifeless",
    "funeral", "burial", "wake",
    "mourn", "mourns", "mourned",
    "eulogy", "pays respects",
]

# Eye-trigger context (only matters if CORE spider exists)
EYE_CONTEXT_TERMS = [
    "eyes",
    "many eyes", "multiple eyes", "dozens of eyes", "rows of eyes",
    "glowing eyes", "shining eyes",
    "watching eyes", "staring eyes", "unblinking eyes",
]

# Intensity hints (heuristic — only affects "severity" label, not presence)
SEVERITY_TERMS = {
    "close-up": 3,
    "close up": 3,
    "giant": 2,
    "huge": 2,
    "massive": 2,
    "swarm": 3,
    "infestation": 3,
    "nest": 2,
    "horde": 2,
    "crawling": 2,
    "crawls": 2,
    "skittering": 2,
    "jump scare": 3,
    "jumpscare": 3,
    "attacks": 2,
    "attack": 2,
    "covered in spiders": 3,
    "surrounded by spiders": 3,
    "webs everywhere": 3,
    "covered in webs": 3,
}

# Avoid Spider-Man confusion
NEGATIVE_CONTEXT = ["spider-man", "spiderman", "spider verse", "spider-verse"]

PREFERRED_DOMAINS = {
    "imdb.com": 5,
    "wikipedia.org": 4,
    "commonsensemedia.org": 3,
    "doesthedogdie.com": 3,
}

USER_AGENT = "Mozilla/5.0 (compatible; SpiderStamp/0.6)"


# -----------------------------
# Helpers
# -----------------------------
def clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text)


def extract_hits(text: str) -> tuple[list[str], list[str]]:
    """
    Returns (core_hits, support_hits). support_hits only kept if core_hits exists.
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


def has_any(text: str, terms: list[str]) -> bool:
    t = text.lower()
    return any(term in t for term in terms)


def is_deceased_context(snippets_text: str) -> bool:
    return has_any(snippets_text, DECEASED_CONTEXT_TERMS)


def has_eye_context(snippets_text: str) -> bool:
    return has_any(snippets_text, EYE_CONTEXT_TERMS)


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
    Returns {title, url, snippet}.
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


# -----------------------------
# Evidence providers
# -----------------------------
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
            "deceased": False,
            "eye_context": False,
        }

    text = clean_text(html)
    core, support = extract_hits(text)

    if not core:
        return {
            "source": "imdb_parentalguide",
            "url": url,
            "ok": True,
            "core_hits": [],
            "support_hits": [],
            "snippets": [],
            "severity": 0,
            "deceased": False,
            "eye_context": False,
        }

    hits_for_snips = core + support
    snips = extract_context_snippets(text, hits_for_snips)
    snip_text = " ".join(snips).lower()

    deceased = is_deceased_context(snip_text)
    eye_ctx = has_eye_context(snip_text)

    sev = severity_score(snip_text)
    if eye_ctx and not deceased:
        sev += 3
    if deceased:
        sev = 0

    return {
        "source": "imdb_parentalguide",
        "url": url,
        "ok": True,
        "core_hits": core,
        "support_hits": support,
        "snippets": snips,
        "severity": sev,
        "deceased": deceased,
        "eye_context": eye_ctx,
    }


def wikipedia_evidence(movie_title: str, movie_year: str) -> dict:
    """
    Wikipedia summary via REST API (no key).
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
            return {
                "source": "wikipedia",
                "url": page_url,
                "ok": True,
                "core_hits": [],
                "support_hits": [],
                "snippets": [],
                "severity": 0,
                "deceased": False,
                "eye_context": False,
            }

        hits_for_snips = core + support
        snips = extract_context_snippets(extract, hits_for_snips, window=200, max_snips=3)
        snip_text = " ".join(snips).lower()

        deceased = is_deceased_context(snip_text)
        eye_ctx = has_eye_context(snip_text)

        sev = severity_score(snip_text) + 2
        if eye_ctx and not deceased:
            sev += 3
        if deceased:
            sev = 0

        return {
            "source": "wikipedia",
            "url": page_url,
            "ok": True,
            "core_hits": core,
            "support_hits": support,
            "snippets": snips,
            "severity": sev,
            "deceased": deceased,
            "eye_context": eye_ctx,
        }

    return {
        "source": "wikipedia",
        "url": "",
        "ok": False,
        "core_hits": [],
        "support_hits": [],
        "snippets": [],
        "severity": 0,
        "deceased": False,
        "eye_context": False,
    }


def search_and_fetch_evidence(movie_title: str, movie_year: str, max_pages: int = 12) -> list[dict]:
    """
    Multi-query DDG search -> fetch pages -> accept only pages with CORE spider terms.
    """
    queries = [
        f"\"{movie_title}\" {movie_year} spider scene",
        f"\"{movie_title}\" {movie_year} tarantula scene",
        f"\"{movie_title}\" {movie_year} arachnid scene",
        f"\"{movie_title}\" {movie_year} acromantula",
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
        if not core:
            continue

        hits_for_snips = core + support
        snips = extract_context_snippets(text, hits_for_snips, window=240, max_snips=4)
        snip_text = " ".join(snips).lower()

        deceased = is_deceased_context(snip_text)
        eye_ctx = has_eye_context(snip_text)

        sev = severity_score(snip_text) + domain_weight(url)
        if eye_ctx and not deceased:
            sev += 3
        if deceased:
            sev = 0

        evidences.append({
            "source": "web_page",
            "url": url,
            "title": r.get("title", ""),
            "core_hits": core,
            "support_hits": support,
            "snippets": snips,
            "severity": sev,
            "deceased": deceased,
            "eye_context": eye_ctx,
        })

    return evidences


# -----------------------------
# Presence + scoring + report
# -----------------------------
def spider_present(imdb_ev: dict, wiki_ev: dict, web_evs: list[dict], imdb_id: str) -> bool:
    """
    Presence = any CORE spider term OR forced override.
    """
    # 🔒 Forced override first
    if imdb_id in FORCED_SPIDER_PRESENCE:
        return FORCED_SPIDER_PRESENCE[imdb_id]

    if imdb_ev.get("core_hits"):
        return True
    if wiki_ev.get("core_hits"):
        return True
    return any(e.get("core_hits") for e in web_evs)



def score_confidence(imdb_ev: dict, wiki_ev: dict, web_evs: list[dict]) -> tuple[str, int]:
    """
    Confidence here means "how confident are we that a spider is present"
    (NOT how scary it is).
    """
    score = 0

    if imdb_ev.get("ok") and imdb_ev.get("core_hits"):
        score += 7
    if wiki_ev.get("ok") and wiki_ev.get("core_hits"):
        score += 4

    score += min(6, len(web_evs))

    # severity helps a little as a proxy for detailed mentions
    sev_total = imdb_ev.get("severity", 0) + wiki_ev.get("severity", 0) + sum(e.get("severity", 0) for e in web_evs)
    score += min(4, sev_total // 4)

    if score >= 12:
        return ("high", score)
    if score >= 6:
        return ("medium", score)
    return ("low", score)


def build_report(movie: dict) -> dict:
    imdb_ev = imdb_parental_guide_evidence(movie["imdb_id"])
    wiki_ev = wikipedia_evidence(movie["title"], movie["year"])
    web_evs = search_and_fetch_evidence(movie["title"], movie["year"], max_pages=12)

    present = spider_present(imdb_ev, wiki_ev, web_evs, movie["imdb_id"])

    confidence, score = score_confidence(imdb_ev, wiki_ev, web_evs)s

    # Optional severity label (for info only)
    all_evs = [imdb_ev, wiki_ev] + web_evs
    spider_evs = [e for e in all_evs if e.get("core_hits")]
    any_eye_alive = any(e.get("eye_context") and not e.get("deceased") for e in spider_evs)
    any_alive = any(e.get("core_hits") and not e.get("deceased") for e in spider_evs)

    if spider_evs and not any_alive:
        severity_label = "deceased-only"
    elif present:
        severity_label = "present"
    else:
        severity_label = "none"

    if any_eye_alive and severity_label in ("present",):
        severity_label = "present+eye-closeups"

    return {
        "movie": movie,
        "present": present,          # ✅ what you wanted
        "confidence": confidence,    # confidence of presence
        "score": score,
        "severity": severity_label,  # informational only
        "evidence": [imdb_ev, wiki_ev],
        "web_evidence": web_evs,
    }
