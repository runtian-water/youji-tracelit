import contextlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import main  # noqa: E402


class TraceLitCoreTests(unittest.TestCase):
    def test_normalize_doi(self):
        self.assertEqual(main.normalize_doi("https://doi.org/10.1038/NATURE12373"), "10.1038/nature12373")
        self.assertEqual(main.normalize_doi("doi:10.1/x"), "10.1/x")
        self.assertEqual(main.normalize_doi(None), "")

    def test_sanitize_text(self):
        self.assertEqual(main.sanitize_text("A\x00B\x07C\nD"), "ABC\nD")
        self.assertEqual(main.sanitize_text(None), "")

    def test_normalize_title(self):
        a = main.normalize_title("Nanometre-scale thermometry in a living cell")
        b = main.normalize_title("Nanometre-scale  thermometry in a living cell")
        self.assertEqual(a, b)

    def test_reconstruct_abstract(self):
        inv = {"We": [0], "study": [1], "perovskite": [2]}
        self.assertEqual(main.reconstruct_abstract(inv), "We study perovskite")
        self.assertEqual(main.reconstruct_abstract(None), "")

    def test_parse_work(self):
        work = {
            "id": "https://openalex.org/W1",
            "title": "A title",
            "doi": "https://doi.org/10.1/x",
            "publication_year": 2024,
            "type": "article",
            "language": "en",
            "authorships": [{"author": {"display_name": "A B"}}],
            "primary_location": {"source": {"display_name": "J"}},
            "biblio": {"volume": "1"},
            "cited_by_count": 3,
            "is_retracted": None,
            "abstract_inverted_index": {"We": [0], "test": [1]},
        }
        r = main.parse_work(work)
        self.assertEqual(r["openalex_id"], "W1")
        self.assertEqual(r["doi"], "10.1/x")
        self.assertEqual(r["retraction_status"], "unknown")
        self.assertEqual(r["_abstract"], "We test")
        self.assertEqual(r["category"], "primary")
        self.assertEqual(r["source"], "J")
        self.assertEqual(r["authors"], ["A B"])
        self.assertEqual(r["author_count"], 1)
        self.assertEqual(r["biblio"], {"volume": "1"})

    def test_dedup_and_version_pair(self):
        records = [
            {
                "openalex_id": "W1", "title": "Same Paper", "doi": "10.1/x",
                "year": 2024, "type": "preprint", "category": "preprint",
                "_norm_title": "same paper", "_norm_first_author": "a",
                "version_duplicate": False,
            },
            {
                "openalex_id": "W2", "title": "Same Paper", "doi": "10.1/y",
                "year": 2024, "type": "article", "category": "primary",
                "_norm_title": "same paper", "_norm_first_author": "a",
                "version_duplicate": False,
            },
        ]
        out = main.dedup_records(records)
        self.assertEqual(len(out), 2)
        preprint = [r for r in out if r["type"] == "preprint"][0]
        self.assertTrue(preprint["version_duplicate"])

    def test_checks_null_semantics(self):
        r = {
            "year": 2020, "type": None, "language": None,
            "retraction_status": "unknown", "version_duplicate": False,
        }
        main.apply_checks(r, 2021, 2026, "en")
        self.assertFalse(r["checks"]["year_ok"])
        self.assertIsNone(r["checks"]["type_ok"])
        self.assertIsNone(r["checks"]["language_ok"])
        self.assertIsNone(r["checks"]["retracted_ok"])
        self.assertTrue(r["checks"]["version_ok"])

    def test_genre_warning(self):
        self.assertTrue(main.is_genre_warning({"title": "Perspective: A view"}))
        self.assertTrue(main.is_genre_warning({
            "title": "Is this strategy good?",
            "biblio": {"first_page": "2444", "last_page": "2446"},
        }))
        self.assertFalse(main.is_genre_warning({"title": "A normal research article"}))

    def test_year_delta_warning(self):
        payload = {
            "message": {
                "title": ["Test title"],
                "published-print": {"date-parts": [[2019, 1, 1]]},
            }
        }
        with patch.object(main, "http_get", return_value=(200, {}, json.dumps(payload))):
            v = main.verify_doi("10.1/x", {"title": "Test title", "year": 2020})
        self.assertEqual(v["status"], "pass")
        self.assertTrue(v["year_warning"])

    def test_single_page_fold(self):
        rec = {
            "authors": ["Smith J"], "author_count": 1, "title": "A title",
            "type": "article", "source": "J", "year": 2020,
            "biblio": {"volume": "1", "first_page": "775", "last_page": "775"},
            "doi": "10.1/a", "openalex_id": "W1",
        }
        entry = main.render_gbt_entry(rec, "1")
        self.assertIn(": 775.", entry)
        self.assertNotIn("775-775", entry)

    def test_cover_suffix_dedup(self):
        base = {
            "publication_year": 2021, "type": "article", "language": "en",
            "authorships": [{"author": {"display_name": "A B"}}],
            "primary_location": {"source": {"display_name": "J"}},
            "biblio": {}, "cited_by_count": 0, "is_retracted": False,
        }
        w1 = dict(base, id="https://openalex.org/W1", title="Paper Title",
                  doi="https://doi.org/10.1/a")
        w2 = dict(base, id="https://openalex.org/W2",
                  title="Paper Title (Adv. Energy Mater. 40/2021)",
                  doi="https://doi.org/10.1/b")
        records = [main.parse_work(w1), main.parse_work(w2)]
        out = main.dedup_records(records)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["openalex_id"], "W1")

    def test_query_health(self):
        self.assertEqual(main.query_health("perovskite interface passivation"), "no_boolean")
        self.assertEqual(main.query_health("perovskite AND passivation"), "ok")
        self.assertEqual(main.query_health('"perovskite interface"'), "ok")
        self.assertEqual(main.query_health("perovskite"), "unexpanded")
        detail = main.query_health_detail("perovskite AND passivation")
        self.assertTrue(detail["has_boolean"])
        self.assertEqual(detail["concepts"], 2)

    def test_empty_one_liner_is_error(self):
        data = {"meta": {"screened": 1}, "records": [{
            "openalex_id": "W1", "title": "A", "year": 2020, "type": "article",
            "category": "primary", "doi": "10.1/a", "verification": {"status": "pass"},
        }]}
        judgments = {"mode": "semantic", "records": [{
            "openalex_id": "W1", "title": "A", "verdict": "✓",
            "reason_code": "", "category": "primary", "evidence_quote": "A", "one_liner": "",
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "in.json"
            jud = Path(tmp) / "j.json"
            inp.write_text(json.dumps(data), encoding="utf-8")
            jud.write_text(json.dumps(judgments), encoding="utf-8")
            args = Namespace(input=str(inp), judgments=str(jud),
                             out=None, format="json", template=False,
                             strict=False, allow_smoke=False)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main.audit_cmd(args)
        self.assertIn("一句话为空", out.getvalue())

    def test_long_one_liner_is_error(self):
        data = {"meta": {"screened": 1}, "records": [{
            "openalex_id": "W1", "title": "A", "year": 2020, "type": "article",
            "category": "primary", "doi": "10.1/a", "verification": {"status": "pass"},
        }]}
        judgments = {"mode": "semantic", "records": [{
            "openalex_id": "W1", "title": "A", "verdict": "✓",
            "reason_code": "", "category": "primary", "evidence_quote": "A", "one_liner": "x" * 25,
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "in.json"
            jud = Path(tmp) / "j.json"
            inp.write_text(json.dumps(data), encoding="utf-8")
            jud.write_text(json.dumps(judgments), encoding="utf-8")
            args = Namespace(input=str(inp), judgments=str(jud),
                             out=None, format="json", template=False,
                             strict=False, allow_smoke=False, allow_unlabeled=False)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                main.audit_cmd(args)
        self.assertIn("超过 24 字", out.getvalue())

    def test_smoke_report_requires_flag(self):
        data = {"meta": {"screened": 1}, "records": [{
            "openalex_id": "W1", "title": "A", "year": 2020, "type": "article",
            "category": "primary", "doi": "10.1/a", "verification": {"status": "pass"},
        }]}
        judgments = {"mode": "mechanical_smoke", "records": [{
            "openalex_id": "W1", "title": "A", "verdict": "✓",
            "reason_code": "", "category": "primary", "one_liner": "[机械冒烟]",
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "in.json"
            jud = Path(tmp) / "j.json"
            inp.write_text(json.dumps(data), encoding="utf-8")
            jud.write_text(json.dumps(judgments), encoding="utf-8")
            args = Namespace(input=str(inp), judgments=str(jud),
                             out=None, format="md", template=False,
                             strict=False, allow_smoke=False)
            with self.assertRaises(main.TraceLitError):
                main.audit_cmd(args)

    def _render_fixture(self, fixture_name, record_count):
        fixture = Path(__file__).resolve().parent / "fixtures" / fixture_name
        data = json.loads(fixture.read_text(encoding="utf-8"))
        judgments = {
            "mode": "semantic",
            "records": [
                {
                    "openalex_id": r.get("openalex_id"),
                    "title": r.get("title"),
                    "verdict": "✓" if (r.get("category") in ("review", "background", "preprint")
                                       or (r.get("verification") or {}).get("status") == "pass") else "○",
                    "reason_code": "" if (r.get("category") in ("review", "background", "preprint")
                                          or (r.get("verification") or {}).get("status") == "pass") else "D1",
                    "category": r.get("category", "primary"),
                    "evidence_quote": (r.get("evidence") or r.get("title") or "")[:160],
                    "one_liner": "一致",
                }
                for r in data.get("records", [])[:record_count]
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            jud = Path(tmp) / "j.json"
            jud.write_text(json.dumps(judgments), encoding="utf-8")
            args = Namespace(
                input=str(fixture), judgments=str(jud), out=None,
                format="md", template=False, strict=False,
                allow_smoke=False, allow_unlabeled=False, allow_errors=False,
                basis=None,
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                rc = main.audit_cmd(args)
        self.assertEqual(rc, 0)
        return out.getvalue()

    def test_thin_meta_fixture_has_no_empty_placeholders(self):
        text = self._render_fixture("one.verified.json", 1)
        self.assertNotIn("None", text)
        self.assertNotIn("window y", text)
        self.assertNotIn("（boolean=None", text)
        self.assertNotIn("sort  |", text)
        self.assertNotIn("elapsed=ms", text)
        self.assertNotIn("于  执行", text)
        self.assertIn("已核验 ≠ 内容优质", text)
        self.assertIn("专利与标准", text)
        self.assertIn("发表偏倚", text)

    def test_chinese_coverage_banner(self):
        self.assertIn("CNKI", main.chinese_coverage_note({"language_mode": "en|zh"}))
        self.assertIsNone(main.chinese_coverage_note({"language_mode": "en"}))
        fixture = Path(__file__).resolve().parent / "fixtures" / "one.verified.json"
        data = json.loads(fixture.read_text(encoding="utf-8"))
        data["meta"]["language_mode"] = "en|zh"
        record = data["records"][0]
        judgments = {"mode": "semantic", "records": [{
            "openalex_id": record["openalex_id"], "title": record["title"],
            "verdict": "✓", "reason_code": "", "category": "primary",
            "evidence_quote": record["title"], "one_liner": "一致",
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "in.json"
            jud = Path(tmp) / "j.json"
            inp.write_text(json.dumps(data), encoding="utf-8")
            jud.write_text(json.dumps(judgments), encoding="utf-8")
            args = Namespace(input=str(inp), judgments=str(jud), out=None,
                             format="md", template=False, strict=False,
                             allow_smoke=False, allow_unlabeled=False,
                             allow_errors=False, basis=None)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                main.audit_cmd(args)
        self.assertIn("CNKI", out.getvalue())
        self.assertIn("万方", out.getvalue())

    def test_real_meta_fixture_has_no_empty_placeholders(self):
        text = self._render_fixture("real_meta.verified.json", 2)
        self.assertNotIn("None", text)
        self.assertNotIn("window y", text)
        self.assertNotIn("sort  |", text)
        self.assertNotIn("elapsed=ms", text)
        self.assertIn("per_page 100", text)
        self.assertIn("background_filter:", text)

    def test_evidence_quote_required_and_checked(self):
        data = {"meta": {"screened": 1}, "records": [{
            "openalex_id": "W1", "title": "A title", "year": 2020,
            "type": "article", "category": "primary", "doi": "10.1/a",
            "evidence": "The sample includes undergraduate students.",
            "verification": {"status": "pass"},
        }]}
        base = {
            "openalex_id": "W1", "title": "A title", "verdict": "✓",
            "reason_code": "", "category": "primary", "one_liner": "一致",
        }
        cases = [
            ({**base}, "缺少 evidence_quote"),
            ({**base, "evidence_quote": "not present"}, "不在 evidence/title"),
            ({**base, "evidence_quote": "The sample includes undergraduate students."}, None),
        ]
        for record, expected in cases:
            judgments = {"mode": "semantic", "records": [record]}
            with tempfile.TemporaryDirectory() as tmp:
                inp = Path(tmp) / "in.json"
                jud = Path(tmp) / "j.json"
                inp.write_text(json.dumps(data), encoding="utf-8")
                jud.write_text(json.dumps(judgments), encoding="utf-8")
                args = Namespace(input=str(inp), judgments=str(jud), out=None,
                                 format="json", template=False, strict=False,
                                 allow_smoke=False, allow_unlabeled=False,
                                 allow_errors=False, basis=None)
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    main.audit_cmd(args)
            if expected:
                self.assertIn(expected, out.getvalue())
            else:
                self.assertNotIn("evidence_quote", out.getvalue())

    def test_mode_required_and_whitelist(self):
        data = {"meta": {"screened": 1}, "records": [{
            "openalex_id": "W1", "title": "A title", "year": 2020,
            "type": "article", "category": "primary", "doi": "10.1/a",
            "verification": {"status": "pass"},
        }]}
        record = {
            "openalex_id": "W1", "title": "A title", "verdict": "✓",
            "reason_code": "", "category": "primary",
            "evidence_quote": "A title", "one_liner": "一致",
        }
        for mode in (None, "Semantic"):
            payload = {"records": [record]} if mode is None else {"mode": mode, "records": [record]}
            with tempfile.TemporaryDirectory() as tmp:
                inp = Path(tmp) / "in.json"
                jud = Path(tmp) / "j.json"
                inp.write_text(json.dumps(data), encoding="utf-8")
                jud.write_text(json.dumps(payload), encoding="utf-8")
                args = Namespace(input=str(inp), judgments=str(jud),
                                 out=None, format="md", template=False,
                                 strict=False, allow_smoke=False, allow_unlabeled=False)
                with self.assertRaises(main.TraceLitError):
                    main.audit_cmd(args)

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "in.json"
            jud = Path(tmp) / "j.json"
            inp.write_text(json.dumps(data), encoding="utf-8")
            jud.write_text(json.dumps({"mode": "semantic", "records": [record]}), encoding="utf-8")
            args = Namespace(input=str(inp), judgments=str(jud),
                             out=None, format="md", template=False,
                             strict=False, allow_smoke=False, allow_unlabeled=False,
                             basis=None)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = main.audit_cmd(args)
        self.assertEqual(rc, 0)

    def test_legend_and_header(self):
        judgments = [{"reason_code": "Y1"}, {"reason_code": "D1"}]
        legend = main.render_legend(judgments)
        self.assertIn("Y1", legend)
        self.assertIn("年份越界", legend)
        self.assertIn("D1", legend)
        header = main.render_header({"tier": "循迹", "field": "materials"})
        self.assertIn("档位：循迹", header)
        self.assertIn("依据：默认档位", header)
        self.assertIn("缺失模式", main.render_tail({"tier": "溯迹", "gaps": [{"facet": "x"}]}))
        self.assertNotIn("缺失模式", main.render_tail({"tier": "溯迹", "gaps": []}))
        self.assertIn("已核验", main.render_tail({"tier": "循迹"}))

    def test_classify_429(self):
        with self.assertRaises(main.BudgetError):
            main.classify_429({"X-RateLimit-Remaining": "0"}, "")
        with self.assertRaises(main.BudgetError):
            main.classify_429({"X-RateLimit-Remaining": "10"}, '{"dailyRemainingUsd":0}')
        with self.assertRaises(main.BudgetError):
            main.classify_429({"X-RateLimit-Remaining": "10", "Retry-After": "300"}, "")
        with self.assertRaises(main.RateLimitError):
            main.classify_429({"X-RateLimit-Remaining": "10"}, "rate limit exceeded")

    def test_retraction_update_states(self):
        self.assertIs(main.has_retraction_update({"update-to": [{"type": "retraction"}]}), True)
        self.assertEqual(main.has_retraction_update({}), "none_found")

    def test_verify_doi_crossref_pass_and_mismatches(self):
        payload = {
            "message": {
                "title": ["Test title"],
                "published-print": {"date-parts": [[2020, 1, 1]]},
                "update-to": [],
                "relation": {},
            }
        }
        with patch.object(main, "http_get", return_value=(200, {}, json.dumps(payload))):
            v = main.verify_doi("10.1/x", {"title": "Test title", "year": 2020})
        self.assertEqual(v["status"], "pass")
        self.assertEqual(v["registrar"], "crossref")
        self.assertEqual(v["retraction_update"], "none_found")
        self.assertEqual(v["year_delta"], 0)

        bad_title = {"message": {"title": ["Different title"], "published-print": {"date-parts": [[2020, 1, 1]]}}}
        with patch.object(main, "http_get", return_value=(200, {}, json.dumps(bad_title))):
            v = main.verify_doi("10.1/x", {"title": "Test title", "year": 2020})
        self.assertEqual(v["status"], "fail")
        self.assertEqual(v["reason"], "title_mismatch")

        bad_year = {"message": {"title": ["Test title"], "published-print": {"date-parts": [[2010, 1, 1]]}}}
        with patch.object(main, "http_get", return_value=(200, {}, json.dumps(bad_year))):
            v = main.verify_doi("10.1/x", {"title": "Test title", "year": 2020})
        self.assertEqual(v["status"], "fail")
        self.assertEqual(v["reason"], "year_mismatch")

    def test_verify_doi_datacite_fallback(self):
        payload = {
            "data": {
                "attributes": {
                    "titles": [{"title": "Test title"}],
                    "publicationYear": 2020,
                }
            }
        }
        with patch.object(main, "http_get", side_effect=[(404, {}, ""), (200, {}, json.dumps(payload))]):
            v = main.verify_doi("10.1/x", {"title": "Test title", "year": 2020})
        self.assertEqual(v["registrar"], "datacite")
        self.assertEqual(v["status"], "pass")
        self.assertEqual(v["retraction_update"], "unknown")

    def test_verify_doi_unavailable(self):
        with patch.object(main, "http_get", return_value=(0, {}, "timeout")):
            v = main.verify_doi("10.1/x", {"title": "Test title", "year": 2020})
        self.assertEqual(v["status"], "unavailable")

    def test_audit_md_keeps_summary_out_of_stdout(self):
        data = {
            "meta": {
                "screened": 1, "cost_credits": 10, "elapsed_ms": 100,
                "api_key_used": True, "search": "test", "filter": "",
                "sort": "relevance_score:desc", "per_page": 100,
                "total_hits": 1, "returned": 1, "dedup_removed": 0,
            },
            "records": [{
                "openalex_id": "W1", "title": "A title", "year": 2020,
                "type": "article", "category": "primary", "doi": "10.1/a",
                "authors": ["Smith J"], "author_count": 1, "source": "J",
                "biblio": {"volume": "1", "first_page": "1", "last_page": "2"},
                "verification": {"status": "pass"},
            }],
        }
        judgments = {"mode": "semantic", "records": [{
            "openalex_id": "W1", "title": "A title", "verdict": "✓",
            "reason_code": "", "category": "primary",
            "evidence_quote": "A title", "one_liner": "一致",
        }]}
        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "in.json"
            jud = Path(tmp) / "judgments.json"
            inp.write_text(json.dumps(data), encoding="utf-8")
            jud.write_text(json.dumps(judgments), encoding="utf-8")
            args = Namespace(
                input=str(inp), judgments=str(jud), out=None,
                format="md", template=False, strict=False,
            )
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = main.audit_cmd(args)
        self.assertEqual(rc, 0)
        stdout, stderr = out.getvalue(), err.getvalue()
        self.assertNotIn('"ok"', stdout)
        self.assertIn('"ok"', stderr)
        self.assertIn("### 参考文献", stdout)
        self.assertIn("credits=10", stdout)
        self.assertIn("elapsed=100ms", stdout)

    def test_background_and_foundational_passes(self):
        def work(oid, title, year, doi, typ="article"):
            return {
                "id": f"https://openalex.org/{oid}", "title": title,
                "doi": f"https://doi.org/{doi}", "publication_year": year,
                "type": typ, "language": "en",
                "authorships": [{"author": {"display_name": "A"}}],
                "primary_location": {"source": {"display_name": "J"}},
                "biblio": {}, "cited_by_count": 10, "is_retracted": False,
                "abstract_inverted_index": {"We": [0], "study": [1], "perovskite": [2]},
            }
        primary = work("W1", "Primary perovskite study", 2024, "10.1/a")
        bg = work("W2", "Review of perovskite passivation", 2015, "10.1/bg", "review")
        fg = work("W3", "Foundational perovskite work", 2010, "10.1/fg")
        args = Namespace(
            query="perovskite", search="perovskite AND passivation",
            filter=None, discipline="stem", language="en",
            from_year=2021, to_year=2026, per_page=100, tier="循迹",
            out=None, dry_run=False, api_key="test", pretty=False,
            field="materials", background=True, foundational=True,
            history=False, basis="", exact=False,
        )
        headers = {"X-RateLimit-Credits-Used": "10", "X-RateLimit-Remaining": "9990"}
        with tempfile.TemporaryDirectory() as tmp:
            args.out = str(Path(tmp) / "search.json")
            with patch.object(main, "get_key", return_value="test"):
                with patch.object(main, "openalex_get", return_value=({"meta": {"count": 1}, "results": [primary]}, headers, "u")):
                    with patch.object(main, "supplemental_search", side_effect=[
                        ({"meta": {"count": 1}, "results": [bg]}, headers),
                        ({"meta": {"count": 1}, "results": [fg]}, headers),
                    ]):
                        with contextlib.redirect_stdout(io.StringIO()):
                            rc = main.search_cmd(args)
            self.assertEqual(rc, 0)
            data = json.loads(Path(args.out).read_text(encoding="utf-8"))
        self.assertEqual(data["meta"]["screened"], 3)
        self.assertEqual(data["meta"]["background_count"], 1)
        self.assertEqual(data["meta"]["foundational_count"], 1)
        self.assertEqual(data["meta"]["cost_credits"], 30)
        cats = [r["category"] for r in data["records"]]
        self.assertIn("background", cats)
        self.assertTrue(any(r.get("foundational") for r in data["records"]))

    def test_conference_types(self):
        conf = {
            "year": 2020, "type": "conference-paper", "language": "en",
            "retraction_status": "not_retracted", "version_duplicate": False,
        }
        main.apply_checks(conf, 2016, 2026, "en")
        self.assertTrue(conf["checks"]["type_ok"])
        abstract = {
            "year": 2020, "type": "conference-abstract", "language": "en",
            "retraction_status": "not_retracted", "version_duplicate": False,
        }
        main.apply_checks(abstract, 2016, 2026, "en")
        self.assertFalse(abstract["checks"]["type_ok"])

    def test_title_similarity(self):
        a = "Nanometre-scale thermometry in a living cell"
        self.assertAlmostEqual(main.title_similarity(a, a), 1.0, places=3)
        self.assertLess(main.title_similarity(a, "A completely different title"), 0.6)

    def test_select_evidence(self):
        abstract = "We study perovskite films. The efficiency is 25%. The sample is small."
        ev, field = main.select_evidence(abstract, ["perovskite", "efficiency"], ["efficiency"], 200)
        self.assertEqual(field, "abstract")
        self.assertIn("perovskite", ev)
        self.assertIn("efficiency", ev)

    def test_field_windows_and_inference(self):
        self.assertEqual(main.FIELD_WINDOWS["cs"], 3)
        self.assertEqual(main.FIELD_WINDOWS["materials"], 5)
        self.assertEqual(main.FIELD_WINDOWS["math"], 10)
        self.assertEqual(main.infer_field("perovskite interface passivation"), "materials")
        self.assertEqual(main.infer_field("deep learning for image classification"), "cs")
        self.assertEqual(main.infer_field("quantum mechanics proof"), "math")
        self.assertEqual(main.infer_field("undergraduate education policy"), "social")
        self.assertEqual(main.infer_field("something obscure"), "unknown")

    def test_format_author_en(self):
        self.assertEqual(main.format_author_en("G. Kucsko"), "KUCSKO G")
        self.assertEqual(main.format_author_en("P. C. Maurer"), "MAURER P C")
        self.assertEqual(main.format_author_en("N. Y. Yao"), "YAO N Y")
        self.assertEqual(main.format_author_en("John Smith"), "SMITH J")
        self.assertEqual(main.format_author_en("Smith, John"), "SMITH J")

    def test_format_authors_chinese(self):
        rec = {
            "authors": ["张三", "李四", "王五", "赵六"],
            "author_count": 4,
            "title": "中文题目",
        }
        self.assertEqual(main.format_authors(rec), "张三, 李四, 王五, 等")

    def test_render_gbt_entry(self):
        rec = {
            "authors": ["G. Kucsko", "P. C. Maurer", "N. Y. Yao"],
            "author_count": 8,
            "title": "Nanometre-scale thermometry in a living cell",
            "type": "article",
            "source": "Nature",
            "year": 2013,
            "biblio": {"volume": "500", "issue": "7460", "first_page": "54", "last_page": "58"},
            "doi": "10.1038/nature12373",
            "openalex_id": "W1",
        }
        entry = main.render_gbt_entry(rec, "1")
        self.assertIn("KUCSKO G, MAURER P C, YAO N Y, et al.", entry)
        self.assertIn("[J]", entry)
        self.assertIn("Nature, 2013, 500(7460): 54-58", entry)
        self.assertIn("DOI: 10.1038/nature12373.", entry)

    def test_suiji_render_and_default_facets(self):
        self.assertEqual(len(main.default_facets("stem", "x")), 3)
        self.assertEqual(len(main.default_facets("social", "x")), 3)
        self.assertEqual(main.render_suiji({"tier": "循迹"}), "")
        meta = {
            "tier": "溯迹", "screen_year_window": "2021-01-01/2026-12-31",
            "language_mode": "en", "total_hits": 100,
            "facet_queries": [{
                "label": "技术路线", "hits": 10,
                "representatives": [{"title": "A review", "year": 2020}],
            }],
            "top5": [{
                "rank": 1, "title": "A paper", "year": 2021,
                "doi": "10.1/x", "match_hits": 3,
            }],
            "gaps": [{
                "facet": "技术路线", "hits": 10, "share": 0.1,
                "representatives": [{"title": "A review", "year": 2020}],
                "hypothesis": "H", "verify": "V",
            }],
        }
        text = main.render_suiji(meta)
        self.assertIn("### 簇计数表", text)
        self.assertIn("### 近邻工作 Top5", text)
        self.assertIn("### 缺口候选（不是结论）", text)
        self.assertIn("不是 OpenAlex 全库", text)

    def test_no_gap_when_coverage_high(self):
        meta = {
            "tier": "溯迹", "total_hits": 1000,
            "screen_year_window": "2021-01-01/2026-12-31", "language_mode": "en",
            "facets": [{
                "label": "技术路线", "hits": 900,
                "representatives": [{"title": "A", "year": 2023}],
            }],
            "top5": [], "gaps": [],
        }
        text = main.render_suiji(meta)
        self.assertIn("未发现可论证缺口", text)
        self.assertIn("hits≥50 且 share≥5%", text)
        self.assertNotIn("缺失模式", main.render_tail(meta))

    def test_docx_writer(self):
        md = (
            "# Title\n\n## Section\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "```\nsearch: test\n```\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report.docx"
            main.markdown_to_docx(md, str(out))
            with zipfile.ZipFile(out) as zf:
                document = zf.read("word/document.xml").decode("utf-8")
        self.assertIn("Title", document)
        self.assertIn("<w:tbl>", document)
        self.assertIn("search: test", document)

    def test_background_category(self):
        rec = {
            "openalex_id": "W1", "title": "A background review", "type": "article",
            "category": "background", "year": 2015, "authors": ["Smith J"],
            "author_count": 1, "source": "J", "biblio": {}, "doi": "10.1/a",
        }
        data = {"records": [rec]}
        judgments = [{"openalex_id": "W1", "verdict": "✓", "category": "background"}]
        md = main.render_gbt7714(data, judgments)
        self.assertIn("### 背景文献", md)
        self.assertEqual(main.type_label(rec), "背景[综述]")
        table = main.render_audit_table(data, judgments)
        self.assertIn("| B1 |", table)
        self.assertIn("| ✓ |", table)

    def test_render_gbt7714_sections(self):
        primary = {
            "openalex_id": "W1", "title": "A primary study", "type": "article",
            "category": "primary", "authors": ["Smith J"], "author_count": 1,
            "source": "J", "year": 2020, "biblio": {"volume": "1", "first_page": "1", "last_page": "2"},
            "doi": "10.1/a",
        }
        review = {
            "openalex_id": "W2", "title": "A review", "type": "review",
            "category": "review", "authors": ["Lee K"], "author_count": 1,
            "source": "R", "year": 2021, "biblio": {}, "doi": "10.1/b",
        }
        preprint = {
            "openalex_id": "W3", "title": "A preprint", "type": "preprint",
            "category": "preprint", "authors": ["Kim S"], "author_count": 1,
            "source": "arXiv", "year": 2024, "biblio": {}, "doi": "10.1/c",
        }
        data = {"records": [primary, review, preprint]}
        judgments = [
            {"openalex_id": "W1", "verdict": "✓", "category": "primary"},
            {"openalex_id": "W2", "verdict": "✓", "category": "review"},
            {"openalex_id": "W3", "verdict": "✓", "category": "preprint"},
        ]
        md = main.render_gbt7714(data, judgments)
        self.assertIn("### 参考文献", md)
        self.assertIn("[1]", md)
        self.assertIn("### 背景文献", md)
        self.assertIn("[B1]", md)
        self.assertIn("### 预印本", md)
        self.assertIn("[P1]", md)

    def test_render_audit_table_columns(self):
        rec = {
            "openalex_id": "W1", "title": "A title", "year": 2020,
            "type": "article", "category": "primary", "doi": "10.1/a",
        }
        data = {"records": [rec]}
        judgments = [{"openalex_id": "W1", "verdict": "✓", "reason_code": "", "one_liner": "一致"}]
        table = main.render_audit_table(data, judgments)
        header = table.splitlines()[0]
        self.assertEqual(header.count("|"), 9)  # 8 columns + outer pipes
        self.assertIn("2020", table)
        self.assertIn("10.1/a", table)
        self.assertIn("期刊论文", table)

    def test_search_cmd_with_fake_openalex(self):
        abstract = {"We": [0], "study": [1], "perovskite": [2], "passivation": [3],
                    "efficiency": [4], "is": [5], "25%": [6]}
        work_preprint = {
            "id": "https://openalex.org/W1", "title": "Perovskite passivation",
            "doi": None, "publication_year": 2024, "type": "preprint",
            "language": "en", "authorships": [{"author": {"display_name": "A"}}],
            "primary_location": {"source": {"display_name": "arXiv"}},
            "biblio": {}, "cited_by_count": 1, "is_retracted": False,
            "abstract_inverted_index": abstract,
        }
        work_article = {
            "id": "https://openalex.org/W2", "title": "Perovskite passivation",
            "doi": "https://doi.org/10.1/x", "publication_year": 2024,
            "type": "article", "language": "en",
            "authorships": [{"author": {"display_name": "A"}}],
            "primary_location": {"source": {"display_name": "J"}},
            "biblio": {}, "cited_by_count": 2, "is_retracted": False,
            "abstract_inverted_index": abstract,
        }
        fake = {"meta": {"count": 2}, "results": [work_preprint, work_article]}
        headers = {"X-RateLimit-Credits-Used": "10", "X-RateLimit-Remaining": "9990"}
        args = Namespace(
            query="perovskite passivation", search=None, filter=None,
            discipline="stem", language="en", from_year=2021, to_year=2026,
            per_page=100, tier="寻迹", out=None, dry_run=False,
            api_key=None, pretty=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            args.out = str(Path(tmp) / "search.json")
            with patch.object(main, "get_key", return_value=""):
                with patch.object(main, "openalex_get", return_value=(fake, headers, "u")):
                    with contextlib.redirect_stdout(io.StringIO()):
                        rc = main.search_cmd(args)
            self.assertEqual(rc, 0)
            data = json.loads(Path(args.out).read_text(encoding="utf-8"))
            self.assertEqual(data["meta"]["screened"], 2)
            self.assertEqual(data["meta"]["dedup_removed"], 0)
            self.assertEqual(data["meta"]["cost_credits"], 10)
            self.assertFalse(data["meta"]["api_key_used"])
            self.assertEqual(data["meta"]["field"], "materials")
            self.assertEqual(data["meta"]["window_years"], 5)
            self.assertFalse(data["meta"]["history"])
            self.assertEqual(data["meta"]["y1_rate"], 0)
            pre = [r for r in data["records"] if r["type"] == "preprint"][0]
            self.assertTrue(pre["version_duplicate"])
            self.assertIn("perovskite", pre["evidence"].lower())


if __name__ == "__main__":
    unittest.main()
