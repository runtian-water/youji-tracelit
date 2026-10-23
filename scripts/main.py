#!/usr/bin/env python3
"""TraceLit main.py — search / verify / audit / doctor.

Zero-dependency core: urllib + difflib + concurrent.futures.
Optional accelerators: rapidfuzz, certifi.
"""

from __future__ import annotations

import argparse
from argparse import Namespace
import contextlib
import html
import io
import json
import os
import re
import ssl
import sys
import time
import unicodedata
import zipfile
from xml.sax.saxutils import escape as xml_escape
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

VERSION = "0.5.0"
OPENALEX_WORKS = "https://api.openalex.org/works"
OPENALEX_RATE = "https://api.openalex.org/rate-limit"
CROSSREF_WORKS = "https://api.crossref.org/works/"
DATACITE_DOIS = "https://api.datacite.org/dois/"
MAX_PER_PAGE = 100
SEARCH_COST = 10
MAX_URL_LEN = 4094
KEY_URL = "https://openalex.org/settings/api"
GAP_HITS_MAX = 50
GAP_SHARE_MAX = 0.05

ACCEPTED_TYPES = {
    "article", "review", "preprint", "proceedings-article", "conference-paper",
    "book-chapter", "book", "dissertation", "report",
}
EXCLUDE_CODES = {"R1", "P1", "Y1", "L1", "V1", "T1", "S1", "M1", "C1", "I1"}
PENDING_CODES = {"D1", "D2", "D3", "D4", "E1"}
SEMANTIC_CODES = {"T1", "S1", "M1", "C1", "I1"}
ALL_CODES = EXCLUDE_CODES | PENDING_CODES
VERDICTS = {"✓", "×", "○"}

DIM_CUES = {
    "stem": [
        "material", "sample", "dataset", "synthesis", "characterization",
        "method", "algorithm", "model", "temperature", "concentration",
        "scale", "training", "efficiency", "accuracy", "yield", "error",
        "performance", "device", "process",
    ],
    "social": [
        "sample", "participant", "respondent", "interview", "questionnaire",
        "survey", "experiment", "method", "policy", "region", "context",
        "variable", "outcome", "effect", "mechanism", "governance",
    ],
}

# Default screening window by field. The API window adds 5 extra years
# for Y1 audit; the screen window is what the table reports.
FIELD_WINDOWS = {
    "cs": 3,
    "materials": 5,
    "math": 10,
    "social": 10,
    "unknown": 10,
}

FIELD_KEYWORDS = {
    "materials": [
        "perovskite", "material", "synthesis", "catalyst", "polymer",
        "battery", "electrode", "nanoparticle", "mof", "lifepo4", "co2",
        "film", "passivation", "alloy", "ceramic", "membrane", "photovoltaic",
    ],
    "cs": [
        "machine learning", "deep learning", "neural", "algorithm", "llm",
        "language model", "computer vision", "nlp", "dataset", "classification",
        "software", "reinforcement", "transformer", "artificial intelligence",
        " ai ",
    ],
    "math": [
        "theorem", "proof", "equation", "mechanics", "quantum", "relativity",
        "fluid", "finite element", "topology", "numerical", "pde", "ode",
    ],
    "social": [
        "education", "student", "undergraduate", "policy", "survey", "interview",
        "questionnaire", "governance", "economic", "sociology", "psychology",
        "management", "rural", "china",
    ],
}

BOOLEAN_WORDS = {"and", "or", "not", "near", "with", "without"}


class TraceLitError(Exception):
    pass


class AuthError(TraceLitError):
    pass


class BudgetError(TraceLitError):
    pass


class RateLimitError(TraceLitError):
    pass


class QueryError(TraceLitError):
    pass


class QueryTooLong(TraceLitError):
    pass


class APIError(TraceLitError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_env_file():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and not os.environ.get(key):
                os.environ[key] = value
    except Exception:
        pass


load_env_file()


def get_key(explicit: str | None = None) -> str:
    return (explicit or os.environ.get("OPENALEX_API_KEY", "")).strip()


def user_agent() -> str:
    contact = (
        os.environ.get("CROSSREF_MAILTO", "").strip()
        or os.environ.get("OPENALEX_CONTACT", "").strip()
    )
    return f"TraceLit/{VERSION}" + (f" (+{contact})" if contact else "")


def ssl_context():
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def ci_get(headers: dict, key: str, default=None):
    for k, v in headers.items():
        if k.lower() == key.lower():
            return v
    return default


def http_get(url: str, headers: dict | None = None, timeout: int = 20, retries: int = 2,
             retry_429: bool = False):
    headers = dict(headers or {})
    headers.setdefault("User-Agent", user_agent())
    last = (0, {}, "unknown error")
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout, context=ssl_context()) as resp:
                body = resp.read().decode("utf-8", "replace")
                return resp.status, dict(resp.headers), body
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            last = (exc.code, dict(exc.headers), body)
            if exc.code == 429 and retry_429 and attempt < retries:
                try:
                    delay = int(str(ci_get(dict(exc.headers), "Retry-After", "0") or "0"))
                except ValueError:
                    delay = 0
                time.sleep(min(max(delay, 1), 10) if delay else (2 ** attempt))
                continue
            if exc.code >= 500 and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return last
        except (URLError, TimeoutError, ssl.SSLError) as exc:
            last = (0, {}, str(exc))
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return last
    return last


def classify_429(headers: dict, body: str):
    remaining = str(ci_get(headers, "X-RateLimit-Remaining", "") or "")
    try:
        remaining_val = float(remaining)
    except ValueError:
        remaining_val = None
    try:
        retry_after_val = int(str(ci_get(headers, "Retry-After", "0") or "0"))
    except ValueError:
        retry_after_val = 0
    low = (body or "").lower()
    budget_tokens = ("dailyremainingusd", "creditsrequired", "insufficient budget", "not_enough_credits")
    if (
        (remaining_val is not None and remaining_val <= 0)
        or retry_after_val > 120
        or any(t in low for t in budget_tokens)
    ):
        raise BudgetError(
            "OpenAlex 日预算耗尽。UTC 零点重置，或在 "
            f"{KEY_URL} 申请/更换 key。"
        )
    raise RateLimitError("OpenAlex 突发限流；稍后重试或降低并发。")


def openalex_get(params: dict, key: str):
    url = OPENALEX_WORKS + "?" + urlencode(params)
    if len(url) > MAX_URL_LEN:
        raise QueryTooLong(
            f"检索 URL {len(url)} 字符，超过 {MAX_URL_LEN}。"
            "请拆分 OR 组、减少同义词，或分多次检索并记录 chunks。"
        )
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    status, resp_headers, body = http_get(url, headers=headers)
    if status == 429:
        classify_429(resp_headers, body)
    if status in (401, 403):
        raise AuthError(f"OpenAlex key 无效或未激活。申请：{KEY_URL}")
    if status == 400:
        raise QueryError(f"OpenAlex 400：{body[:500]}")
    if status == 0 or status >= 500:
        raise APIError(f"OpenAlex 请求失败：status={status} body={body[:300]}")
    if status != 200:
        raise APIError(f"OpenAlex 返回 {status}：{body[:300]}")
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise APIError(f"OpenAlex 返回非 JSON：{exc}") from exc
    return data, resp_headers, url


def normalize_doi(raw) -> str:
    s = (raw or "").strip().lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi:\s*", "", s)
    return s


def normalize_title(raw) -> str:
    s = unicodedata.normalize("NFKC", html.unescape(raw or ""))
    s = s.lower().replace("–", "-").replace("—", "-").replace("−", "-")
    s = re.sub(r"[^\w\s一-鿿]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def sanitize_text(text: str) -> str:
    """Strip control characters from untrusted metadata before it reaches the LLM."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text or "")


def normalize_quote(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def strip_cover_suffix(title: str) -> str:
    """Strip publisher cover/issue suffixes such as '(Adv. Energy Mater. 40/2021)'."""
    t = (title or "").strip()
    patterns = [
        r"\s*\([^()]*(?:19|20)\d{2}[^()]*/[^()]*\)\s*$",
        r"\s*\([^()]*\b(?:Adv\.|Mater\.|Nature|Science|Chem\.|Phys\.|Energy|Vol\.?|Issue|No\.)\b[^()]*(?:19|20)\d{2}[^()]*\)\s*$",
    ]
    for pat in patterns:
        new = re.sub(pat, "", t, flags=re.I).strip()
        if new and new != t:
            return new
    return t


def query_health_detail(expr: str) -> dict:
    s = expr or ""
    has_bool = bool(re.search(r"\b(?:AND|OR|NOT)\b", s))
    has_quote = '"' in s
    terms = [
        t for t in re.findall(r"[A-Za-z0-9一-鿿]{2,}", s)
        if t.lower() not in BOOLEAN_WORDS
    ]
    if has_bool or has_quote:
        health = "ok"
    else:
        health = "unexpanded" if len(terms) < 3 else "no_boolean"
    return {
        "health": health,
        "has_boolean": has_bool,
        "has_quote": has_quote,
        "concepts": len(terms),
        "terms": terms[:8],
    }


def query_health(expr: str) -> str:
    return query_health_detail(expr)["health"]


def reconstruct_abstract(inv) -> str:
    if not isinstance(inv, dict) or not inv:
        return ""
    positions = [p for ps in inv.values() for p in ps if isinstance(p, int)]
    if not positions:
        return ""
    words = [""] * (max(positions) + 1)
    for word, ps in inv.items():
        for p in ps:
            if isinstance(p, int) and 0 <= p < len(words):
                words[p] = word
    return " ".join(w for w in words if w).strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？.!?])\s*", text or "")
    return [p.strip() for p in parts if p.strip()]


def query_terms(search_expr: str) -> list[str]:
    terms = re.findall(r"[A-Za-z0-9一-鿿]{2,}", search_expr or "")
    return [t.lower() for t in terms if t.lower() not in BOOLEAN_WORDS]


def select_evidence(abstract: str, terms: list[str], cues: list[str], limit: int):
    if not abstract:
        return "", "title"
    sentences = split_sentences(abstract)
    scored = []
    for i, sent in enumerate(sentences):
        low = sent.lower()
        score = sum(1 for t in terms if t and t in low)
        score += sum(1 for c in cues if c in low)
        if score:
            scored.append((score, i, sent))
    if scored:
        picked = sorted(scored, key=lambda x: (-x[0], x[1]))[:4]
        picked.sort(key=lambda x: x[1])
    else:
        picked = [(0, i, s) for i, s in enumerate(sentences[:2])]
    out = ""
    for _, _, sent in picked:
        if out and len(out) + len(sent) + 1 > limit:
            break
        out = (out + " " + sent).strip()
    if not out:
        out = picked[0][2][:limit]
    return out[:limit], "abstract"


def parse_work(work: dict) -> dict:
    source = ((work.get("primary_location") or {}).get("source") or {}).get("display_name")
    authorships = work.get("authorships") or []
    authors = []
    for a in authorships:
        name = ((a or {}).get("author") or {}).get("display_name")
        if name:
            authors.append(name)
    typ = work.get("type") or "other"
    category = "review" if typ == "review" else "preprint" if typ == "preprint" else "primary"
    is_retracted = work.get("is_retracted")
    if is_retracted is True:
        retraction_status = "retracted"
    elif is_retracted is False:
        retraction_status = "not_retracted"
    else:
        retraction_status = "unknown"
    return {
        "openalex_id": (work.get("id") or "").rsplit("/", 1)[-1],
        "title": sanitize_text(work.get("title") or ""),
        "doi": normalize_doi(work.get("doi")),
        "year": work.get("publication_year"),
        "type": typ,
        "language": work.get("language"),
        "authors": authors[:3],
        "author_count": len(authors),
        "source": source,
        "biblio": work.get("biblio") or {},
        "cited_by_count": work.get("cited_by_count", 0),
        "is_retracted": is_retracted,
        "retraction_status": retraction_status,
        "version_duplicate": False,
        "category": category,
        "_abstract": sanitize_text(reconstruct_abstract(work.get("abstract_inverted_index"))),
        "_norm_title": normalize_title(work.get("title")),
        "_norm_title_cover": normalize_title(strip_cover_suffix(work.get("title"))),
        "_norm_first_author": normalize_title(authors[0]) if authors else "",
    }


def dedup_records(records: list[dict]) -> list[dict]:
    seen_doi = set()
    seen_key = set()
    out = []
    for r in records:
        doi = r.get("doi") or ""
        if doi:
            if doi in seen_doi:
                continue
            seen_doi.add(doi)
        title_key = r.get("_norm_title_cover") or r.get("_norm_title") or r.get("openalex_id") or ""
        key = (title_key, r.get("year"), r.get("_norm_first_author"), r.get("type"))
        if key in seen_key:
            continue
        seen_key.add(key)
        out.append(r)

    groups: dict[tuple, list[dict]] = {}
    for r in out:
        norm = r.get("_norm_title_cover") or r.get("_norm_title")
        if not norm:
            continue
        groups.setdefault((norm, r["_norm_first_author"]), []).append(r)
    for group in groups.values():
        preprints = [r for r in group if r.get("category") == "preprint"]
        published = [r for r in group if r.get("category") != "preprint"]
        if preprints and published:
            for p in preprints:
                p["version_duplicate"] = True
    return out


def is_genre_warning(rec: dict) -> bool:
    title = (rec.get("title") or "").strip().lower()
    if title.startswith((
        "perspective:", "perspective ", "commentary:", "preview:",
        "editorial:", "opinion:", "letter:",
    )):
        return True
    if "a balanced view" in title or "outlook" in title:
        return True
    b = rec.get("biblio") or {}
    first, last = b.get("first_page"), b.get("last_page")
    try:
        span = int(last) - int(first) + 1
    except (TypeError, ValueError):
        span = None
    if span is not None and span <= 3 and "?" in title:
        return True
    return False


def apply_checks(r: dict, from_year: int | None, to_year: int | None, language_mode: str):
    year = r.get("year")
    if year is None:
        year_ok = None
    else:
        year_ok = (from_year is None or year >= from_year) and (to_year is None or year <= to_year)
    typ = r.get("type")
    type_ok = None if not typ else typ in ACCEPTED_TYPES
    lang = r.get("language")
    if not lang:
        language_ok = None
    elif language_mode == "en":
        language_ok = lang == "en"
    elif language_mode == "zh":
        language_ok = lang == "zh"
    else:
        language_ok = lang in ("en", "zh")
    rs = r.get("retraction_status")
    retracted_ok = None if rs == "unknown" else rs != "retracted"
    r["checks"] = {
        "year_ok": year_ok,
        "type_ok": type_ok,
        "language_ok": language_ok,
        "retracted_ok": retracted_ok,
        "version_ok": not r.get("version_duplicate", False),
    }
    r["genre_warning"] = is_genre_warning(r)


def tier_limits(tier: str):
    if tier == "寻迹":
        return 10, 600
    if tier == "溯迹":
        return 25, 1200
    return 25, 600


def infer_field(text: str) -> str:
    low = (text or "").lower()
    scores = {
        field: sum(1 for kw in kws if kw in low)
        for field, kws in FIELD_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def default_facets(field: str, expr: str) -> list[tuple[str, str]]:
    if field == "social":
        return [
            ("对象/样本", f'({expr}) AND (sample OR participant OR respondent)'),
            ("方法/设计", f'({expr}) AND (survey OR interview OR experiment OR "research design")'),
            ("情境/政策", f'({expr}) AND (policy OR governance OR context OR region)'),
        ]
    return [
        ("技术路线", f'({expr}) AND (synthesis OR fabrication OR "technical route")'),
        ("材料体系", f'({expr}) AND (material OR composition OR "material system")'),
        ("性能区间", f'({expr}) AND (efficiency OR performance OR stability)'),
    ]


def facet_search(expr: str, key: str, from_year: int, to_year: int, language: str):
    filter_parts = [
        f"from_publication_date:{from_year}-01-01",
        f"to_publication_date:{to_year}-12-31",
    ]
    if language != "all":
        filter_parts.append(f"language:{language}")
    params = {
        "search.title_abstract_keywords": expr,
        "per_page": "1",
        "sort": "relevance_score:desc",
        "filter": ",".join(filter_parts),
    }
    data, headers, _ = openalex_get(params, key)
    return int((data.get("meta") or {}).get("count", 0) or 0), headers


def supplemental_filter_parts(kind: str, from_year: int, to_year: int, language: str) -> list[str]:
    if kind == "background":
        start = max(1, from_year - 10)
        parts = [
            f"from_publication_date:{start}-01-01",
            f"to_publication_date:{to_year}-12-31",
        ]
    else:
        parts = [f"to_publication_date:{to_year}-12-31"]
    if language != "all":
        parts.append(f"language:{language}")
    return parts


def supplemental_search(expr: str, key: str, kind: str, from_year: int, to_year: int,
                        language: str):
    if kind == "background":
        query = f'({expr}) AND (review OR "systematic review" OR overview OR perspective)'
    else:
        query = expr
    params = {
        "search.title_abstract_keywords": query,
        "per_page": "5",
        "sort": "cited_by_count:desc",
        "filter": ",".join(supplemental_filter_parts(kind, from_year, to_year, language)),
    }
    data, headers, _ = openalex_get(params, key)
    return data, headers


def resolve_field(args) -> tuple[str, str]:
    explicit = getattr(args, "field", None)
    if explicit:
        return explicit, "explicit"
    inferred = infer_field(getattr(args, "query", "") or "")
    if inferred != "unknown":
        return inferred, "inferred"
    return "unknown", "default"


def search_cmd(args) -> int:
    key = get_key(args.api_key)
    if not key:
        if args.tier in ("循迹", "溯迹") and not args.dry_run:
            raise AuthError(
                "循迹/溯迹需要 OpenAlex API key。免费申请："
                f"{KEY_URL}（$1/天，无需信用卡）。"
                "如果只想无 key 试跑，请用 --tier 寻迹。"
            )
        warning = (
            "无 key：本次仅 dry-run；循迹/溯迹正式运行需要 key。"
            if args.dry_run and args.tier in ("循迹", "溯迹")
            else "无 key：寻迹可用，但预算约 $0.10/天且按出口 IP 共享。"
        )
        print(json.dumps({
            "warning": warning,
            "key_url": KEY_URL,
        }, ensure_ascii=False), file=sys.stderr)

    field, field_source = resolve_field(args)
    today_year = datetime.now(timezone.utc).year
    to_year = args.to_year or today_year
    if args.from_year is not None:
        from_year = args.from_year
        window_source = "from_year"
    else:
        window_source = {
            "explicit": "field",
            "inferred": "inferred",
            "default": "default",
        }.get(field_source, "default")
        from_year = to_year - FIELD_WINDOWS.get(field, 10)
    window_years = (to_year - from_year) if from_year is not None else None
    if field_source == "default" and args.from_year is None and args.tier in ("循迹", "溯迹"):
        print(json.dumps({
            "warning": "学科未识别，窗口默认 10 年；建议传 --field 或 --from-year。",
        }, ensure_ascii=False), file=sys.stderr)
    if field == "social":
        discipline = "social"
    elif field in ("cs", "materials", "math"):
        discipline = "stem"
    else:
        discipline = getattr(args, "discipline", None) or "stem"
    history = bool(getattr(args, "history", False))
    api_from = max(1, from_year - 5) if (from_year is not None and history) else from_year

    filter_parts = []
    if args.filter:
        filter_parts.append(args.filter.strip())
    else:
        if api_from is not None:
            filter_parts.append(f"from_publication_date:{api_from}-01-01")
        if to_year is not None:
            filter_parts.append(f"to_publication_date:{to_year}-12-31")
        if args.language != "all":
            filter_parts.append(f"language:{args.language}")

    search_expr = args.search or args.query
    health_detail = query_health_detail(search_expr)
    health = health_detail["health"]
    if health != "ok":
        print(json.dumps({
            "warning": f"检索式体检：{health}（boolean={health_detail['has_boolean']}, "
                       f"quote={health_detail['has_quote']}, concepts={health_detail['concepts']}）；"
                       "样本可能只覆盖领域一角。建议用 --search 传扩展后的布尔式。",
        }, ensure_ascii=False), file=sys.stderr)
    per_page = max(1, min(int(args.per_page or MAX_PER_PAGE), MAX_PER_PAGE))
    exact = bool(getattr(args, "exact", False))
    search_key = "search.exact" if exact else "search.title_abstract_keywords"
    params = {
        search_key: search_expr,
        "per_page": str(per_page),
        "sort": "relevance_score:desc",
    }
    if filter_parts:
        params["filter"] = ",".join(filter_parts)

    url = OPENALEX_WORKS + "?" + urlencode(params)
    if args.dry_run:
        bg_est = getattr(args, "background", None)
        if bg_est is None:
            bg_est = args.tier in ("循迹", "溯迹")
        if args.tier == "寻迹":
            bg_est = False
        fd_est = bool(getattr(args, "foundational", False))
        facet_est = 0
        if args.tier == "溯迹":
            facet_est = 10 * (len(getattr(args, "facet", None) or []) or 3)
        print(json.dumps({
            "dry_run": True,
            "url_len": len(url),
            "estimated_credits": SEARCH_COST + (10 if bg_est else 0) + (10 if fd_est else 0) + facet_est,
            "background": bg_est,
            "foundational": fd_est,
            "facet_count": (len(getattr(args, "facet", None) or []) or 3) if args.tier == "溯迹" else 0,
            "params": params,
            "field": field,
            "field_source": field_source,
            "window_years": window_years,
            "window_source": window_source,
            "screen_year_window": f"{from_year}-01-01/{to_year}-12-31",
            "api_year_window": f"{api_from}-01-01/{to_year}-12-31",
            "key_configured": bool(key),
        }, ensure_ascii=False, indent=2))
        return 0
    if len(url) > MAX_URL_LEN:
        raise QueryTooLong(
            f"检索 URL {len(url)} 字符，超过 {MAX_URL_LEN}。"
            "请拆分 OR 组、减少同义词，或分多次检索并记录 chunks。"
        )

    started = time.time()
    exact_fallback = False
    try:
        data, headers, _ = openalex_get(params, key)
    except QueryError:
        if not exact:
            raise
        params.pop("search.exact", None)
        params["search.title_abstract_keywords"] = search_expr
        data, headers, _ = openalex_get(params, key)
        exact_fallback = True
    raw_results = data.get("results") or []
    total_hits = (data.get("meta") or {}).get("count", 0)
    records = [parse_work(w) for w in raw_results]
    before = len(records)
    records = dedup_records(records)
    after_dedup = len(records)
    display, evidence_limit = tier_limits(args.tier)
    terms = query_terms(search_expr)
    cues = DIM_CUES.get(discipline, DIM_CUES["stem"])
    for r in records:
        apply_checks(r, from_year, to_year, args.language)
        ev, ev_field = select_evidence(r.get("_abstract", ""), terms, cues, evidence_limit)
        r["evidence"] = ev
        r["evidence_field"] = ev_field
    background_opt = getattr(args, "background", None)
    background = background_opt if background_opt is not None else args.tier in ("循迹", "溯迹")
    if args.tier == "寻迹" and background:
        background = False
        print(json.dumps({
            "warning": "寻迹默认不跑背景 pass，保持单次 search（10 credits）。"
                       "需要背景综述请用循迹/溯迹。",
        }, ensure_ascii=False), file=sys.stderr)
    foundational = bool(getattr(args, "foundational", False))
    primary_records = records[:display]
    extras = []
    background_count = foundational_count = 0
    background_hits = foundational_hits = 0
    background_returned = foundational_returned = 0
    extra_cost = 0
    seen_dois = {r.get("doi") for r in primary_records if r.get("doi")}
    seen_titles = {
        (r.get("_norm_title_cover") or r.get("_norm_title"))
        for r in primary_records
    }
    if (background or foundational) and not key:
        print(json.dumps({
            "warning": "背景/奠基 pass 需要 OpenAlex key；已跳过。",
        }, ensure_ascii=False), file=sys.stderr)

    remaining = ci_get(headers, "X-RateLimit-Remaining")
    try:
        remaining_val = int(float(remaining))
    except (TypeError, ValueError):
        remaining_val = None
    needed = (10 if background else 0) + (10 if foundational else 0)
    if remaining_val is not None and remaining_val < needed:
        if background:
            background = False
        if foundational:
            foundational = False
        print(json.dumps({
            "warning": f"剩余 credits {remaining_val} < 额外 pass 需要 {needed}；"
                       "已跳过背景/奠基检索，仅返回主检索结果。",
        }, ensure_ascii=False), file=sys.stderr)

    if background and key:
        bdata, _ = supplemental_search(search_expr, key, "background", from_year, to_year, args.language)
        background_hits = (bdata.get("meta") or {}).get("count", 0)
        braw = bdata.get("results") or []
        background_returned = len(braw)
        for r in dedup_records([parse_work(w) for w in braw]):
            doi = r.get("doi") or ""
            title_key = r.get("_norm_title_cover") or r.get("_norm_title")
            if (doi and doi in seen_dois) or (title_key and title_key in seen_titles):
                continue
            r["background"] = True
            r["foundational"] = False
            r["category"] = "background"
            apply_checks(r, from_year, to_year, args.language)
            r["checks"]["background_ok"] = True
            ev, ev_field = select_evidence(r.get("_abstract", ""), terms, cues, evidence_limit)
            r["evidence"] = ev
            r["evidence_field"] = ev_field
            extras.append(r)
            if doi:
                seen_dois.add(doi)
            if title_key:
                seen_titles.add(title_key)
            background_count += 1
            if background_count >= 3:
                break
        extra_cost += 10

    if foundational and key:
        fdata, _ = supplemental_search(search_expr, key, "foundational", from_year, to_year, args.language)
        foundational_hits = (fdata.get("meta") or {}).get("count", 0)
        fraw = fdata.get("results") or []
        foundational_returned = len(fraw)
        for r in dedup_records([parse_work(w) for w in fraw]):
            if r.get("year") is None or r["year"] >= from_year:
                continue
            doi = r.get("doi") or ""
            title_key = r.get("_norm_title_cover") or r.get("_norm_title")
            if (doi and doi in seen_dois) or (title_key and title_key in seen_titles):
                continue
            r["background"] = True
            r["foundational"] = True
            r["category"] = "background"
            apply_checks(r, from_year, to_year, args.language)
            r["checks"]["background_ok"] = True
            ev, ev_field = select_evidence(r.get("_abstract", ""), terms, cues, evidence_limit)
            r["evidence"] = ev
            r["evidence_field"] = ev_field
            extras.append(r)
            if doi:
                seen_dois.add(doi)
            if title_key:
                seen_titles.add(title_key)
            foundational_count += 1
            if foundational_count >= 3:
                break
        extra_cost += 10

    records = primary_records + extras

    facet_queries = []
    facet_credits = 0
    if args.tier == "溯迹" and key:
        facet_args = getattr(args, "facet", None) or []
        specs = []
        for i, item in enumerate(facet_args, 1):
            if "=" in item:
                label, query = item.split("=", 1)
            else:
                label, query = f"F{i}", item
            specs.append((label.strip() or f"F{i}", query.strip()))
        if not specs:
            specs = default_facets(field, search_expr)
        for label, query in specs[:5]:
            try:
                hits, fheaders = facet_search(
                    query, key, from_year, to_year, args.language
                )
            except BudgetError as exc:
                facet_queries.append({
                    "label": label, "query": query, "hits": None,
                    "cost_credits": 0, "error": str(exc),
                })
                print(json.dumps({
                    "warning": f"facet「{label}」预算耗尽，停止后续 facet。",
                }, ensure_ascii=False), file=sys.stderr)
                break
            except TraceLitError as exc:
                facet_queries.append({
                    "label": label, "query": query, "hits": None,
                    "cost_credits": 0, "error": str(exc),
                })
                continue
            cost = int(ci_get(fheaders, "X-RateLimit-Credits-Used", SEARCH_COST) or SEARCH_COST)
            facet_credits += cost
            facet_queries.append({
                "label": label, "query": query, "hits": hits,
                "cost_credits": cost,
            })

    top5 = []
    gaps = []
    if args.tier == "溯迹":
        def match_hits(rec: dict) -> int:
            text = ((rec.get("title") or "") + " " + (rec.get("evidence") or "")).lower()
            return sum(1 for t in terms if t and t in text) + sum(1 for c in cues if c in text)

        ranked = sorted(
            primary_records,
            key=lambda r: (-match_hits(r), -(r.get("cited_by_count") or 0)),
        )
        for i, r in enumerate(ranked[:5], 1):
            top5.append({
                "rank": i,
                "openalex_id": r.get("openalex_id"),
                "title": r.get("title"),
                "year": r.get("year"),
                "doi": r.get("doi"),
                "match_hits": match_hits(r),
            })
        for f in facet_queries:
            if f.get("hits") is None:
                f["representatives"] = []
                continue
            fterms = query_terms(f["query"])
            reps = sorted(
                primary_records,
                key=lambda r: -sum(
                    1 for t in fterms
                    if t and t in ((r.get("title") or "") + " " + (r.get("evidence") or "")).lower()
                ),
            )[:2]
            f["representatives"] = [
                {"title": r.get("title"), "year": r.get("year"), "doi": r.get("doi")}
                for r in reps
            ]

        usable = []
        for f in facet_queries:
            if f.get("hits") is None:
                continue
            share = (f["hits"] / total_hits) if total_hits else None
            if f["hits"] < GAP_HITS_MAX or (share is not None and share < GAP_SHARE_MAX):
                usable.append(f)
        for f in sorted(usable, key=lambda x: x["hits"])[:3]:
            gaps.append({
                "facet": f["label"],
                "query": f["query"],
                "hits": f["hits"],
                "share": round(f["hits"] / total_hits, 4) if total_hits else None,
                "representatives": f.get("representatives") or [],
                "hypothesis": f"若 {f['label']} 方向确有空白，需在纳入文献引言中找到未覆盖的 {f['label']} 组合；否则删除该候选。",
                "verify": "读代表文献的引言与方法；若已覆盖，删除该候选，不得写入申报书。",
            })

    y1_count = sum(1 for r in primary_records if (r.get("checks") or {}).get("year_ok") is False)
    y1_rate = (y1_count / len(primary_records)) if primary_records else 0.0
    genre_warnings = sum(1 for r in records if r.get("genre_warning"))
    if genre_warnings:
        print(json.dumps({
            "warning": f"{genre_warnings} 条疑似 Perspective/Preview/评论；"
                       "语义判定时需人工确认，勿直接计为 primary。",
        }, ensure_ascii=False), file=sys.stderr)
    if history and y1_rate > 0.4:
        print(json.dumps({
            "warning": f"Y1 率 {y1_rate:.0%} > 40%；建议去掉 --history，"
                       "直接用筛选窗口重跑，避免老论文挤占样本。",
        }, ensure_ascii=False), file=sys.stderr)
    for i, r in enumerate(records, 1):
        r["rank"] = i
        for k in ("_abstract", "_norm_title", "_norm_title_cover", "_norm_first_author"):
            r.pop(k, None)

    background_filter = (
        ",".join(supplemental_filter_parts("background", from_year, to_year, args.language))
        if background else None
    )
    foundational_filter = (
        ",".join(supplemental_filter_parts("foundational", from_year, to_year, args.language))
        if foundational else None
    )

    meta = {
        "query": args.query,
        "basis": getattr(args, "basis", "") or "",
        "search": search_expr,
        "query_health": health,
        "query_health_detail": health_detail,
        "search_mode": "title_abstract_keywords" if (not exact or exact_fallback) else "exact",
        "exact_fallback": exact_fallback,
        "filter": ",".join(filter_parts),
        "sort": "relevance_score:desc",
        "field": field,
        "field_source": field_source,
        "window_years": window_years,
        "window_source": window_source,
        "discipline": discipline,
        "language_mode": args.language,
        "total_hits": total_hits,
        "returned": len(raw_results),
        "background": background,
        "foundational": foundational,
        "background_filter": background_filter,
        "foundational_filter": foundational_filter,
        "background_hits": background_hits,
        "background_returned": background_returned,
        "background_count": background_count,
        "foundational_hits": foundational_hits,
        "foundational_returned": foundational_returned,
        "foundational_count": foundational_count,
        "extra_cost_credits": extra_cost,
        "facet_queries": facet_queries,
        "facet_count": len([f for f in facet_queries if f.get("hits") is not None]),
        "facet_credits": facet_credits,
        "top5": top5,
        "gaps": gaps,
        "per_page": per_page,
        "dedup_removed": max(0, before - after_dedup),
        "screened": len(records),
        "api_year_window": f"{api_from}-01-01/{to_year}-12-31" if api_from and to_year else None,
        "screen_year_window": f"{from_year}-01-01/{to_year}-12-31" if from_year and to_year else None,
        "history": history,
        "y1_rate": round(y1_rate, 4),
        "genre_warnings": genre_warnings,
        "accepted_types": sorted(ACCEPTED_TYPES),
        "chunks": 1,
        "attempt": 1,
        "executed_at": now_iso(),
        "script_version": VERSION,
        "cost_credits": int(ci_get(headers, "X-RateLimit-Credits-Used", SEARCH_COST) or SEARCH_COST) + extra_cost + facet_credits,
        "credits_remaining": ci_get(headers, "X-RateLimit-Remaining"),
        "api_key_used": bool(key),
        "elapsed_ms": int((time.time() - started) * 1000),
        "evidence_limit": evidence_limit,
        "tier": args.tier,
    }
    out = {"meta": meta, "records": records}
    text = json.dumps(out, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def crossref_year(message: dict) -> int | None:
    dates = []
    for field in ("published-print", "published-online", "issued", "created"):
        parts = ((message.get(field) or {}).get("date-parts") or [[]])
        if parts and parts[0] and parts[0][0]:
            dates.append(tuple(parts[0]))
    if not dates:
        return None
    return min(dates)[0]


def has_retraction_update(message: dict) -> bool | str:
    updates = message.get("update-to") or []
    for item in updates:
        if "retract" in str((item or {}).get("type", "")).lower():
            return True
    relation = message.get("relation") or {}
    for key in relation:
        if "retract" in str(key).lower():
            return True
    return "none_found"


def first_title(value) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    return str(value or "")


def title_similarity(a: str, b: str) -> float:
    a_norm, b_norm = normalize_title(a), normalize_title(b)
    if not a_norm or not b_norm:
        return 0.0
    try:
        from rapidfuzz import fuzz  # type: ignore
        full = fuzz.ratio(a_norm, b_norm) / 100.0
    except Exception:
        full = SequenceMatcher(None, a_norm, b_norm).ratio()
    main_a = a_norm.split(":", 1)[0].strip()
    main_b = b_norm.split(":", 1)[0].strip()
    if main_a and main_b and (main_a != a_norm or main_b != b_norm):
        try:
            from rapidfuzz import fuzz  # type: ignore
            main = fuzz.ratio(main_a, main_b) / 100.0
        except Exception:
            main = SequenceMatcher(None, main_a, main_b).ratio()
        full = max(full, main)
    return full


def verify_doi(doi: str, record: dict) -> dict:
    headers = {"User-Agent": user_agent()}
    registrar = "crossref"
    status = 0
    body = ""
    url = CROSSREF_WORKS + quote(doi, safe="/")
    status, _, body = http_get(url, headers=headers, retry_429=True)
    if status == 404:
        registrar = "datacite"
        status, _, body = http_get(DATACITE_DOIS + quote(doi, safe="/"), headers=headers, retry_429=True)

    if status != 200:
        return {
            "doi": doi,
            "registrar": registrar,
            "http_status": status,
            "status": "unavailable" if status == 0 or status >= 500 else "fail",
            "reason": "doi_not_found" if status == 404 else "service_unavailable",
            "title_score": None,
            "matched_title": "",
            "year_delta": None,
            "year_warning": False,
            "retraction_update": "unknown",
        }

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {
            "doi": doi, "registrar": registrar, "http_status": status,
            "status": "fail", "reason": "invalid_json", "title_score": None,
            "matched_title": "", "year_delta": None, "year_warning": False, "retraction_update": "unknown",
        }

    if registrar == "crossref":
        message = payload.get("message") or {}
        ref_title = first_title(message.get("title"))
        ref_year = crossref_year(message)
        retraction = has_retraction_update(message)
    else:
        attrs = ((payload.get("data") or {}).get("attributes") or {})
        titles = attrs.get("titles") or []
        ref_title = str((titles[0] or {}).get("title", "")) if titles else ""
        ref_year = attrs.get("publicationYear")
        retraction = "unknown"

    score = title_similarity(record.get("title", ""), ref_title)
    year = record.get("year")
    year_delta = abs(year - ref_year) if isinstance(year, int) and isinstance(ref_year, int) else None
    title_ok = score >= 0.85
    year_ok = year_delta is None or year_delta <= 1
    pass_ = bool(title_ok and year_ok)
    reason = "" if pass_ else ("title_mismatch" if not title_ok else "year_mismatch")
    return {
        "doi": doi,
        "registrar": registrar,
        "http_status": status,
        "status": "pass" if pass_ else "fail",
        "reason": reason,
        "title_score": round(score, 4),
        "matched_title": ref_title,
        "year_delta": year_delta,
        "year_warning": year_delta == 1,
        "retraction_update": retraction,
    }


def verify_cmd(args) -> int:
    path = Path(args.input)
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records") or []
    started = time.time()
    keys = [(i, r.get("doi") or "") for i, r in enumerate(records) if r.get("doi")]
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, int(args.workers or 3))) as pool:
        futures = {pool.submit(verify_doi, doi, records[i]): i for i, doi in keys}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as exc:  # noqa: BLE001
                results[i] = {
                    "doi": records[i].get("doi"), "registrar": "unknown",
                    "http_status": 0, "status": "unavailable",
                    "reason": f"exception:{type(exc).__name__}", "title_score": None,
                    "matched_title": "", "year_delta": None, "year_warning": False, "retraction_update": "unknown",
                }
    retractions = 0
    year_warnings = 0
    for i, r in enumerate(records):
        if i in results:
            r["verification"] = results[i]
            if results[i].get("retraction_update") is True:
                r["retraction_status"] = "retracted"
                r.setdefault("checks", {})["retracted_ok"] = False
                retractions += 1
            if results[i].get("year_warning"):
                year_warnings += 1
        else:
            r["verification"] = {
                "doi": None, "registrar": None, "http_status": None,
                "status": "unavailable", "reason": "no_doi",
                "title_score": None, "matched_title": "",
                "year_delta": None, "year_warning": False, "retraction_update": "unknown",
            }
    meta = data.setdefault("meta", {})
    meta["verified_at"] = now_iso()
    meta["verify_elapsed_ms"] = int((time.time() - started) * 1000)
    meta["retraction_updates"] = retractions
    meta["year_delta_warnings"] = year_warnings
    meta["verify_cost_credits"] = 0
    text = json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def is_cjk(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text or ""))


def truncate_title(title: str) -> tuple[str, bool]:
    title = (title or "").strip()
    limit = 40 if is_cjk(title) else 80
    if len(title) <= limit:
        return title, False
    return title[: max(0, limit - 1)] + "…", True


def format_author_en(name: str) -> str:
    s = re.sub(r"\s+", " ", (name or "").strip())
    if not s:
        return ""
    if s.upper() == s and " " in s:
        return s
    if "," in s:
        surname, given = s.split(",", 1)
    else:
        parts = s.split()
        if len(parts) == 1:
            return parts[0].upper()
        surname, given = parts[-1], " ".join(parts[:-1])
    surname = surname.strip().upper()
    initials = []
    for token in re.split(r"[\s\-]+", given.strip()):
        token = token.strip(".")
        if token:
            initials.append(token[0].upper())
    return surname + (" " + " ".join(initials) if initials else "")


def format_authors(rec: dict) -> str:
    authors = [a for a in (rec.get("authors") or []) if a]
    if not authors:
        return "[作者待补]"
    count = rec.get("author_count") or len(authors)
    title = rec.get("title") or ""
    if is_cjk(title) or any(is_cjk(a) for a in authors):
        out = ", ".join(authors[:3])
        return out + (", 等" if count > 3 else "")
    out = ", ".join(format_author_en(a) for a in authors[:3])
    return out + (", et al." if count > 3 else "")


TYPE_LABELS = {
    "article": "期刊论文",
    "review": "综述[背景]",
    "preprint": "预印本[未评审]",
    "proceedings-article": "会议论文",
    "conference-paper": "会议论文",
    "conference-abstract": "会议摘要",
    "book-chapter": "图书章节",
    "book": "图书",
    "dissertation": "学位论文",
    "report": "报告",
    "dataset": "数据集",
    "standard": "标准",
}


def type_label(rec: dict) -> str:
    typ = rec.get("type") or ""
    if rec.get("category") == "review":
        return "综述[背景]"
    if rec.get("category") == "background":
        return "背景[奠基]" if rec.get("foundational") else "背景[综述]"
    if rec.get("category") == "preprint":
        return "预印本[未评审]"
    return TYPE_LABELS.get(typ, "其他")


def gbt_tag(rec: dict) -> str:
    typ = rec.get("type") or ""
    return {
        "article": "[J]",
        "review": "[J]",
        "preprint": "[EB/OL]",
        "proceedings-article": "[C]",
        "conference-paper": "[C]",
        "conference-abstract": "[C]",
        "book": "[M]",
        "book-chapter": "[M]",
        "dissertation": "[D]",
        "report": "[R]",
        "standard": "[S]",
        "dataset": "[DS/OL]",
    }.get(typ, "[Z]")


def biblio_parts(rec: dict) -> tuple[str, str]:
    b = rec.get("biblio") or {}
    vol = b.get("volume")
    issue = b.get("issue")
    first = b.get("first_page")
    last = b.get("last_page")
    vol_issue = f"{vol}({issue})" if vol and issue else (str(vol) if vol else "")
    if first and last:
        pages = str(first) if str(first) == str(last) else f"{first}-{last}"
    elif first:
        pages = str(first)
    else:
        pages = ""
    return vol_issue, pages


def render_gbt_entry(rec: dict, label: str) -> str:
    authors = format_authors(rec).rstrip(".")
    title = (rec.get("title") or "题名待补").rstrip(".")
    source = rec.get("source") or "[出版源待补]"
    year = rec.get("year") or "[年份待补]"
    doi = rec.get("doi") or ""
    openalex_id = rec.get("openalex_id") or ""
    vol_issue, pages = biblio_parts(rec)
    tag = gbt_tag(rec)

    if tag == "[J]":
        body = f"{authors}. {title}[J]. {source}, {year}"
        if vol_issue and pages:
            body += f", {vol_issue}: {pages}."
        elif vol_issue:
            body += f", {vol_issue}: [起止页待补]."
        elif pages:
            body += f", [卷期待补]: {pages}."
        else:
            body += ", [卷期页待补]."
    elif tag == "[C]":
        body = f"{authors}. {title}[C]//{source}. {year}"
        body += f": {pages}." if pages else "."
    elif tag == "[M]":
        if rec.get("type") == "book-chapter":
            body = f"{authors}. {title}[M]//{source}. {year}"
            body += f": {pages}." if pages else "."
        else:
            body = f"{authors}. {title}[M]. {source}, {year}."
    elif tag in ("[D]", "[R]", "[S]"):
        body = f"{authors}. {title}{tag}. {source}, {year}."
    elif tag in ("[EB/OL]", "[DS/OL]"):
        url = f"https://doi.org/{doi}" if doi else f"https://openalex.org/{openalex_id}"
        body = f"{authors}. {title}{tag}. ({year})[引用日期待补]. {url}."
    else:
        body = f"{authors}. {title}[Z]. {source}, {year}."

    if doi and tag not in ("[EB/OL]", "[DS/OL]"):
        body += f" DOI: {doi}."
    return f"[{label}] {body}"


def render_gbt7714(data: dict, judgments: list[dict]) -> str:
    by_id = {r.get("openalex_id"): r for r in (data.get("records") or [])}
    primary, background, preprints, pending = [], [], [], []
    for j in judgments:
        rec = by_id.get(j.get("openalex_id"))
        if not rec:
            continue
        verdict = j.get("verdict")
        category = j.get("category") or rec.get("category") or "primary"
        if verdict == "✓":
            if category in ("review", "background"):
                background.append(rec)
            elif category == "preprint":
                preprints.append(rec)
            else:
                primary.append(rec)
        elif verdict == "○":
            pending.append(rec)

    primary_lines = [render_gbt_entry(rec, str(i)) for i, rec in enumerate(primary, 1)]
    background_lines = [render_gbt_entry(rec, f"B{i}") for i, rec in enumerate(background, 1)]
    preprint_lines = [render_gbt_entry(rec, f"P{i}") for i, rec in enumerate(preprints, 1)]
    pending_lines = [render_gbt_entry(rec, f"?{i}") for i, rec in enumerate(pending, 1)]
    draft = any("待补" in line for line in primary_lines + background_lines + preprint_lines)

    lines = ["### 参考文献（GB/T 7714-2015）", ""]
    if draft:
        lines.append("> 草稿：以下条目含待补字段（卷/期/页），正式提交前必须补齐或删除。")
        lines.append("")
    if primary_lines:
        lines.extend(primary_lines)
    else:
        lines.append("本轮无 primary ✓，不生成正式参考文献。")
    if background_lines:
        lines += ["", "### 背景文献（不计入 K）", ""]
        lines.extend(background_lines)
    if preprint_lines:
        lines += ["", "### 预印本（未评审，不计入 K）", ""]
        lines.extend(preprint_lines)
    if pending_lines:
        lines += ["", "### 待核（○，不进正式参考文献）", ""]
        lines.extend(pending_lines)
    return "\n".join(lines)


def sample_caption(judgments: list[dict]) -> str:
    primary = background = preprint = 0
    b_verified = p_verified = 0
    for j in judgments:
        category = j.get("category") or "primary"
        verdict = j.get("verdict")
        if category in ("review", "background"):
            background += 1
            if verdict == "✓":
                b_verified += 1
        elif category == "preprint":
            preprint += 1
            if verdict == "✓":
                p_verified += 1
        else:
            primary += 1
    return (
        f"样本：primary {primary} + background {background}（B={b_verified}）"
        f" + preprint {preprint}（P={p_verified}） = {len(judgments)}"
    )


def render_audit_table(data: dict, judgments: list[dict]) -> str:
    by_id = {r.get("openalex_id"): r for r in (data.get("records") or [])}
    lines = [
        "| # | 标题 | 年 | 类型 | DOI / OpenAlex ID | 判定 | 理由码 | 一句话 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    primary_no = background_no = preprint_no = 0
    for j in judgments:
        rec = by_id.get(j.get("openalex_id")) or {}
        raw_title = rec.get("title") or j.get("title") or ""
        title, truncated = truncate_title(raw_title)
        year = rec.get("year") or ""
        category = j.get("category") or rec.get("category") or "primary"
        rec_for_label = dict(rec)
        rec_for_label["category"] = category
        typ = type_label(rec_for_label)
        if rec.get("genre_warning"):
            typ += " [体裁待核]"
        doi_id = rec.get("doi") or rec.get("openalex_id") or ""
        if truncated and rec.get("doi") and rec.get("openalex_id"):
            doi_id += f" / {rec['openalex_id']}"
        verdict = j.get("verdict") or ""
        if category in ("review", "background"):
            background_no += 1
            label = f"B{background_no}"
            verdict_display = verdict
        elif category == "preprint":
            preprint_no += 1
            label = f"P{preprint_no}"
            verdict_display = verdict
        else:
            primary_no += 1
            label = str(primary_no)
            verdict_display = verdict
        code = j.get("reason_code") or "—"
        one = j.get("one_liner") or ""
        safe = lambda s: str(s).replace("|", "\\|")  # noqa: E731
        lines.append(
            f"| {safe(label)} | {safe(title)} | {safe(year)} | {safe(typ)} | {safe(doi_id)} | "
            f"{safe(verdict_display)} | {safe(code)} | {safe(one)} |"
        )
    return "\n".join(lines)


REASON_LEGEND = {
    "R1": "已撤稿｜结论不可信｜自查：看期刊撤稿声明",
    "P1": "类型不符｜不是你要的文献类型｜自查：看 type",
    "Y1": "年份越界｜太老，方法可能过时｜自查：看 publication_year",
    "L1": "语言不符｜语言不在范围内｜自查：看 language",
    "V1": "版本重复｜预印本与已发表同时命中｜自查：比对 DOI/年份",
    "T1": "主题不符｜和你的题目不是一回事｜自查：读标题和摘要",
    "S1": "体系/对象不符｜材料/样本/对象和你不同｜自查：看摘要体系或样本",
    "M1": "手段/方法不符｜技术路线/研究设计和你不同｜自查：看摘要方法段",
    "C1": "条件/情境不符｜温度/浓度/地区/政策情境不同｜自查：看摘要条件段",
    "I1": "指标/结果不符｜效率/精度/变量口径不同｜自查：看摘要结果段",
    "D1": "无 DOI｜预印本/报告，先别引用｜自查：手动搜标题",
    "D2": "DOI 无法解析｜Crossref/DataCite 都查不到｜自查：点 DOI",
    "D3": "标题不一致｜DOI 指向的标题对不上｜自查：比对 DOI 落地页",
    "D4": "核验服务不可用｜本轮暂时查不了 DOI｜自查：稍后重试",
    "E1": "证据不足｜摘要缺失或没提到关键信息｜自查：读全文再定",
}
LEGEND_ORDER = [
    "R1", "P1", "Y1", "L1", "V1", "T1", "S1", "M1", "C1", "I1",
    "D1", "D2", "D3", "D4", "E1",
]


def render_legend(judgments: list[dict]) -> str:
    used = {
        (j.get("reason_code") or "").strip()
        for j in judgments
        if (j.get("reason_code") or "").strip()
    }
    lines = ["✓ 纳入　○ 待核（不计入纳入数）　× 排除"]
    for code in LEGEND_ORDER:
        if code in used:
            lines.append(f"{code} {REASON_LEGEND[code]}")
    return "\n".join(lines)


def render_header(meta: dict, basis: str | None = None) -> str:
    tier = meta.get("tier") or "循迹"
    reason = basis or meta.get("basis") or "默认档位"
    parts = [f"档位：{tier} ── 依据：{reason}"]
    field = meta.get("field")
    if field and field != "unknown":
        parts.append(f"学科：{field}")
    window = meta.get("screen_year_window")
    if window:
        parts.append(f"时间：{window}")
    language = meta.get("language_mode")
    if language:
        parts.append(f"语言：{language}")
    if "api_key_used" in meta:
        parts.append(f"key：{'已配置' if meta.get('api_key_used') else '未配置'}")
    return "｜".join(parts)


def chinese_coverage_note(meta: dict) -> str | None:
    language = meta.get("language_mode") or ""
    if "zh" in language:
        return (
            "[中文覆盖] OpenAlex 中文期刊覆盖有限；本结果不代表中文文献已查全，"
            "建议用 CNKI/万方补充。"
        )
    return None


def render_suiji(meta: dict) -> str:
    if meta.get("tier") != "溯迹":
        return ""
    parts = ["### 簇计数表（同窗口命中，不是全库）", ""]
    facets = meta.get("facet_queries") or []
    if facets:
        parts += ["| 子方向 | 同窗口命中 | 占本轮命中 | 词面代表文献 |", "|---|---|---|---|"]
        for facet in facets:
            hits = facet.get("hits")
            share = "—"
            if hits is not None and meta.get("total_hits"):
                share = f"{hits / meta['total_hits']:.1%}"
            reps = "；".join(
                f"{truncate_title(r.get('title') or '')[0]} ({r.get('year')})"
                for r in (facet.get("representatives") or [])
            ) or "—"
            parts.append(
                f"| {facet.get('label')} | {hits if hits is not None else '—'} | "
                f"{share} | {reps.replace('|', chr(92) + '|')} |"
            )
        parts += [
            "",
            f"注：同窗口 = {meta.get('screen_year_window', '')} + "
            f"{meta.get('language_mode', '')}；子方向可重叠，占比不可相加；不是 OpenAlex 全库。"
            "代表文献按词面命中取前 2，不保证语义匹配。",
        ]
    else:
        parts.append("本轮无 facet 数据。")

    top5 = meta.get("top5") or []
    parts += ["", "### 近邻工作 Top5（词面命中排序；语义需人工确认）", ""]
    if top5:
        parts += ["| # | 标题 | 年 | DOI | 词面命中数 |", "|---|---|---|---|---|"]
        for row in top5:
            parts.append(
                f"| {row.get('rank')} | {truncate_title(row.get('title') or '')[0]} | "
                f"{row.get('year')} | {row.get('doi') or row.get('openalex_id')} | "
                f"{row.get('match_hits')} |"
            )
    else:
        parts.append("本轮无 Top5。")

    gaps = meta.get("gaps") or []
    parts += ["", "### 缺口候选（不是结论）", ""]
    if gaps:
        for i, gap in enumerate(gaps, 1):
            reps = "；".join(
                f"{truncate_title(r.get('title') or '')[0]} ({r.get('year')})"
                for r in (gap.get("representatives") or [])
            ) or "代表文献待补"
            share = f"{gap['share']:.1%}" if gap.get("share") is not None else "—"
            parts.append(
                f"{i}. 现象：{gap.get('facet')} 同窗口命中 {gap.get('hits')}（占 {share}）"
                f"｜需读（词面代表）：{reps}｜可证伪假设：{gap.get('hypothesis')}｜验证：{gap.get('verify')}"
            )
    else:
        parts.append(
            "本轮各子方向覆盖率均高于阈值（hits≥50 且 share≥5%），"
            "未发现可论证缺口。"
        )
    return "\n".join(parts)


def render_tail(meta: dict) -> str:
    lines = []
    if meta.get("tier") == "溯迹" and meta.get("gaps"):
        lines.append(
            "这一簇缺失模式可能提示可论证的空白，但这是检索证据，不是结论。"
            "必须阅读纳入文献的引言确认，不得直接写入申报书。"
        )
    lines += [
        "已核验 ≠ 内容优质，也不等于元数据全对；请点开 DOI 看摘要。",
        "本 Skill 不提供全文；专利与标准不在 OpenAlex 覆盖范围，请用 Google Patents / CNIPA 另查。",
        "负结果少发表，计数低 ≠ 空白；需结合发表偏倚判断。",
    ]
    return "─\n\n" + "\n".join(lines)


def fallback_supplemental_filter(meta: dict, kind: str) -> str | None:
    screen = meta.get("screen_year_window") or ""
    if "/" not in screen:
        return None
    start_s, end_s = screen.split("/", 1)
    try:
        start_year = int(start_s[:4])
    except ValueError:
        return None
    if kind == "background":
        parts = [
            f"from_publication_date:{max(1, start_year - 10)}-01-01",
            f"to_publication_date:{end_s}",
        ]
    else:
        parts = [f"to_publication_date:{end_s}"]
    language = meta.get("language_mode")
    if language and language != "all":
        parts.append(f"language:{language}")
    return ",".join(parts)


def render_repro_block(data: dict, judgments: list[dict], summary: dict) -> str:
    meta = data.get("meta") or {}
    counts = summary.get("counts") or {}
    xcodes = Counter(
        j.get("reason_code") for j in judgments
        if j.get("verdict") == "×" and j.get("reason_code")
    )
    ocodes = Counter(
        j.get("reason_code") for j in judgments
        if j.get("verdict") == "○" and j.get("reason_code")
    )
    def fmt(counter: Counter) -> str:
        return ", ".join(f"{k}:{v}" for k, v in sorted(counter.items())) or "—"
    key_used = "true" if meta.get("api_key_used") else "false"
    bg_filter = meta.get("background_filter") or (
        fallback_supplemental_filter(meta, "background") if meta.get("background") else None
    )
    fg_filter = meta.get("foundational_filter") or (
        fallback_supplemental_filter(meta, "foundational") if meta.get("foundational") else None
    )
    lines = ["```"]
    executed = meta.get("executed_at")
    if executed:
        lines.append(f"本研究以 OpenAlex 为数据源，于 {executed} 执行检索：")
    else:
        lines.append("本研究以 OpenAlex 为数据源执行检索：")
    search = meta.get("search")
    if search:
        lines.append(f"search: `{search}`")
    filter_text = meta.get("filter")
    if filter_text:
        lines.append(f"filter: `{filter_text}`")
    health = meta.get("query_health")
    detail = meta.get("query_health_detail") or {}
    detail_parts = []
    for key, label in (("has_boolean", "boolean"), ("has_quote", "quote"), ("concepts", "concepts")):
        if detail.get(key) is not None:
            detail_parts.append(f"{label}={detail[key]}")
    if health:
        suffix = f"（{', '.join(detail_parts)}）" if detail_parts else ""
        lines.append(f"search_health: {health}{suffix}")

    sort_parts = []
    if meta.get("sort"):
        sort_parts.append(f"sort {meta['sort']}")
    for key, label in (("per_page", "per_page"), ("returned", "returned"),
                       ("dedup_removed", "dedup"), ("screened", "screened")):
        if meta.get(key) is not None:
            sort_parts.append(f"{label} {meta[key]}")
    if sort_parts:
        lines.append(" | ".join(sort_parts))

    field_parts = []
    if meta.get("field") and meta.get("field") != "unknown":
        field_parts.append(f"field {meta['field']}")
    if meta.get("window_years") is not None:
        window = f"window {meta['window_years']}y"
        if meta.get("window_source"):
            window += f" ({meta['window_source']})"
        field_parts.append(window)
    if meta.get("screen_year_window"):
        field_parts.append(f"screen_year {meta['screen_year_window']}")
    if meta.get("api_year_window"):
        field_parts.append(f"api_year {meta['api_year_window']}")
    if meta.get("language_mode"):
        field_parts.append(f"language {meta['language_mode']}")
    if field_parts:
        lines.append(" | ".join(field_parts))

    if "history" in meta:
        history = f"history {str(meta['history']).lower()}"
        if meta.get("y1_rate") is not None:
            history += f" | y1_rate {meta['y1_rate']}"
        lines.append(history)

    n_parts = []
    if meta.get("total_hits") is not None:
        n_parts.append(f"N={meta['total_hits']}")
    n_parts += [
        f"X={counts.get('X', 0)}（{fmt(xcodes)}）",
        f"O={counts.get('O', 0)}（{fmt(ocodes)}）",
        f"K={counts.get('K', 0)}",
        f"B={counts.get('B', 0)}",
        f"P={counts.get('P', 0)}",
    ]
    lines.append(" | ".join(n_parts))

    bg_parts = []
    if meta.get("background") is not None:
        bg_parts.append(
            f"background={meta.get('background_count', 0)} (hits {meta.get('background_hits', 0)})"
        )
    if meta.get("foundational") is not None:
        bg_parts.append(
            f"foundational={meta.get('foundational_count', 0)} (hits {meta.get('foundational_hits', 0)})"
        )
    if meta.get("extra_cost_credits") is not None:
        bg_parts.append(f"extra_credits={meta['extra_cost_credits']}")
    if bg_parts:
        lines.append(" | ".join(bg_parts))
    if meta.get("facet_queries"):
        lines.append(
            f"facet_queries={meta.get('facet_count', 0)} | "
            f"facet_credits={meta.get('facet_credits', 0)}"
        )
        for facet in meta.get("facet_queries") or []:
            hits = facet.get("hits")
            lines.append(
                f"facet {facet.get('label')}: `{facet.get('query')}` → "
                + (str(hits) if hits is not None else "error")
            )
    if bg_filter or fg_filter:
        lines.append(
            f"background_filter: {bg_filter or '—'} | foundational_filter: {fg_filter or '—'}"
        )

    cost_parts = []
    if meta.get("cost_credits") is not None:
        cost_parts.append(f"credits={meta['cost_credits']}")
    if meta.get("elapsed_ms") is not None:
        cost_parts.append(f"elapsed={meta['elapsed_ms']}ms")
    if meta.get("verify_elapsed_ms") is not None:
        cost_parts.append(f"verify_elapsed={meta['verify_elapsed_ms']}ms")
    if "api_key_used" in meta:
        cost_parts.append(f"api_key_used={key_used}")
    if cost_parts:
        lines.append(" | ".join(cost_parts))

    lines.append("本结果按相关度取前 M 条，属非穷尽检索，不等同于系统综述。")
    lines.append("```")
    return "\n".join(lines)


def audit_template(data: dict) -> dict:
    rows = []
    for r in data.get("records") or []:
        rows.append({
            "openalex_id": r.get("openalex_id"),
            "title": r.get("title"),
            "year": r.get("year"),
            "type": r.get("type"),
            "doi": r.get("doi"),
            "verdict": "",
            "reason_code": "",
            "category": r.get("category", "primary"),
            "evidence_quote": "",
            "one_liner": "",
        })
    return {"mode": "semantic", "records": rows}


def audit_cmd(args) -> int:
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.template:
        print(json.dumps(audit_template(data), ensure_ascii=False, indent=2))
        return 0
    if not args.judgments:
        raise TraceLitError("audit 需要 --judgments，或使用 --template 生成模板。")
    judgments_raw = json.loads(Path(args.judgments).read_text(encoding="utf-8"))
    mode_raw = judgments_raw.get("mode") if isinstance(judgments_raw, dict) else None
    mode = mode_raw.strip() if isinstance(mode_raw, str) else mode_raw
    mode_valid = mode in ("semantic", "mechanical_smoke")
    mode_error = None if mode_valid else (
        "judgments.mode 必须显式声明 semantic 或 mechanical_smoke"
    )
    judgments = judgments_raw.get("records") if isinstance(judgments_raw, dict) else judgments_raw
    if not isinstance(judgments, list):
        raise TraceLitError("judgments 必须是 list 或 {mode, records}。")
    if mode_error and args.format == "md" and not getattr(args, "allow_unlabeled", False):
        raise TraceLitError(mode_error + "；当前未声明，拒绝渲染。")
    if mode == "mechanical_smoke" and args.format == "md" and not getattr(args, "allow_smoke", False):
        raise TraceLitError(
            "拒绝渲染机械冒烟报告：其中没有 T1/S1/M1/C1/I1 语义判定。"
            "如仅用于测试，请加 --allow-smoke。"
        )

    by_id = {r.get("openalex_id"): r for r in (data.get("records") or [])}
    errors, warnings = [], []
    if mode_error:
        errors.append(mode_error)
    seen = set()
    counts = {"X": 0, "O": 0, "K": 0, "B": 0, "P": 0}
    for j in judgments:
        oid = j.get("openalex_id")
        rec = by_id.get(oid)
        if not rec:
            errors.append(f"未知 openalex_id: {oid}")
            continue
        if oid in seen:
            errors.append(f"重复判定: {oid}")
        seen.add(oid)
        verdict = j.get("verdict")
        code = (j.get("reason_code") or "").strip()
        category = j.get("category") or rec.get("category") or "primary"
        if verdict not in VERDICTS:
            errors.append(f"{oid}: verdict 必须是 ✓/×/○")
            continue
        quote = (j.get("evidence_quote") or "").strip()
        needs_quote = verdict == "✓" or (verdict == "×" and code in SEMANTIC_CODES)
        if needs_quote and not quote:
            errors.append(f"{oid}: 缺少 evidence_quote")
        if quote:
            haystack = ((rec.get("evidence") or "") + "\n" + (rec.get("title") or ""))
            if normalize_quote(quote) not in normalize_quote(haystack):
                errors.append(f"{oid}: evidence_quote 不在 evidence/title 中")
        if verdict == "✓":
            if code not in ("", "-", "—", "B", "P"):
                errors.append(f"{oid}: ✓ 不应带排除码 {code}")
            if category not in ("primary", "review", "background", "preprint"):
                errors.append(f"{oid}: category 非法 {category}")
            verification = rec.get("verification") or {}
            if verification.get("status") != "pass":
                errors.append(f"{oid}: ✓ 但 DOI 核验未 pass")
            if category == "primary":
                counts["K"] += 1
            elif category in ("review", "background"):
                counts["B"] += 1
            else:
                counts["P"] += 1
        elif verdict == "×":
            if code not in EXCLUDE_CODES:
                errors.append(f"{oid}: × 的理由码非法 {code}")
            counts["X"] += 1
        else:
            if code not in PENDING_CODES:
                errors.append(f"{oid}: ○ 的理由码非法 {code}")
            counts["O"] += 1
        one = (j.get("one_liner") or "").strip()
        if not one:
            errors.append(f"{oid}: 一句话为空")
        elif len(one) > 24:
            errors.append(f"{oid}: 一句话超过 24 字")

    missing = [oid for oid in by_id if oid not in seen]
    if missing:
        warnings.append(f"{len(missing)} 条记录没有判定")
    total = counts["X"] + counts["O"] + counts["K"] + counts["B"] + counts["P"]
    m = (data.get("meta") or {}).get("screened") or len(by_id)
    if total != m:
        errors.append(f"计数不闭合：X+O+K+B+P={total}，M={m}")
    if counts["K"] < 3:
        warnings.append(f"K={counts['K']} < 3：应先调类型/主题词或放宽，不要直接收尾。")
    smoke_mode = mode == "mechanical_smoke"
    if smoke_mode:
        inclusion_rate = None
        broad_search = None
        sample_alert = False
    else:
        inclusion_rate = ((counts["K"] + counts["B"] + counts["P"]) / m) if m else 0.0
        total_hits = (data.get("meta") or {}).get("total_hits")
        broad_search = (
            isinstance(total_hits, int) and m > 0 and total_hits > 10 * m
        )
        sample_alert = broad_search and (inclusion_rate > 0.9 or counts["X"] == 0)

    meta = data.get("meta") or {}
    genre_rows = [r for r in (data.get("records") or []) if r.get("genre_warning")]
    summary = {
        "ok": not errors,
        "mode": mode if mode_valid else "unlabeled",
        "counts": {**counts, "M": m},
        "sample_health": {
            "inclusion_rate": round(inclusion_rate, 4) if inclusion_rate is not None else None,
            "broad_search": broad_search,
            "alert": sample_alert,
            "note": (
                "mechanical_smoke: X=0 expected; semantic judgment not applied"
                if smoke_mode else None
            ),
            "y1_rate": meta.get("y1_rate"),
            "genre_warnings": len(genre_rows),
            "year_delta_warnings": meta.get("year_delta_warnings", 0),
        },
        "cost": {
            "search_credits": meta.get("cost_credits"),
            "verify_credits": meta.get("verify_cost_credits"),
            "elapsed_ms": meta.get("elapsed_ms"),
            "verify_elapsed_ms": meta.get("verify_elapsed_ms"),
            "api_key_used": meta.get("api_key_used"),
        },
        "errors": errors,
        "warnings": warnings,
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if errors and args.format == "md" and not getattr(args, "allow_errors", False):
        raise TraceLitError("审计校验失败，拒绝渲染报告：" + "; ".join(errors[:3]))
    if args.format == "md":
        banners = []
        if not mode_valid:
            banners.append(
                "[未声明判定模式·不可信] judgments.mode 缺失或非法；"
                "本报告可能是未经语义判定的机械结果。"
            )
        if mode == "mechanical_smoke":
            banners.append(
                "[机械冒烟·非语义判定] 本报告只验证计数/渲染；"
                "T1/S1/M1/C1/I1 未判，不得作为最终筛选结果。"
            )
        zh_note = chinese_coverage_note(meta)
        if zh_note:
            banners.append(zh_note)
        if meta.get("query_health") and meta.get("query_health") != "ok":
            banners.append(
                f"[检索式体检] {meta.get('query_health')}：未见布尔/引号，"
                "样本可能只覆盖领域一角。"
            )
        if sample_alert:
            total_hits = (data.get("meta") or {}).get("total_hits")
            banners.append(
                f"[样本体检] N={total_hits} 远大于 M={m}，"
                f"纳入率 {inclusion_rate:.0%}，X={counts['X']}；"
                "检索式可能过窄或筛选未生效，请抽查。"
            )
        if (meta.get("y1_rate") or 0) > 0.4:
            banners.append(
                f"[样本体检] Y1 率 {meta.get('y1_rate'):.0%} > 40%；"
                "老论文挤占样本，建议去掉 --history 重跑。"
            )
        if genre_rows:
            gw_ids = ", ".join(
                f"#{r.get('rank')} {r.get('openalex_id')}" for r in genre_rows[:8]
            )
            banners.append(
                f"[体裁体检] {len(genre_rows)} 条（{gw_ids}）；"
                "语义判定时需人工确认，勿直接计为 primary。"
            )
        if meta.get("year_delta_warnings", 0):
            banners.append(
                f"[元数据体检] {meta.get('year_delta_warnings')} 条年份偏差=1；"
                "可能是在线优先/卷期年不一致，需人工核对。"
            )
        parts = []
        if banners:
            parts.append("\n".join(banners))
        parts.append(render_header(meta, getattr(args, "basis", None)))
        parts.append(sample_caption(judgments))
        parts.append(render_audit_table(data, judgments))
        parts.append(render_legend(judgments))
        parts.append(render_repro_block(data, judgments, summary))
        parts.append(render_gbt7714(data, judgments))
        suiji = render_suiji(meta)
        if suiji:
            parts.append(suiji)
        parts.append(render_tail(meta))
        md = "\n\n".join(parts)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md + "\n", encoding="utf-8")
        print(md)
        print(text, file=sys.stderr)
    else:
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text + "\n", encoding="utf-8")
        print(text)
    if errors and args.strict:
        return 1
    return 0


def doctor_cmd(args) -> int:
    key = get_key(args.api_key)
    py_ok = sys.version_info >= (3, 10)
    tls_ok = True
    tls_error = ""
    try:
        ssl_context()
    except Exception as exc:  # noqa: BLE001
        tls_ok = False
        tls_error = str(exc)
    optional = {}
    for mod in ("rapidfuzz", "certifi"):
        try:
            __import__(mod)
            optional[mod] = True
        except Exception:
            optional[mod] = False
    rate = None
    budget_ok = None
    if key:
        status, headers, body = http_get(
            OPENALEX_RATE,
            headers={"Authorization": f"Bearer {key}"},
        )
        rate = {
            "http_status": status,
            "remaining": ci_get(headers, "X-RateLimit-Remaining"),
            "limit": ci_get(headers, "X-RateLimit-Limit"),
            "reset": ci_get(headers, "X-RateLimit-Reset"),
        }
        try:
            payload = json.loads(body)
            limits = payload.get("rate_limit") or {}
            rate.update({
                "daily_budget_usd": limits.get("daily_budget_usd"),
                "daily_used_usd": limits.get("daily_used_usd"),
                "daily_remaining_usd": limits.get("daily_remaining_usd"),
                "resets_at": limits.get("resets_at"),
            })
        except json.JSONDecodeError:
            rate["body"] = "non-json response"
        budget_ok = status == 200
        if rate.get("daily_remaining_usd") is not None:
            budget_ok = budget_ok and float(rate["daily_remaining_usd"]) > 0
    ok = (
        py_ok and tls_ok
        and (bool(key) or args.tier == "寻迹")
        and (budget_ok is not False)
    )
    out = {
        "ok": ok,
        "python": sys.version.split()[0],
        "python_ok": py_ok,
        "tls_ok": tls_ok,
        "tls_error": tls_error,
        "key_present": bool(key),
        "key_url": KEY_URL,
        "tier": args.tier,
        "tier_needs_key": args.tier in ("循迹", "溯迹"),
        "budget_ok": budget_ok,
        "optional": optional,
        "openalex_rate": rate,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def _docx_para(text: str, bold: bool = False, size: int | None = None,
               mono: bool = False) -> str:
    props = []
    if bold:
        props.append("<w:b/>")
    if size:
        props.append(f'<w:sz w:val="{size}"/>')
    if mono:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="SimSun"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return (
        f'<w:p><w:r>{rpr}<w:t xml:space="preserve">'
        f"{xml_escape(text)}</w:t></w:r></w:p>"
    )


def _docx_table(rows: list[list[str]]) -> str:
    max_cols = max((len(r) for r in rows), default=1)
    grid = "".join('<w:gridCol w:w="1200"/>' for _ in range(max_cols))
    borders = (
        "<w:tblBorders>"
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        "</w:tblBorders>"
    )
    out = [
        "<w:tbl><w:tblPr>"
        '<w:tblW w:w="5000" w:type="pct"/>'
        f"{borders}</w:tblPr><w:tblGrid>{grid}</w:tblGrid>"
    ]
    for i, row in enumerate(rows):
        cells = "".join(
            "<w:tc><w:tcPr>"
            '<w:tcW w:w="0" w:type="auto"/>'
            f"</w:tcPr>{_docx_para(cell, bold=(i == 0), size=16)}</w:tc>"
            for cell in row
        )
        out.append(f"<w:tr>{cells}</w:tr>")
    out.append("</w:tbl><w:p/>")
    return "".join(out)


def markdown_to_docx(markdown: str, out_path: str) -> None:
    lines = markdown.splitlines()
    parts: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            for row in code:
                parts.append(_docx_para(row, size=16, mono=True))
            continue
        if line.strip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip().strip("|")
                cells = [c.strip() for c in raw.split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                parts.append(_docx_table(rows))
            continue
        if line.startswith("### "):
            parts.append(_docx_para(line[4:].strip(), bold=True, size=24))
        elif line.startswith("## "):
            parts.append(_docx_para(line[3:].strip(), bold=True, size=28))
        elif line.startswith("# "):
            parts.append(_docx_para(line[2:].strip(), bold=True, size=32))
        elif line.startswith("> "):
            parts.append(_docx_para(line[2:].strip(), size=20))
        elif line.strip() in ("─", "---", "***"):
            parts.append(_docx_para("─", size=20))
        else:
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            parts.append(_docx_para(text, size=20))
        i += 1

    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        + "".join(parts)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
        'w:header="709" w:footer="709" w:gutter="0"/></w:sectPr>'
        "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
    )
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)


def docx_cmd(args) -> int:
    markdown = Path(args.input).read_text(encoding="utf-8")
    markdown_to_docx(markdown, args.out)
    print(json.dumps({
        "ok": True,
        "out": args.out,
        "bytes": Path(args.out).stat().st_size,
    }, ensure_ascii=False))
    return 0


def run_cmd(args) -> int:
    if args.docx and not args.judgments:
        raise TraceLitError("--docx 需要同时提供 --judgments。")
    out_dir = Path(args.out_dir or f"runs/run-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    out_dir.mkdir(parents=True, exist_ok=True)
    search_out = out_dir / "search.json"
    verify_out = out_dir / "verified.json"
    template_out = out_dir / "judgments.template.json"
    search_args = Namespace(
        query=args.query, search=args.search, filter=args.filter,
        discipline="social" if args.field == "social" else "stem",
        language=args.language, from_year=args.from_year, to_year=args.to_year,
        per_page=args.per_page, tier=args.tier, out=str(search_out),
        dry_run=args.dry_run, api_key=args.api_key, pretty=False,
        field=args.field, background=args.background,
        foundational=args.foundational, history=args.history,
        basis=args.basis, exact=args.exact, facet=args.facet,
    )
    if args.dry_run:
        return search_cmd(search_args)
    with contextlib.redirect_stdout(io.StringIO()):
        search_cmd(search_args)
    verify_args = Namespace(
        input=str(search_out), out=str(verify_out), workers=3, pretty=False,
    )
    with contextlib.redirect_stdout(io.StringIO()):
        verify_cmd(verify_args)
    data = json.loads(verify_out.read_text(encoding="utf-8"))
    template_out.write_text(
        json.dumps(audit_template(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_path = None
    docx_path = None
    if args.judgments:
        report_path = out_dir / "report.md"
        audit_args = Namespace(
            input=str(verify_out), judgments=args.judgments,
            out=str(report_path), format="md", template=False, strict=False,
            allow_smoke=False, allow_unlabeled=False, allow_errors=False,
            basis=args.basis,
        )
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            audit_cmd(audit_args)
        if args.docx:
            docx_path = out_dir / "report.docx"
            with contextlib.redirect_stdout(io.StringIO()):
                docx_cmd(Namespace(input=str(report_path), out=str(docx_path)))
    summary = {
        "ok": True,
        "search": str(search_out),
        "verified": str(verify_out),
        "template": str(template_out),
        "judgments": args.judgments,
        "report": str(report_path) if report_path else None,
        "docx": str(docx_path) if docx_path else None,
        "next": None if args.judgments else (
            f"fill {template_out}, then: "
            f"audit --input {verify_out} --judgments <filled> --format md "
            f"--out {out_dir / 'report.md'}; "
            f"docx --input {out_dir / 'report.md'} --out {out_dir / 'report.docx'}"
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="TraceLit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="OpenAlex 检索与机械筛选")
    s.add_argument("--query", required=True)
    s.add_argument("--search", default=None, help="显式布尔式；省略则用 --query")
    s.add_argument("--exact", action="store_true", help="使用 search.exact；400 时自动退回 title_abstract_keywords")
    s.add_argument("--basis", default="", help="触发依据；写入报告首行")
    s.add_argument("--filter", default=None, help="显式 filter；省略则按年份/语言生成")
    s.add_argument("--field", choices=["cs", "materials", "math", "social", "unknown"], default=None,
                   help="学科窗口；省略时按 query 关键词推断")
    s.add_argument("--discipline", choices=["stem", "social"], default=None,
                   help="维度词轨道；通常由 --field 推导")
    s.add_argument("--language", choices=["en", "en|zh", "zh", "all"], default="en")
    s.add_argument("--from-year", type=int, default=None)
    s.add_argument("--to-year", type=int, default=None)
    s.add_argument("--history", action="store_true", help="API 回溯 5 年供 Y1 审计；默认只用筛选窗口")
    s.add_argument("--background", dest="background", action="store_true", default=None,
                   help="额外检索背景综述（默认循迹/溯迹开启）")
    s.add_argument("--no-background", dest="background", action="store_false",
                   help="关闭背景综述 pass")
    s.add_argument("--foundational", action="store_true", help="额外检索高被引奠基文献")
    s.add_argument("--facet", action="append", default=None,
                   help="溯迹 facet 子查询，可重复 3–5 次；格式 label=expr")
    s.add_argument("--per-page", type=int, default=MAX_PER_PAGE)
    s.add_argument("--tier", choices=["寻迹", "循迹", "溯迹"], default="循迹")
    s.add_argument("--out", default=None)
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--api-key", default=None)
    s.add_argument("--pretty", action="store_true")
    s.set_defaults(func=search_cmd)

    v = sub.add_parser("verify", help="Crossref/DataCite DOI 核验")
    v.add_argument("--input", required=True)
    v.add_argument("--out", default=None)
    v.add_argument("--workers", type=int, default=3)
    v.add_argument("--pretty", action="store_true")
    v.set_defaults(func=verify_cmd)

    a = sub.add_parser("audit", help="校验判定与计数，或生成模板")
    a.add_argument("--input", required=True)
    a.add_argument("--judgments", default=None)
    a.add_argument("--out", default=None)
    a.add_argument("--format", choices=["json", "md"], default="json")
    a.add_argument("--template", action="store_true")
    a.add_argument("--strict", action="store_true")
    a.add_argument("--allow-smoke", action="store_true", help="仅测试：允许渲染 mechanical_smoke 报告")
    a.add_argument("--allow-errors", action="store_true", help="仅测试：允许在校验失败时渲染报告")
    a.add_argument("--allow-unlabeled", action="store_true", help="仅测试：允许渲染未声明 mode 的 judgments")
    a.add_argument("--basis", default=None, help="覆盖首行的触发依据")
    a.set_defaults(func=audit_cmd)

    d = sub.add_parser("doctor", help="检查 key、预算、TLS、依赖")
    d.add_argument("--api-key", default=None)
    d.add_argument("--tier", choices=["寻迹", "循迹", "溯迹"], default="循迹")
    d.set_defaults(func=doctor_cmd)

    r = sub.add_parser("run", help="search + verify + template（可选 audit/docx）")
    r.add_argument("--query", required=True)
    r.add_argument("--search", default=None)
    r.add_argument("--filter", default=None)
    r.add_argument("--field", choices=["cs", "materials", "math", "social", "unknown"], default="unknown")
    r.add_argument("--language", choices=["en", "en|zh", "zh", "all"], default="en")
    r.add_argument("--from-year", type=int, default=None)
    r.add_argument("--to-year", type=int, default=None)
    r.add_argument("--per-page", type=int, default=MAX_PER_PAGE)
    r.add_argument("--tier", choices=["寻迹", "循迹", "溯迹"], default="循迹")
    r.add_argument("--background", dest="background", action="store_true", default=None)
    r.add_argument("--no-background", dest="background", action="store_false")
    r.add_argument("--foundational", action="store_true")
    r.add_argument("--history", action="store_true")
    r.add_argument("--facet", action="append", default=None)
    r.add_argument("--basis", default="")
    r.add_argument("--out-dir", default=None)
    r.add_argument("--judgments", default=None)
    r.add_argument("--docx", action="store_true")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--api-key", default=None)
    r.add_argument("--exact", action="store_true")
    r.set_defaults(func=run_cmd)

    x = sub.add_parser("docx", help="把 audit 的 Markdown 报告转成 docx")
    x.add_argument("--input", required=True)
    x.add_argument("--out", required=True)
    x.set_defaults(func=docx_cmd)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except TraceLitError as exc:
        payload = {"ok": False, "error": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, (AuthError, BudgetError)):
            payload["key_url"] = KEY_URL
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "ok": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
