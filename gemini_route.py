#!/usr/bin/env python3
"""gemini_route.py — Template-based task routing to Gemini Flash / Ollama.

Maps skill domains to prompt templates, calls the appropriate model,
and logs results for empirical evaluation.

Usage:
    python3 gemini_route.py test-gen --context src/module.py
    python3 gemini_route.py kb-summarize --context article.md
    python3 gemini_route.py commit-msg --context diff.txt
    python3 gemini_route.py css-draft --context page.html --task "Increase button padding"
    python3 gemini_route.py --list
    python3 gemini_route.py --coverage
    python3 gemini_route.py --stats
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gemini_draft import draft as gemini_draft

TEMPLATE_DIR = Path(__file__).parent / 'gemini-templates'
EVAL_LOG = Path.home() / '.claude' / '.locks' / 'gemini-route-eval.jsonl'

# ── Template metadata: skills, model compat, estimated token savings ──

TEMPLATES = {
    'test-gen': {
        'skills': ['/quality', '/ship', '/plugin', '/cto'],
        'ollama': True,
        'savings': 3500,
        'desc': 'Generate pytest tests from source code',
        'priority': 1,  # highest value
    },
    'kb-summarize': {
        'skills': ['/don-norman', '/cto', '/ask-lenny', '/music-biz', '/atrium',
                   '/art-director', '/marketing-hacker', '/audio-production',
                   '/competitive-analysis'],
        'ollama': False,  # needs large context window
        'savings': 8000,
        'desc': 'Summarize KB articles for advisor skills',
        'priority': 1,
    },
    'css-draft': {
        'skills': ['/art-director', '/ship'],
        'ollama': True,
        'savings': 2000,
        'desc': 'Generate or modify CSS from design specs',
        'priority': 2,
    },
    'commit-msg': {
        'skills': ['/session-close'],
        'ollama': True,
        'savings': 350,
        'desc': 'Generate commit messages from git diff',
        'priority': 2,
    },
    'docstring': {
        'skills': ['/quality', '/ship'],
        'ollama': True,
        'savings': 1200,
        'desc': 'Add docstrings to Python/JS source files',
        'priority': 3,
    },
    'boilerplate': {
        'skills': ['/ship', '/plugin'],
        'ollama': True,
        'savings': 1500,
        'desc': 'Generate file scaffolding and templates',
        'priority': 2,
    },
    'data-transform': {
        'skills': ['/forge', '/research-scraper'],
        'ollama': True,
        'savings': 2500,
        'desc': 'Write data transformation scripts',
        'priority': 2,
    },
    'review-pass': {
        'skills': ['/quality', '/cto', '/qa-redteam'],
        'ollama': False,  # needs deep understanding
        'savings': 2000,
        'desc': 'First-pass code review for obvious issues',
        'priority': 3,
    },
    'changelog': {
        'skills': ['/session-close', '/ship'],
        'ollama': True,
        'savings': 1500,
        'desc': 'Generate changelog from git log',
        'priority': 2,
    },
    'diff-explain': {
        'skills': ['/quality', '/session-close'],
        'ollama': True,
        'savings': 1000,
        'desc': 'Explain git diff in plain English',
        'priority': 2,
    },
    'shell-script': {
        'skills': ['/ops', '/ship', '/forge'],
        'ollama': True,
        'savings': 2000,
        'desc': 'Generate bash/zsh scripts from specs',
        'priority': 2,
    },
    'type-hints': {
        'skills': ['/quality', '/ship'],
        'ollama': True,
        'savings': 1500,
        'desc': 'Add type hints to Python files',
        'priority': 3,
    },
    'prd-section': {
        'skills': ['/ask-chatprd', '/pm', '/ask-lenny'],
        'ollama': False,  # needs nuanced product thinking
        'savings': 3000,
        'desc': 'Draft PRD sections from feature descriptions',
        'priority': 1,
    },
    'scrape-recipe': {
        'skills': ['/forge', '/research-scraper'],
        'ollama': True,
        'savings': 1500,
        'desc': 'Generate scraper config for new sources',
        'priority': 2,
    },
    'issue-draft': {
        'skills': ['/pm', '/ship', '/quality'],
        'ollama': True,
        'savings': 1000,
        'desc': 'Draft GitHub issues from bug reports',
        'priority': 2,
    },
    'obsidian-note': {
        'skills': ['/ops', '/self-improve', '/today'],
        'ollama': False,  # needs large context for raw notes
        'savings': 2000,
        'desc': 'Structure raw text into Obsidian notes',
        'priority': 2,
    },
    'error-handling': {
        'skills': ['/cto', '/quality', '/ship'],
        'ollama': True,
        'savings': 2000,
        'desc': 'Add error handling to existing code',
        'priority': 2,
    },
    'fixture-gen': {
        'skills': ['/quality', '/ship'],
        'ollama': True,
        'savings': 2000,
        'desc': 'Generate pytest fixtures from data structures',
        'priority': 3,
    },
}


def load_template(category: str) -> str:
    path = TEMPLATE_DIR / f'{category}.txt'
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text()


def fill_template(template: str, context: str = '', task: str = '') -> str:
    result = template
    if '{context}' in result:
        result = result.replace('{context}', context)
    if '{task}' in result:
        result = result.replace('{task}', task or '')
    return result


def call_ollama(prompt: str, model: str = 'qwen2.5-coder:7b', timeout: int = 60) -> str:
    import urllib.request
    import urllib.error

    payload = json.dumps({
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.3}
    }).encode('utf-8')

    req = urllib.request.Request(
        'http://localhost:11434/api/generate',
        data=payload,
        headers={'Content-Type': 'application/json'}
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read())
            return result.get('response', '')
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")


def validate_output(result: str, category: str) -> tuple[bool, str]:
    """Validate LLM output quality before logging as success.

    Returns (is_valid, reason).
    """
    if not result or not result.strip():
        return False, 'empty_output'
    stripped = result.strip()
    # Too short to be useful (< 50 chars)
    if len(stripped) < 50:
        return False, f'too_short ({len(stripped)} chars)'
    # Starts with error indicators
    error_prefixes = ['ERROR:', 'error:', 'I cannot', "I'm sorry", 'I apologize']
    for prefix in error_prefixes:
        if stripped.startswith(prefix):
            return False, f'error_response ({prefix})'
    # Category-specific checks
    if category == 'test-gen' and 'def test_' not in stripped and 'def Test' not in stripped:
        return False, 'no_test_functions'
    if category == 'css-draft' and '{' not in stripped:
        return False, 'no_css_blocks'
    if category == 'type-hints' and ':' not in stripped:
        return False, 'no_type_annotations'
    return True, 'ok'


def log_eval(category: str, model: str, context_chars: int, output_chars: int,
             duration_ms: int, success: bool):
    entry = {
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'category': category,
        'model': model,
        'context_chars': context_chars,
        'output_chars': output_chars,
        'duration_ms': duration_ms,
        'success': success,
        'est_tokens_saved': TEMPLATES.get(category, {}).get('savings', 0),
    }
    EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(EVAL_LOG, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def show_list():
    by_priority = sorted(TEMPLATES.items(), key=lambda x: x[1]['priority'])
    for cat, meta in by_priority:
        compat = 'G+O' if meta['ollama'] else 'G  '
        pri = ['', 'HIGH', 'MED', 'LOW'][meta['priority']]
        print(f"  [{compat}] {cat:20s} {pri:4s}  {meta['desc']}")
        print(f"         skills: {', '.join(meta['skills'])}")


def show_coverage():
    print("=== Gemini Route Coverage ===\n")

    all_skills = set()
    gemini_skills = set()
    ollama_skills = set()
    total_savings = 0

    by_priority = sorted(TEMPLATES.items(), key=lambda x: x[1]['priority'])
    for cat, meta in by_priority:
        pri = ['', 'HIGH', 'MED', 'LOW'][meta['priority']]
        compat = 'G+O' if meta['ollama'] else 'G  '
        print(f"  {cat:20s}  [{compat}] P{meta['priority']}  ~{meta['savings']:,} tok/call")
        print(f"  {'':20s}  {', '.join(meta['skills'])}")
        all_skills.update(meta['skills'])
        gemini_skills.update(meta['skills'])
        if meta['ollama']:
            ollama_skills.update(meta['skills'])
        total_savings += meta['savings']

    avg = total_savings // len(TEMPLATES)
    print(f"\n--- Coverage ---")
    print(f"Templates:          {len(TEMPLATES)}")
    print(f"Skills (Gemini):    {len(gemini_skills)}/36 ({len(gemini_skills)*100//36}%)")
    print(f"Skills (Ollama):    {len(ollama_skills)}/36 ({len(ollama_skills)*100//36}%)")
    print(f"Avg savings/call:   {avg:,} tokens")
    print(f"\n--- Projected Daily Savings ---")
    print(f"  50 RPD:  ~{avg*50//1000}K tokens/day")
    print(f" 100 RPD:  ~{avg*100//1000}K tokens/day")
    print(f" 200 RPD:  ~{avg*200//1000}K tokens/day")


def show_stats():
    if not EVAL_LOG.exists():
        print("No evaluation data yet. Run some routes first.")
        return

    lines = EVAL_LOG.read_text().strip().split('\n')
    entries = [json.loads(l) for l in lines if l.strip()]

    print(f"=== Gemini Route Stats ({len(entries)} calls) ===\n")

    by_cat = {}
    by_model = {}
    total_saved = 0

    for e in entries:
        cat = e['category']
        model = e['model']
        if cat not in by_cat:
            by_cat[cat] = {'count': 0, 'success': 0, 'total_ms': 0, 'saved': 0}
        by_cat[cat]['count'] += 1
        if e['success']:
            by_cat[cat]['success'] += 1
        by_cat[cat]['total_ms'] += e.get('duration_ms', 0)
        by_cat[cat]['saved'] += e.get('est_tokens_saved', 0)
        total_saved += e.get('est_tokens_saved', 0)

        if model not in by_model:
            by_model[model] = 0
        by_model[model] += 1

    for cat, s in sorted(by_cat.items()):
        rate = s['success'] / s['count'] * 100 if s['count'] else 0
        avg_ms = s['total_ms'] // s['count'] if s['count'] else 0
        print(f"  {cat:20s}  calls:{s['count']:3d}  ok:{rate:3.0f}%  avg:{avg_ms:5d}ms  saved:~{s['saved']//1000}K tok")

    print(f"\n  Total calls:       {len(entries)}")
    print(f"  Est tokens saved:  ~{total_saved:,}")
    print(f"  Models used:       {', '.join(f'{m}({c})' for m, c in by_model.items())}")


def main():
    parser = argparse.ArgumentParser(description='Route tasks to Gemini/Ollama via templates')
    parser.add_argument('category', nargs='?', help='Template category')
    parser.add_argument('--context', '-c', help='File to include as context')
    parser.add_argument('--task', '-t', help='Additional task description')
    parser.add_argument('--model', '-m', default='gemini', choices=['gemini', 'ollama'])
    parser.add_argument('--list', action='store_true', help='List templates')
    parser.add_argument('--coverage', action='store_true', help='Coverage analysis')
    parser.add_argument('--stats', action='store_true', help='Empirical stats')
    parser.add_argument('--temperature', type=float, default=0.3)
    args = parser.parse_args()

    if args.list:
        show_list()
        return
    if args.coverage:
        show_coverage()
        return
    if args.stats:
        show_stats()
        return

    if not args.category:
        parser.print_help()
        sys.exit(1)

    if args.category not in TEMPLATES:
        print(f"ERROR: Unknown category '{args.category}'. Use --list.", file=sys.stderr)
        sys.exit(1)

    meta = TEMPLATES[args.category]
    if args.model == 'ollama' and not meta['ollama']:
        print(f"WARNING: {args.category} not recommended for Ollama (needs large context)",
              file=sys.stderr)

    template = load_template(args.category)

    context = ''
    if args.context:
        ctx_path = Path(args.context).resolve()
        # Security: restrict context files to project directories
        allowed_roots = [
            Path.home() / "Development",
            Path.home() / "Documents",
            Path.home() / ".claude",
        ]
        if not any(str(ctx_path).startswith(str(r)) for r in allowed_roots):
            print(f"ERROR: Context file must be under ~/Development, ~/Documents, or ~/.claude", file=sys.stderr)
            sys.exit(1)
        if ctx_path.exists():
            context = ctx_path.read_text()
        else:
            print(f"ERROR: Context file not found: {args.context}", file=sys.stderr)
            sys.exit(1)

    prompt = fill_template(template, context=context, task=args.task or '')

    start = time.time()
    success = False
    result = ''
    try:
        if args.model == 'gemini':
            result = gemini_draft(prompt, temperature=args.temperature)
        else:
            result = call_ollama(prompt)
        success = True
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)

    duration_ms = int((time.time() - start) * 1000)

    # Validate output quality before logging as success
    if success and result:
        is_valid, reason = validate_output(result, args.category)
        if not is_valid:
            print(f"QUALITY: Output failed validation ({reason})", file=sys.stderr)
            success = False

    log_eval(
        category=args.category,
        model=args.model,
        context_chars=len(context),
        output_chars=len(result),
        duration_ms=duration_ms,
        success=success,
    )

    if result:
        print(result)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
