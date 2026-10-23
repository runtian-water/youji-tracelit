# API 契约（脚本 ↔ LLM）

## 1. OpenAlex 请求

- Endpoint：`https://api.openalex.org/works`
- 认证：`Authorization: Bearer $OPENALEX_API_KEY`
  - 寻迹：key 可选。
  - 循迹/溯迹：必须有 key。
  - 不要再用 `mailto` 作为鉴权；改用 API key（`Authorization: Bearer`）。
- 参数：
  - `search.title_abstract_keywords=<boolean>`（默认检索层）
  - `search.exact=<query>`（仅在通配符/去词干必需时；一次请求只能用一种 search 模式）
  - `filter=from_publication_date:...,to_publication_date:...,language:en`；类型默认不过滤，由脚本判 P1。
  - `sort=relevance_score:desc`
  - `per_page=100`（支持上限；`200` 为 legacy，随时可能移除）
  - `cursor=*`（深分页；第一页之后需要 key）
- 成本：`search` = 10 credits；`filter/list` = 1 credit；单条 DOI/ID 查询免费。
- 响应头：`X-RateLimit-Limit`、`X-RateLimit-Remaining`、`X-RateLimit-Credits-Used`、`X-RateLimit-Reset`。

## 2. search 输出（精简 JSON）

```json
{
  "meta": {
    "query": "用户原话",
    "basis": "未命中特定信号，取安全超集",
    "search": "...",
    "query_health": "ok",
    "filter": "...",
    "sort": "relevance_score:desc",
    "per_page": 100,
    "field": "materials",
    "field_source": "explicit",
    "window_years": 5,
    "window_source": "field",
    "discipline": "stem",
    "language_mode": "en",
    "search_mode": "title_abstract_keywords",
    "exact_fallback": false,
    "total_hits": 1234,
    "returned": 100,
    "dedup_removed": 3,
    "screened": 25,
    "api_year_window": "2016-01-01/2026-12-31",
    "screen_year_window": "2021-01-01/2026-12-31",
    "history": false,
    "y1_rate": 0.0,
    "genre_warnings": 0,
    "background": true,
    "foundational": false,
    "background_filter": "from_publication_date:2011-01-01,to_publication_date:2026-12-31,language:en",
    "foundational_filter": null,
    "background_hits": 996,
    "background_returned": 5,
    "background_count": 3,
    "foundational_hits": 0,
    "foundational_returned": 0,
    "foundational_count": 0,
    "extra_cost_credits": 10,
    "facet_queries": [
      {
        "label": "技术路线",
        "query": "...",
        "hits": 1287,
        "cost_credits": 10,
        "representatives": [{"title": "...", "year": 2023, "doi": "10.1/x"}]
      }
    ],
    "facet_count": 3,
    "facet_credits": 30,
    "top5": [
      {"rank": 1, "openalex_id": "W...", "title": "...", "year": 2021,
       "doi": "10.1/x", "match_hits": 12}
    ],
    "gaps": [
      {"facet": "技术路线", "query": "...", "hits": 1287, "share": 0.1637,
       "representatives": [{"title": "...", "year": 2023, "doi": "10.1/x"}],
       "hypothesis": "...", "verify": "..."}
    ],
    "accepted_types": ["article", "review", "preprint", "proceedings-article", "conference-paper", "book-chapter", "book", "dissertation", "report"],
    "chunks": 1,
    "attempt": 1,
    "executed_at": "2026-10-22T11:00:00Z",
    "script_version": "0.5.0",
    "cost_credits": 10,
    "credits_remaining": 9990,
    "api_key_used": true,
    "elapsed_ms": 850,
    "evidence_limit": 600
  },
  "records": [{
    "rank": 1,
    "openalex_id": "W1234567890",
    "title": "原文，不翻译",
    "doi": "10.1234/abc",
    "year": 2021,
    "type": "article",
    "language": "en",
    "authors": ["A", "B", "C"],
    "author_count": 5,
    "source": "Journal Name",
    "biblio": {"volume": "12", "issue": "3", "first_page": "45", "last_page": "67"},
    "cited_by_count": 12,
    "is_retracted": false,
    "retraction_status": "not_retracted",
    "version_duplicate": false,
    "checks": {
      "year_ok": true,
      "type_ok": true,
      "language_ok": true,
      "retracted_ok": true,
      "version_ok": true
    },
    "category": "primary",
    "background": false,
    "foundational": false,
    "genre_warning": false,
    "evidence": "摘要中与检索词/维度词相关的 2–4 句逐字文本，≤600（寻迹/循迹）或 ≤1200（溯迹）",
    "evidence_field": "abstract"
  }]
}
```

字段约束：

- `title`、`authors` 原样，不翻译、不改写。
- `authors` 只回前 3 位；`author_count` 用于判断是否加“等/et al.”。
- `category`：`primary`（原始研究）、`review`（综述）、`background`（背景/奠基）、`preprint`（预印本）。
- `background`/`foundational`：来自额外 pass 的标记；`category=background` 计入 B，不占 K。
- `background_filter`/`foundational_filter`：额外 pass 的实际 filter，必须在复现块展示。
- `facet_queries`/`top5`/`gaps`：仅溯迹；`facet_count` 是成功计数的 facet 数，`facet_credits` 是额外成本；`match_hits` 是词面命中数，不是体系/手段语义匹配，也不是相关度分数；`gaps` 只是候选，不是结论；只有 `hits < 50` 或 `share < 5%` 的 facet 才进入，全部高于阈值时为空。
- `category=preprint` 只用于 DOI 核验 pass 的预印本；无 DOI 的预印本仍留在 records 里，由 LLM 判 `○ D1`，不进 `P`。
- `retraction_status`：`not_retracted|retracted|unknown`；`null` 不能当 `false`。
- `evidence_field`：`abstract|title`；无摘要时为 `title`，对象/方法/条件/指标一律由 LLM 判 `E1`。
- `checks` 是脚本的机械判定；LLM 不重算年份、类型、语言、撤稿、版本。
- `field`：`cs|materials|math|social|unknown`；`window_years` 是筛选窗口；`window_source` 为 `field|inferred|from_year|default`。
- `basis`：报告首行的触发依据；由 `--basis` 写入。
- `query_health`：`ok|no_boolean|unexpanded`；非 `ok` 时报告必须提示“样本可能只覆盖领域一角”。
- `history`：默认 `false`，API 窗口等于筛选窗口；`true` 才回溯 5 年供 Y1 审计，并记录 `y1_rate`。
- `genre_warning`：标题疑似 Perspective/Preview/评论，或 ≤3 页且标题含问号；只警告，不自动排除。
- `search_mode`：`title_abstract_keywords|exact`；`exact_fallback=true` 表示 exact 遇 400 后退回默认层。
- `cost_credits` 是本轮所有 OpenAlex 请求的累计 credits；`credits_remaining` 取最后一次响应头。
- `api_key_used` 只记布尔值，绝不记录 key 本身。

## 3. verify 输出

```json
{
  "doi": "10.1234/abc",
  "registrar": "crossref",
  "http_status": 200,
  "status": "pass",
  "reason": "",
  "title_score": 0.93,
  "matched_title": "...",
  "year_delta": 0,
  "retraction_update": "none_found"
}
```

- `status`：`pass|fail|unavailable`。
  - `fail` 附 `reason`（标题不一致/年份偏差/查无此 DOI）。
  - `unavailable` 对应 `D4`（Crossref/DataCite 均无响应）。
- `registrar`：`crossref|datacite`；arXiv `10.48550/...` 通常走 DataCite。
- `retraction_update`：`true|"none_found"|"unknown"`；Crossref 成功且 `update-to`/relation 中无撤稿 → `"none_found"`；DataCite 或查询失败 → `"unknown"`；不要写 `false` 冒充已确认。
- 标题归一化：NFKC、HTML unescape、小写、统一连字符、去标点、压缩空白。
- 相似度：`rapidfuzz.fuzz.ratio` 优先；无 rapidfuzz 时用 `difflib.SequenceMatcher`。有副标题时同时比较冒号前主标题，取最大值；少于 4 个词的标题要求近似完全一致。
- 年份：取 Crossref `published-print`/`published-online`/`issued` 中最早者，与 OpenAlex `publication_year` 比，偏差 ≤1。
- CJK/译名无法可靠比对时 → `D3`，不判 `×`。
- `title_score` 是核验指标，不是相关度；只写核验记录，不进审计表。
- `year_warning`：`|year_delta| == 1` 时为 true；`delta=0` 但卷期/年份不一致的情况无法仅凭这两个字段发现，需人工抽查。

## 3.5 judgments 契约（LLM → audit）

```json
{
  "mode": "semantic",
  "records": [
    {
      "openalex_id": "W1234567890",
      "verdict": "✓",
      "reason_code": "",
      "category": "primary",
      "evidence_quote": "evidence/title 中的逐字片段",
      "one_liner": "≤24 字，非空"
    }
  ]
}
```

- `mode`：只接受 `semantic` 或 `mechanical_smoke`；LLM 交付必须是 `semantic`。
- `mode` 缺失/非法：md 拒绝渲染；json 校验失败；`--allow-unlabeled` 仅测试。
- `verdict`：`✓|×|○`。
- `reason_code`：`✓` 留空；`×` 取 R1/P1/Y1/L1/V1/T1/S1/M1/C1/I1；`○` 取 D1/D2/D3/D4/E1。
- `category`：`primary|review|background|preprint`。
- `evidence_quote`：`✓` 和语义 `×`（T1/S1/M1/C1/I1）必填；必须是 `evidence` 或 `title` 的逐字子串，否则 audit 报错。元数据 `×` 与 `○` 可省略。
- `one_liner`：非空、≤24 字。
- 判定顺序：主题 → 体系/对象 → 手段/方法 → 条件/情境 → 指标/结果；first-fail。

## 4. 错误映射

| 状态 | 处理 |
|---|---|
| 401/403 | key 无效或未激活；停止，给申请/激活链接 |
| 429 + `X-RateLimit-Remaining: 0` | 日预算耗尽；停止，不重试；提示 UTC 零点重置或申请 key |
| 429 + 响应体含 `dailyRemainingUsd`/`creditsRequired`/`Insufficient budget` | 预算不足；停止，不重试（OQL 的 `not_enough_credits` 同） |
| 429 + `X-RateLimit-Remaining > 0` | 突发限流；退避 1/2/4 秒，最多 2 次 |
| 400 | 检索式非法；回显 `search`/`filter`，不重试 |
| 5xx/超时 | 重试 2 次指数退避；仍失败 → `检索失败：{status}` |
| 0 命中 | 输出检索式 + 2 条放宽建议；不编造 |

## 5. 禁止回传

完整 abstract、references、concepts、Crossref 原始 message、OpenAlex 原始响应、API key。

`evidence` 是唯一允许回传的正文文本，且必须是逐字片段；寻迹/循迹 ≤600 字，溯迹 ≤1200 字。
