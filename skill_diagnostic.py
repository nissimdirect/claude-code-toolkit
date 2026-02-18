#!/usr/bin/env python3
"""Skill Diagnostic Toolchain — Measures advisor skill health.

Diagnoses hedging, blandness, and inconsistency in advisor skills.
Uses peer-reviewed methods: SycEval (conviction), RAGAS (faithfulness),
Self-BLEU (diversity), SPLIT-RAG (source mapping).

Usage:
    # Zero-cost modes (no LLM calls)
    python3 skill_diagnostic.py --skill cto --map          # Source mapping only
    python3 skill_diagnostic.py --skill cto --dry-run      # Self-BLEU on existing corpus

    # LLM-using modes
    python3 skill_diagnostic.py --skill cto --generate     # Generate response corpus
    python3 skill_diagnostic.py --skill cto --analyze      # Faithfulness + diversity + map
    python3 skill_diagnostic.py --skill cto --rebuttal     # Conviction under pressure
    python3 skill_diagnostic.py --skill cto --full         # All of the above + report
    python3 skill_diagnostic.py --skill cto --post-scrape  # Faithfulness only (after KB changes)

    # Multi-skill modes
    python3 skill_diagnostic.py --all --health             # Lightweight scan all skills

    # Reporting
    python3 skill_diagnostic.py --skill cto --report       # Markdown from existing results
    python3 skill_diagnostic.py --skill cto --diff         # Compare to last baseline

From Python:
    from skill_diagnostic import SkillDiagnostic
    diag = SkillDiagnostic()
    diag.run("cto", mode="map")
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

# ── Project imports ──
sys.path.insert(0, str(Path(__file__).parent))
from persona_test import QUESTIONS  # 10 test questions (single source of truth)

# Lazy import kb_loader to avoid import-time side effects
_kb_loader = None


def _get_kb_loader():
    global _kb_loader
    if _kb_loader is None:
        from kb_loader import KBLoader
        _kb_loader = KBLoader()
    return _kb_loader


# ── Paths ──
LOCKS_DIR = Path.home() / ".claude" / ".locks"
CORPUS_DIR = LOCKS_DIR / "diagnostic-responses"
HISTORY_DIR = LOCKS_DIR / "diagnostic-history"
LATEST_DIR = HISTORY_DIR / "latest"
SKILLS_DIR = Path.home() / ".claude" / "skills"
BUDGET_STATE = Path.home() / ".claude" / ".locks" / ".budget-state.json"

# ── Call limits per mode ──
CALL_LIMITS = {
    "full": 200,
    "post-scrape": 50,
    "health": 500,
    "generate": 50,
    "analyze": 100,
    "rebuttal": 150,
}

# ── Skill list (advisors with KBs worth diagnosing) ──
DIAGNOSABLE_SKILLS = [
    "cto", "art-director", "music-biz", "label", "atrium",
    "lenny", "music-composer", "audio-production", "marketing-hacker",
    "don-norman", "chatprd", "indie-trinity",
]


# ============================================================================
# Component 0: LLM Provider
# ============================================================================

class LLMProvider:
    """Handles LLM API calls via Gemini Flash (fast, free-tier friendly).

    Uses gemini_draft.py for all LLM calls. Falls back to Groq if Gemini fails.
    Budget gate prevents runaway costs.
    """

    def __init__(self, model: str = "gemini", call_limit: int = 200):
        self.model = model
        self.call_limit = call_limit
        self.call_count = 0
        self._draft_fn = None

    def _get_draft_fn(self):
        if self._draft_fn is None:
            from gemini_draft import draft
            self._draft_fn = draft
        return self._draft_fn

    def check_budget(self, threshold: float = 0.7) -> bool:
        """Return True if budget is OK (below threshold)."""
        if not BUDGET_STATE.exists():
            return True
        try:
            state = json.loads(BUDGET_STATE.read_text())
            pct = state.get("budget_pct", 0)
            if isinstance(pct, str):
                pct = float(pct.rstrip("%")) / 100
            return pct < threshold
        except (json.JSONDecodeError, ValueError, KeyError):
            return True

    def call_llm(self, system: str, user: str, max_tokens: int = 1024) -> str | None:
        """Call Gemini Flash with retry and budget gate. Returns text or None."""
        if self.call_count >= self.call_limit:
            return None

        if not self.check_budget():
            print(f"  [BUDGET GATE] Budget >70%, skipping LLM call", file=sys.stderr)
            return None

        draft_fn = self._get_draft_fn()
        retries = [2, 4, 8]

        # Combine system + user into a single prompt for Gemini
        combined_prompt = f"{user}"

        for attempt, delay in enumerate(retries):
            try:
                self.call_count += 1
                result = draft_fn(combined_prompt, context=system, temperature=0.4)
                if result and result.strip():
                    return result.strip()
                return None
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    time.sleep(delay)
                    continue
                elif "500" in err_str or "502" in err_str or "503" in err_str:
                    time.sleep(delay)
                    continue
                else:
                    print(f"  [LLM ERROR] {e}", file=sys.stderr)
                    return None

        print(f"  [LLM ERROR] All retries exhausted", file=sys.stderr)
        return None


# ============================================================================
# Component 1: Source Mapper (SPLIT-RAG inspired, zero LLM cost)
# ============================================================================

class SourceMapper:
    """Maps which KB sources are relevant for each test question."""

    def __init__(self):
        self.loader = _get_kb_loader()

    @staticmethod
    def get_source_key(path: str) -> str:
        """Map file path to a human-readable source key."""
        p = Path(path)
        parts = p.parts
        # Walk backwards from the file looking for 'articles' parent
        for i, part in enumerate(parts):
            if part == "articles" and i > 0:
                return parts[i - 1]
        # Fallback: parent directory name
        return p.parent.name

    def build_source_matrix(self, skill: str) -> dict:
        """Build a matrix: {question_index: {source_key: hit_count}}.

        Shows which sources answer which questions, revealing natural clusters.
        """
        matrix = {}
        questions_for_skill = [q for q in QUESTIONS if q["advisor"] == skill]

        # If no questions specifically target this skill, use all questions
        if not questions_for_skill:
            questions_for_skill = QUESTIONS

        for q in questions_for_skill:
            idx = q["index"]
            results = self.loader.search(skill, q["context_query"], max_results=20)
            source_counts: dict[str, int] = {}
            for r in results:
                key = self.get_source_key(r["path"])
                source_counts[key] = source_counts.get(key, 0) + 1
            matrix[idx] = source_counts

        return matrix

    def cluster_sources(self, matrix: dict) -> list[dict]:
        """Suggest persona splits based on source co-occurrence.

        Returns clusters: [{sources: [str], questions: [int], label: str}]
        """
        if not matrix:
            return []

        # Build co-occurrence: which sources appear together across questions
        all_sources = set()
        for q_sources in matrix.values():
            all_sources.update(q_sources.keys())

        if len(all_sources) <= 2:
            return [{"sources": list(all_sources), "questions": list(matrix.keys()),
                      "label": "single-cluster"}]

        # Simple greedy clustering: group sources that answer the same questions
        # For each source, build its question profile
        source_profiles: dict[str, set] = {}
        for q_idx, q_sources in matrix.items():
            for src in q_sources:
                if src not in source_profiles:
                    source_profiles[src] = set()
                source_profiles[src].add(q_idx)

        # Group sources with >50% question overlap (Jaccard similarity)
        clusters: list[dict] = []
        assigned = set()

        for src in sorted(source_profiles, key=lambda s: -len(source_profiles[s])):
            if src in assigned:
                continue
            cluster_sources = [src]
            cluster_questions = set(source_profiles[src])
            assigned.add(src)

            for other in sorted(source_profiles, key=lambda s: -len(source_profiles[s])):
                if other in assigned:
                    continue
                overlap = source_profiles[src] & source_profiles[other]
                union = source_profiles[src] | source_profiles[other]
                jaccard = len(overlap) / len(union) if union else 0
                if jaccard > 0.5:
                    cluster_sources.append(other)
                    cluster_questions.update(source_profiles[other])
                    assigned.add(other)

            clusters.append({
                "sources": cluster_sources,
                "questions": sorted(cluster_questions),
                "label": f"cluster-{len(clusters) + 1}",
            })

        # Pick up any unassigned sources
        for src in all_sources - assigned:
            clusters.append({
                "sources": [src],
                "questions": sorted(source_profiles.get(src, set())),
                "label": f"singleton-{src}",
            })

        return clusters


# ============================================================================
# Component 2: Diversity Measure (Self-BLEU, zero LLM cost)
# ============================================================================

class DiversityMeasure:
    """Compute Self-BLEU between response texts to measure diversity."""

    @staticmethod
    def _ngrams(tokens: list[str], n: int) -> list[tuple]:
        """Extract n-grams from token list."""
        return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]

    @classmethod
    def compute_self_bleu(cls, text_a: str, text_b: str, max_n: int = 4) -> float:
        """Compute Self-BLEU between two texts (0=totally different, 1=identical).

        Uses modified precision for 1-gram through max_n-gram, geometric mean.
        """
        tokens_a = text_a.lower().split()
        tokens_b = text_b.lower().split()

        if not tokens_a or not tokens_b:
            return 0.0

        precisions = []
        for n in range(1, max_n + 1):
            ngrams_a = cls._ngrams(tokens_a, n)
            ngrams_b = cls._ngrams(tokens_b, n)

            if not ngrams_a or not ngrams_b:
                break

            ref_counts = Counter(ngrams_b)
            matches = 0
            for ng in ngrams_a:
                if ref_counts.get(ng, 0) > 0:
                    matches += 1
                    ref_counts[ng] -= 1

            precision = matches / len(ngrams_a) if ngrams_a else 0
            precisions.append(max(precision, 1e-10))  # Avoid log(0)

        if not precisions:
            return 0.0

        # Geometric mean of precisions
        import math
        log_avg = sum(math.log(p) for p in precisions) / len(precisions)
        return math.exp(log_avg)

    @classmethod
    def cross_skill_matrix(cls, responses_by_skill: dict[str, list[str]]) -> dict:
        """Compute Self-BLEU between all skill pairs.

        Input: {skill_name: [response_text_0, response_text_1, ...]}
        Output: {(skill_a, skill_b): avg_self_bleu}
        """
        skills = sorted(responses_by_skill.keys())
        matrix = {}

        for i, skill_a in enumerate(skills):
            for skill_b in skills[i + 1:]:
                texts_a = responses_by_skill[skill_a]
                texts_b = responses_by_skill[skill_b]
                scores = []
                for ta, tb in zip(texts_a, texts_b):
                    if ta and tb:
                        scores.append(cls.compute_self_bleu(ta, tb))
                avg = sum(scores) / len(scores) if scores else 0.0
                matrix[f"{skill_a} vs {skill_b}"] = round(avg, 3)

        return matrix


# ============================================================================
# Component 3: Response Corpus
# ============================================================================

class ResponseCorpus:
    """Generate and manage response corpus for diagnostic analysis."""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    @staticmethod
    def _load_skill_md(skill: str) -> str:
        """Read a skill's SKILL.md content."""
        skill_path = SKILLS_DIR / skill / "SKILL.md"
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8", errors="replace")
        return f"[SKILL.md not found for {skill}]"

    def generate(self, skill: str) -> dict:
        """Generate responses for all 10 questions from a skill's perspective.

        Returns dict with question index as key, response metadata as value.
        Saves each response to disk as JSON.
        """
        skill_md = self._load_skill_md(skill)
        loader = _get_kb_loader()
        corpus = {}

        skill_dir = CORPUS_DIR / skill
        skill_dir.mkdir(parents=True, exist_ok=True)

        for q in QUESTIONS:
            idx = q["index"]
            print(f"  Generating Q{idx}: {q['question'][:60]}...")

            # Get KB context for this question
            kb_context = loader.get_context(
                q.get("advisor", skill),
                q["context_query"],
                max_tokens=3000,
                max_results=10,
            )

            # Build prompt
            system_prompt = f"""You are an expert advisor. Follow these instructions exactly:

{skill_md}

## Knowledge Base Context
{kb_context}

## Response Rules
- Take a clear position. Do not hedge.
- Cite specific sources from the KB context when possible.
- End with a concrete recommendation.
- Keep response under 500 words."""

            response_text = self.llm.call_llm(system_prompt, q["question"])

            if response_text is None:
                corpus[idx] = {"status": "skipped", "question": q["question"]}
                continue

            entry = {
                "status": "ok",
                "question": q["question"],
                "domain": q["domain"],
                "advisor": q.get("advisor", skill),
                "response": response_text,
                "model": self.llm.model,
                "timestamp": datetime.now().isoformat(),
                "kb_context_length": len(kb_context),
            }
            corpus[idx] = entry

            # Save to disk
            out_path = skill_dir / f"q{idx}_response.json"
            out_path.write_text(json.dumps(entry, indent=2), encoding="utf-8")

        return corpus

    @staticmethod
    def load(skill: str) -> dict:
        """Load existing response corpus from disk."""
        skill_dir = CORPUS_DIR / skill
        if not skill_dir.exists():
            return {}

        corpus = {}
        for f in sorted(skill_dir.glob("q*_response.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                # Extract question index from filename
                idx = int(re.search(r"q(\d+)", f.stem).group(1))
                corpus[idx] = data
            except (json.JSONDecodeError, AttributeError, ValueError):
                continue
        return corpus


# ============================================================================
# Component 4: Faithfulness Scorer (RAGAS-inspired)
# ============================================================================

class FaithfulnessScorer:
    """Measures how well a response is grounded in its KB context."""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def extract_claims(self, response: str) -> list[str]:
        """Extract factual claims from a response using LLM."""
        result = self.llm.call_llm(
            system="You extract factual claims from text. Return one claim per line. "
                   "Only include verifiable statements, not opinions or recommendations. "
                   "Return just the claims, no numbering or prefixes.",
            user=f"Extract all factual claims from this text:\n\n{response}",
            max_tokens=512,
        )
        if not result:
            return []
        return [line.strip() for line in result.strip().split("\n") if line.strip()]

    def check_grounding(self, claims: list[str], kb_context: str) -> float:
        """Check what fraction of claims are grounded in KB context."""
        if not claims:
            return 0.0

        claims_text = "\n".join(f"- {c}" for c in claims)
        result = self.llm.call_llm(
            system="You check if claims are supported by a knowledge base context. "
                   "For each claim, respond SUPPORTED or UNSUPPORTED on its own line. "
                   "A claim is SUPPORTED if the context contains evidence for it. "
                   "Return one verdict per line, matching the order of claims.",
            user=f"## Claims\n{claims_text}\n\n## Knowledge Base Context\n{kb_context}",
            max_tokens=256,
        )
        if not result:
            return 0.0

        lines = result.strip().split("\n")
        supported = sum(1 for line in lines if "SUPPORTED" in line.upper()
                        and "UNSUPPORTED" not in line.upper())
        return supported / len(claims)

    def score(self, skill: str, corpus: dict) -> dict:
        """Score faithfulness for all responses in a corpus."""
        loader = _get_kb_loader()
        scores = {}

        for idx, entry in corpus.items():
            if entry.get("status") != "ok":
                continue

            q = QUESTIONS[int(idx)]
            kb_context = loader.get_context(
                q.get("advisor", skill),
                q["context_query"],
                max_tokens=3000,
                max_results=20,
            )

            claims = self.extract_claims(entry["response"])
            if claims:
                grounding = self.check_grounding(claims, kb_context)
            else:
                grounding = 0.0

            scores[int(idx)] = {
                "claims_count": len(claims),
                "grounding": round(grounding, 2),
            }
            print(f"  Q{idx}: {len(claims)} claims, {grounding:.0%} grounded")

        avg = sum(s["grounding"] for s in scores.values()) / len(scores) if scores else 0
        return {"per_question": scores, "avg": round(avg, 2)}


# ============================================================================
# Component 5: Baseline Storage + Diff
# ============================================================================

class BaselineStorage:
    """Store and compare diagnostic results over time."""

    @staticmethod
    def save(skill: str, mode: str, results: dict):
        """Save results with timestamp and copy to latest/."""
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        LATEST_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d")
        entry = {
            "version": 1,
            "skill": skill,
            "mode": mode,
            "timestamp": datetime.now().isoformat(),
            "components": results,
        }

        # Timestamped snapshot
        snapshot_path = HISTORY_DIR / f"{timestamp}_{skill}_{mode}.json"
        snapshot_path.write_text(json.dumps(entry, indent=2), encoding="utf-8")

        # Latest pointer
        latest_path = LATEST_DIR / f"{skill}.json"
        latest_path.write_text(json.dumps(entry, indent=2), encoding="utf-8")

        return snapshot_path

    @staticmethod
    def load_latest(skill: str) -> dict | None:
        """Load most recent results for a skill."""
        latest_path = LATEST_DIR / f"{skill}.json"
        if not latest_path.exists():
            return None
        try:
            return json.loads(latest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def diff(skill: str, current: dict) -> str:
        """Compare current results against latest baseline."""
        previous = BaselineStorage.load_latest(skill)
        if not previous:
            return f"No previous baseline for {skill}. This run becomes the baseline."

        lines = [f"## Diff: {skill}", f"Previous: {previous.get('timestamp', '?')}",
                 f"Current:  {datetime.now().isoformat()}", ""]

        prev_c = previous.get("components", {})
        curr_c = current

        # Compare faithfulness
        if "faithfulness" in prev_c and "faithfulness" in curr_c:
            p_avg = prev_c["faithfulness"].get("avg", 0)
            c_avg = curr_c["faithfulness"].get("avg", 0)
            delta = c_avg - p_avg
            arrow = "IMPROVED" if delta > 0 else "DEGRADED" if delta < 0 else "UNCHANGED"
            lines.append(f"Faithfulness: {p_avg} → {c_avg} ({delta:+.2f}) {arrow}")

        # Compare source mapping clusters
        if "source_mapping" in prev_c and "source_mapping" in curr_c:
            p_clusters = len(prev_c["source_mapping"].get("clusters", []))
            c_clusters = len(curr_c["source_mapping"].get("clusters", []))
            lines.append(f"Source clusters: {p_clusters} → {c_clusters}")

        # Compare diversity
        if "diversity" in prev_c and "diversity" in curr_c:
            lines.append(f"Self-BLEU cross-skill: {prev_c['diversity']} → {curr_c['diversity']}")

        return "\n".join(lines)


# ============================================================================
# Orchestrator
# ============================================================================

class SkillDiagnostic:
    """Main orchestrator for skill diagnostic runs."""

    def __init__(self, model: str = "haiku"):
        self.model = model

    def run(self, skill: str, mode: str, output_path: str | None = None) -> dict:
        """Run diagnostic in specified mode. Returns results dict."""
        results = {}

        if mode == "map":
            results = self._run_map(skill)
        elif mode == "dry-run":
            results = self._run_dry_run(skill)
        elif mode == "generate":
            results = self._run_generate(skill)
        elif mode == "analyze":
            results = self._run_analyze(skill)
        elif mode == "full":
            results = self._run_full(skill)
        elif mode == "post-scrape":
            results = self._run_post_scrape(skill)
        elif mode == "report":
            results = self._run_report(skill)
        elif mode == "diff":
            print(BaselineStorage.diff(skill, results))
            return results
        elif mode == "health":
            results = self._run_health_all()
        elif mode == "directive-audit":
            results = self._run_directive_audit()
        else:
            print(f"Unknown mode: {mode}", file=sys.stderr)
            sys.exit(1)

        # Save baseline
        if mode in ("full", "analyze", "post-scrape"):
            path = BaselineStorage.save(skill, mode, results)
            print(f"\nBaseline saved: {path}")

        # Write markdown report if requested
        if output_path:
            report = self._format_report(skill, mode, results)
            Path(output_path).write_text(report, encoding="utf-8")
            print(f"Report written: {output_path}")

        return results

    def _run_map(self, skill: str) -> dict:
        """Phase 1: Source mapping only (zero cost)."""
        print(f"\n=== Source Map: {skill} ===")
        mapper = SourceMapper()
        matrix = mapper.build_source_matrix(skill)
        clusters = mapper.cluster_sources(matrix)

        # Print matrix
        all_sources = set()
        for q_sources in matrix.values():
            all_sources.update(q_sources.keys())

        print(f"\nSources found: {len(all_sources)}")
        for src in sorted(all_sources):
            total = sum(matrix[q].get(src, 0) for q in matrix)
            print(f"  {src}: {total} hits across {sum(1 for q in matrix if src in matrix[q])} questions")

        print(f"\nSuggested clusters: {len(clusters)}")
        for c in clusters:
            print(f"  {c['label']}: {c['sources']} → Q{c['questions']}")

        return {"source_mapping": {"matrix": matrix, "clusters": clusters,
                                    "source_count": len(all_sources)}}

    def _run_dry_run(self, skill: str) -> dict:
        """Self-BLEU on existing corpus (zero cost)."""
        print(f"\n=== Dry Run: {skill} ===")
        corpus = ResponseCorpus.load(skill)
        if not corpus:
            print(f"No corpus found for {skill}. Run --generate first.")
            return {}

        # Self-BLEU within this skill's responses
        texts = [entry.get("response", "") for entry in corpus.values()
                 if entry.get("status") == "ok"]
        diversity = DiversityMeasure()

        if len(texts) >= 2:
            # Pairwise Self-BLEU within responses
            scores = []
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    scores.append(diversity.compute_self_bleu(texts[i], texts[j]))
            avg_self_bleu = sum(scores) / len(scores) if scores else 0
            print(f"Intra-skill Self-BLEU: {avg_self_bleu:.3f} "
                  f"({'high overlap' if avg_self_bleu > 0.5 else 'diverse'})")
        else:
            avg_self_bleu = 0
            print("Not enough responses for Self-BLEU")

        # Source mapping (also free)
        map_results = self._run_map(skill)

        return {
            "diversity": {"intra_skill_self_bleu": round(avg_self_bleu, 3)},
            **map_results,
        }

    def _run_generate(self, skill: str) -> dict:
        """Phase 2: Generate response corpus."""
        print(f"\n=== Generate Corpus: {skill} ===")
        llm = LLMProvider(model=self.model, call_limit=CALL_LIMITS["generate"])
        corpus_gen = ResponseCorpus(llm)
        corpus = corpus_gen.generate(skill)

        ok_count = sum(1 for e in corpus.values() if e.get("status") == "ok")
        print(f"\nGenerated {ok_count}/{len(QUESTIONS)} responses ({llm.call_count} API calls)")
        return {"corpus": {"generated": ok_count, "total": len(QUESTIONS),
                           "api_calls": llm.call_count}}

    def _run_analyze(self, skill: str) -> dict:
        """Faithfulness + diversity + source mapping."""
        print(f"\n=== Analyze: {skill} ===")
        corpus = ResponseCorpus.load(skill)
        if not corpus:
            print(f"No corpus found. Run --generate first.")
            return {}

        llm = LLMProvider(model=self.model, call_limit=CALL_LIMITS["analyze"])

        # Faithfulness
        print("\n--- Faithfulness ---")
        faithfulness = FaithfulnessScorer(llm)
        faith_results = faithfulness.score(skill, corpus)
        print(f"Average faithfulness: {faith_results['avg']:.0%}")

        # Diversity (free)
        dry_results = self._run_dry_run(skill)

        return {
            "faithfulness": faith_results,
            **dry_results,
        }

    def _run_full(self, skill: str) -> dict:
        """Full diagnostic: generate + analyze + report."""
        print(f"\n{'='*50}")
        print(f"  FULL DIAGNOSTIC: {skill}")
        print(f"{'='*50}")

        # Generate
        gen_results = self._run_generate(skill)

        # Analyze
        analyze_results = self._run_analyze(skill)

        # Merge
        results = {**gen_results, **analyze_results}

        # Print summary
        print(f"\n{'='*50}")
        print(f"  SUMMARY: {skill}")
        print(f"{'='*50}")
        faith_avg = analyze_results.get("faithfulness", {}).get("avg", "N/A")
        diversity = analyze_results.get("diversity", {}).get("intra_skill_self_bleu", "N/A")
        clusters = len(analyze_results.get("source_mapping", {}).get("clusters", []))
        print(f"  Faithfulness:  {faith_avg}")
        print(f"  Self-BLEU:     {diversity}")
        print(f"  Source clusters: {clusters}")

        return results

    def _run_post_scrape(self, skill: str) -> dict:
        """Faithfulness-only check after KB changes."""
        print(f"\n=== Post-Scrape Check: {skill} ===")
        corpus = ResponseCorpus.load(skill)
        if not corpus:
            print(f"No corpus found. Run --generate first.")
            return {}

        llm = LLMProvider(model=self.model, call_limit=CALL_LIMITS["post-scrape"])
        faithfulness = FaithfulnessScorer(llm)
        faith_results = faithfulness.score(skill, corpus)
        print(f"Average faithfulness: {faith_results['avg']:.0%}")

        return {"faithfulness": faith_results}

    def _run_report(self, skill: str) -> dict:
        """Generate markdown report from existing results."""
        latest = BaselineStorage.load_latest(skill)
        if not latest:
            print(f"No results found for {skill}. Run --full first.")
            return {}

        report = self._format_report(skill, latest.get("mode", "?"), latest.get("components", {}))
        print(report)
        return latest.get("components", {})

    def _run_directive_audit(self) -> dict:
        """Audit ALL skill directive files for bloat and specialization candidates. $0."""
        import os
        skill_dir = Path.home() / ".claude/skills"
        from kb_loader import ADVISORS
        advisors = set(ADVISORS.keys())

        WARN_LINES = 300
        CRIT_LINES = 500

        skills = []
        for d in sorted(skill_dir.iterdir()):
            sf = d / "SKILL.md"
            if not sf.exists():
                continue
            text = sf.read_text(encoding="utf-8")
            lines = text.splitlines()
            line_count = len(lines)
            char_count = len(text)
            sections = [l for l in lines if l.startswith("## ")]
            code_blocks = text.count("```") // 2
            modes = [l for l in lines if "MODE" in l.upper() and l.startswith("#")]
            has_kb = d.name in advisors or any(
                alias in advisors for alias in [
                    d.name.replace("ask-", ""),
                    d.name.replace("-", "_"),
                ]
            )
            tier = "CRITICAL" if line_count >= CRIT_LINES else (
                "WARNING" if line_count >= WARN_LINES else "OK")

            skills.append({
                "name": d.name,
                "lines": line_count,
                "chars": char_count,
                "sections": len(sections),
                "code_blocks": code_blocks,
                "modes": len(modes),
                "has_kb": has_kb,
                "tier": tier,
            })

        skills.sort(key=lambda x: -x["lines"])

        # Print report
        print(f"\n{'='*60}")
        print(f"  DIRECTIVE AUDIT — {len(skills)} skills")
        print(f"{'='*60}")
        print(f"  CRITICAL (>={CRIT_LINES} lines): "
              f"{sum(1 for s in skills if s['tier']=='CRITICAL')}")
        print(f"  WARNING  (>={WARN_LINES} lines): "
              f"{sum(1 for s in skills if s['tier']=='WARNING')}")
        print(f"  OK       (<{WARN_LINES} lines):  "
              f"{sum(1 for s in skills if s['tier']=='OK')}")

        print(f"\n--- SPECIALIZATION CANDIDATES ---")
        for s in skills:
            if s["tier"] == "OK":
                continue
            kb_tag = "KB" if s["has_kb"] else "DIRECTIVE-ONLY"
            flags = []
            if s["lines"] >= 1000:
                flags.append("EXTREME: likely never fully activated")
            if s["code_blocks"] >= 15:
                flags.append("reference-doc-in-disguise")
            if s["modes"] >= 3:
                flags.append(f"{s['modes']} modes → split into sub-skills")
            if s["sections"] >= 20:
                flags.append(f"{s['sections']} sections → too many concerns")
            if not s["has_kb"] and s["lines"] >= WARN_LINES:
                flags.append("no KB backing + large directives = wasted context")

            print(f"\n  {s['name']:30s} {s['lines']:5d} lines | {s['sections']:2d} sections | "
                  f"{s['code_blocks']:2d} code blocks | {kb_tag}")
            for f in flags:
                print(f"    !! {f}")

        # Summary stats
        total_chars = sum(s["chars"] for s in skills)
        avg_lines = sum(s["lines"] for s in skills) / len(skills) if skills else 0
        print(f"\n--- SUMMARY ---")
        print(f"  Total directive chars: {total_chars:,}")
        print(f"  Avg lines/skill:       {avg_lines:.0f}")
        print(f"  Skills > 300 lines:    {sum(1 for s in skills if s['lines']>=300)}/{len(skills)}")

        return {
            "total_skills": len(skills),
            "critical": [s for s in skills if s["tier"] == "CRITICAL"],
            "warning": [s for s in skills if s["tier"] == "WARNING"],
            "total_directive_chars": total_chars,
            "avg_lines": round(avg_lines),
        }

    def _run_health_all(self) -> dict:
        """Lightweight scan across all diagnosable skills."""
        print(f"\n{'='*50}")
        print(f"  SKILL HEALTH SCAN")
        print(f"{'='*50}")

        results = {}
        for skill in DIAGNOSABLE_SKILLS:
            print(f"\n--- {skill} ---")
            # Only free components: source mapping + diversity on existing corpus
            try:
                map_results = self._run_map(skill)
                corpus = ResponseCorpus.load(skill)
                has_corpus = bool(corpus)
                latest = BaselineStorage.load_latest(skill)
                stale = False
                if latest:
                    ts = latest.get("timestamp", "")
                    try:
                        dt = datetime.fromisoformat(ts)
                        stale = (datetime.now() - dt).days > 30
                    except ValueError:
                        stale = True

                results[skill] = {
                    "has_corpus": has_corpus,
                    "stale_baseline": stale,
                    "source_count": map_results.get("source_mapping", {}).get("source_count", 0),
                    "cluster_count": len(map_results.get("source_mapping", {}).get("clusters", [])),
                }
            except Exception as e:
                results[skill] = {"error": str(e)}
                print(f"  ERROR: {e}")

        # Summary
        print(f"\n{'='*50}")
        print(f"  HEALTH SUMMARY")
        print(f"{'='*50}")
        needs_attention = []
        for skill, data in results.items():
            if data.get("error"):
                needs_attention.append(f"{skill}: ERROR - {data['error']}")
            elif not data.get("has_corpus"):
                needs_attention.append(f"{skill}: No corpus (run --full)")
            elif data.get("stale_baseline"):
                needs_attention.append(f"{skill}: Stale baseline (>30 days)")

        if needs_attention:
            print(f"\nNeeds Attention ({len(needs_attention)}):")
            for item in needs_attention:
                print(f"  - {item}")
        else:
            print("\nAll skills healthy.")

        return results

    def _format_report(self, skill: str, mode: str, results: dict) -> str:
        """Format results as markdown report."""
        lines = [
            f"# Skill Diagnostic Report: {skill}",
            f"**Mode:** {mode}",
            f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        if "faithfulness" in results:
            faith = results["faithfulness"]
            lines.append("## Faithfulness")
            lines.append(f"**Average:** {faith.get('avg', 'N/A')}")
            if "per_question" in faith:
                lines.append("")
                lines.append("| Question | Claims | Grounding |")
                lines.append("|----------|--------|-----------|")
                for q_idx, data in sorted(faith["per_question"].items(), key=lambda x: int(x[0])):
                    lines.append(f"| Q{q_idx} | {data['claims_count']} | {data['grounding']:.0%} |")
            lines.append("")

        if "diversity" in results:
            div = results["diversity"]
            lines.append("## Diversity")
            lines.append(f"**Intra-skill Self-BLEU:** {div.get('intra_skill_self_bleu', 'N/A')}")
            lines.append("")

        if "source_mapping" in results:
            sm = results["source_mapping"]
            lines.append("## Source Mapping")
            lines.append(f"**Sources:** {sm.get('source_count', '?')}")
            clusters = sm.get("clusters", [])
            lines.append(f"**Clusters:** {len(clusters)}")
            for c in clusters:
                lines.append(f"- **{c['label']}:** {', '.join(c['sources'])} → Q{c['questions']}")
            lines.append("")

        if "corpus" in results:
            c = results["corpus"]
            lines.append("## Corpus")
            lines.append(f"**Generated:** {c.get('generated', '?')}/{c.get('total', '?')}")
            lines.append(f"**API calls:** {c.get('api_calls', '?')}")
            lines.append("")

        return "\n".join(lines)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Skill Diagnostic Toolchain")
    parser.add_argument("--skill", help="Skill to diagnose (e.g., cto, art-director)")
    parser.add_argument("--all", action="store_true", help="Scan all diagnosable skills")

    # Modes (mutually exclusive)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--map", action="store_true", help="Source mapping only ($0)")
    modes.add_argument("--dry-run", action="store_true", help="Self-BLEU on existing corpus ($0)")
    modes.add_argument("--generate", action="store_true", help="Generate response corpus")
    modes.add_argument("--analyze", action="store_true", help="Faithfulness + diversity + map")
    modes.add_argument("--rebuttal", action="store_true", help="Conviction under pressure")
    modes.add_argument("--full", action="store_true", help="Generate + analyze + report")
    modes.add_argument("--post-scrape", action="store_true", help="Faithfulness only")
    modes.add_argument("--health", action="store_true", help="Lightweight scan all skills")
    modes.add_argument("--report", action="store_true", help="Markdown from existing results")
    modes.add_argument("--diff", action="store_true", help="Compare to last baseline")
    modes.add_argument("--directive-audit", action="store_true",
                       help="Audit ALL skill files for bloat and specialization candidates ($0)")

    # Options
    parser.add_argument("--model", choices=["haiku", "sonnet"], default="haiku")
    parser.add_argument("--output", help="Write markdown report to file")
    parser.add_argument("--json", action="store_true", help="JSON output instead of markdown")

    args = parser.parse_args()

    # Validation
    if args.all and args.full:
        print("ERROR: --all --full is blocked (4320+ API calls). Use --all --health.", file=sys.stderr)
        sys.exit(1)

    if args.health:
        args.all = True

    if args.directive_audit:
        args.all = True

    if not args.skill and not args.all:
        print("ERROR: Specify --skill NAME or --all", file=sys.stderr)
        sys.exit(1)

    # Determine mode
    mode = None
    for m in ["map", "dry_run", "generate", "analyze", "rebuttal", "full",
              "post_scrape", "health", "report", "diff", "directive_audit"]:
        if getattr(args, m, False):
            mode = m.replace("_", "-")
            break

    diag = SkillDiagnostic(model=args.model)

    if args.all:
        results = diag.run("all", mode, output_path=args.output)
    else:
        results = diag.run(args.skill, mode, output_path=args.output)

    if args.json:
        # Serialize, handling non-serializable types
        def default_handler(o):
            if isinstance(o, set):
                return list(o)
            return str(o)
        print(json.dumps(results, indent=2, default=default_handler))


if __name__ == "__main__":
    main()
