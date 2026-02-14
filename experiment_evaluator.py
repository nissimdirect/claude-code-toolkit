#!/usr/bin/env python3
"""JSONL Auto-Evaluator — Mines session transcripts to evaluate experiments.

Code > Tokens. This script runs POST-HOC on JSONL session files,
extracts evidence for running experiments, and auto-logs observations.

Usage:
    python3 experiment_evaluator.py run                  # Evaluate all running experiments
    python3 experiment_evaluator.py run --session <id>   # Evaluate specific session
    python3 experiment_evaluator.py run --last N          # Evaluate last N sessions
    python3 experiment_evaluator.py dry-run               # Show what would be logged (no writes)
    python3 experiment_evaluator.py status                # Show evaluation coverage

Designed to run at session end (via /session-close) or manually.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

JSONL_DIR = Path.home() / '.claude' / 'projects' / '-Users-nissimagent'
EXPERIMENTS_JSON = Path.home() / '.claude' / '.locks' / 'experiments-state.json'
EVAL_LOG = Path.home() / '.claude' / '.locks' / 'experiment-eval-log.json'


# ---------------------------------------------------------------------------
# JSONL Parsing
# ---------------------------------------------------------------------------

def iter_jsonl(path: Path):
    """Yield parsed JSON objects from a JSONL file. Skips bad lines."""
    with open(path, 'r', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def get_session_files(last_n: int = 0, session_id: str = '') -> list:
    """Get JSONL session files, sorted newest first."""
    files = sorted(JSONL_DIR.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)
    if session_id:
        files = [f for f in files if session_id in f.stem]
    if last_n > 0:
        files = files[:last_n]
    return files


def extract_session_data(path: Path) -> dict:
    """Extract structured data from a session JSONL file.

    Returns a dict with:
        - tool_calls: list of {name, input_keys, line}
        - skill_invocations: list of {skill_name, line}
        - user_messages: list of {text, line}
        - assistant_texts: list of {text, line}
        - system_messages: list of {text, line}
        - models_used: set of model IDs
        - session_id: str
        - file_edits: list of {path, line}
        - task_agents: list of {description, line, status}
    """
    data = {
        'tool_calls': [],
        'skill_invocations': [],
        'user_messages': [],
        'assistant_texts': [],
        'system_messages': [],
        'models_used': set(),
        'session_id': path.stem,
        'file_edits': [],
        'task_agents': [],
        'compact_events': [],
        'hook_outputs': [],
        'cancel_events': [],
        'at_file_refs': [],
    }

    for i, obj in enumerate(iter_jsonl(path)):
        msg_type = obj.get('type', '')
        msg = obj.get('message', {})
        content = msg.get('content', '')
        model = msg.get('model', '')

        if model:
            data['models_used'].add(model)

        # User messages
        if msg_type == 'user' and msg.get('role') == 'user':
            if isinstance(content, str):
                data['user_messages'].append({'text': content, 'line': i})
                # Check for @file references
                at_refs = re.findall(r'@[\w./\-]+\.(?:md|py|js|ts|json)', content)
                for ref in at_refs:
                    data['at_file_refs'].append({'ref': ref, 'line': i})
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get('text', '')
                        if text:
                            data['user_messages'].append({'text': text[:2000], 'line': i})
                            at_refs = re.findall(r'@[\w./\-]+\.(?:md|py|js|ts|json)', text)
                            for ref in at_refs:
                                data['at_file_refs'].append({'ref': ref, 'line': i})

        # Assistant messages with tool calls
        if msg_type == 'assistant':
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get('type', '')

                        if block_type == 'tool_use':
                            name = block.get('name', '')
                            inp = block.get('input', {})
                            data['tool_calls'].append({
                                'name': name,
                                'input_keys': list(inp.keys()) if isinstance(inp, dict) else [],
                                'input': inp,
                                'line': i,
                            })
                            if name == 'Skill':
                                skill_name = inp.get('skill', '') if isinstance(inp, dict) else ''
                                data['skill_invocations'].append({'skill_name': skill_name, 'line': i})
                            if name == 'Edit':
                                file_path = inp.get('file_path', '') if isinstance(inp, dict) else ''
                                data['file_edits'].append({'path': file_path, 'line': i})
                            if name == 'Task':
                                desc = inp.get('description', '') if isinstance(inp, dict) else ''
                                data['task_agents'].append({'description': desc, 'line': i})
                            if name == 'TaskStop':
                                data['cancel_events'].append({'line': i, 'input': inp})

                        if block_type == 'text':
                            text = block.get('text', '')
                            if text:
                                data['assistant_texts'].append({'text': text[:2000], 'line': i})

        # System messages
        if msg_type == 'system':
            sys_content = msg.get('content', '')
            if isinstance(sys_content, str):
                data['system_messages'].append({'text': sys_content[:2000], 'line': i})
            elif isinstance(sys_content, list):
                for block in sys_content:
                    if isinstance(block, dict):
                        text = block.get('text', '')
                        if text:
                            data['system_messages'].append({'text': text[:2000], 'line': i})

        # Hook outputs: injected as <system-reminder> tags in user messages
        # Budget hook: "[Budget] 5-hour window..."
        # Skill gate: "Skill keyword detected..."
        # Check all message types for hook content (hooks inject into various places)
        check_text = json.dumps(content) if content else ''
        if check_text:
            hook_keywords = ['[Budget]', 'Skill keyword', 'hook success', 'hook fail',
                           'skill_gate', 'code_first_check', 'session_audit',
                           'UserPromptSubmit hook', 'PreToolUse hook', 'PostToolUse hook']
            for kw in hook_keywords:
                if kw in check_text:
                    data['hook_outputs'].append({'text': check_text[:500], 'line': i, 'hook_type': kw})
                    break

        # Queue operations (compact events)
        if msg_type == 'queue-operation':
            data['compact_events'].append({'line': i, 'data': str(obj)[:200]})

    return data


# ---------------------------------------------------------------------------
# Experiment Evaluators
# ---------------------------------------------------------------------------
# Each evaluator takes session_data and returns:
#   {'has_evidence': bool, 'observation': str, 'confidence': float}
# confidence: 0.0 = no data, 1.0 = definitive

def eval_002_skill_gate(data: dict) -> dict:
    """EXP-002: Skill Gate hook prevents missed skill invocations.

    Look for: /command patterns in SHORT user messages (not skill prompts).
    Skill prompts are injected as long user messages (>500 chars) — skip those.
    """
    skill_keywords = {
        'today', 'commit', 'session-close', 'lenny', 'cherie', 'jesse',
        'cto', 'chatprd', 'don-norman', 'art-director', 'plugin', 'label',
        'glitch-video', 'music-composer', 'coach', 'ship', 'creative',
        'red-team', 'qa', 'quality', 'reflect', 'self-improve', 'research',
        'scrape', 'forge', 'refresh', 'competitive', 'audio-production',
        'ghostwriter', 'lyric-analyst', 'mad-scientist', 'strategy',
        'synthesize', 'orchestrate',
    }

    total_skill_keywords_detected = 0
    total_skills_invoked = len(data['skill_invocations'])

    for msg in data['user_messages']:
        text = msg['text']
        # Skip injected skill prompts and system context (long messages)
        if len(text) > 500:
            continue
        # Skip tool results (they contain file contents, not user intent)
        if text.startswith('     1') or 'tool_use_id' in text:
            continue
        text_lower = text.lower()
        # Check for /command patterns (explicit user invocations)
        slash_commands = re.findall(r'/(\w[\w-]*)', text_lower)
        for cmd in slash_commands:
            if cmd in skill_keywords:
                total_skill_keywords_detected += 1

    if total_skill_keywords_detected == 0 and total_skills_invoked == 0:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    if total_skill_keywords_detected > 0:
        compliance_rate = total_skills_invoked / max(total_skill_keywords_detected, 1)
        obs = (f"Session {data['session_id'][:8]}: "
               f"{total_skill_keywords_detected} /skill commands in user messages, "
               f"{total_skills_invoked} Skill tool invocations. "
               f"Compliance: {compliance_rate:.0%}")
        return {
            'has_evidence': True,
            'observation': obs,
            'confidence': 0.7 if total_skill_keywords_detected >= 2 else 0.4,
        }

    return {'has_evidence': False, 'observation': '', 'confidence': 0.0}


def eval_006_hook_context(data: dict) -> dict:
    """EXP-006: UserPromptSubmit hooks with additionalContext influence behavior.

    Look for: system messages with hook output, followed by assistant behavior changes.
    """
    hook_count = len(data['hook_outputs'])
    if hook_count == 0:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    # Check if any hook output mentions budget recommendations
    budget_hooks = [h for h in data['hook_outputs'] if 'budget' in h['text'].lower() or 'model' in h['text'].lower()]
    skill_hooks = [h for h in data['hook_outputs'] if 'skill' in h['text'].lower()]

    obs = (f"Session {data['session_id'][:8]}: "
           f"{hook_count} hook outputs detected "
           f"({len(budget_hooks)} budget, {len(skill_hooks)} skill-gate). "
           f"Hook injection is active.")
    return {
        'has_evidence': True,
        'observation': obs,
        'confidence': 0.5,
    }


def eval_008_stop_and_check(data: dict) -> dict:
    """EXP-008: STOP AND CHECK block reduces behavioral errors.

    Look for: Read tool calls before Edit calls (P4 compliance),
    Skill invocations when keywords present (P36 compliance).
    """
    edits = [tc for tc in data['tool_calls'] if tc['name'] == 'Edit']
    reads = [tc for tc in data['tool_calls'] if tc['name'] == 'Read']

    if not edits:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    # For each Edit, check if a Read of the same file preceded it
    read_files = set()
    edit_files = []
    violations = 0

    for tc in data['tool_calls']:
        if tc['name'] == 'Read':
            fp = tc['input'].get('file_path', '')
            if fp:
                read_files.add(fp)
        elif tc['name'] == 'Edit':
            fp = tc['input'].get('file_path', '')
            if fp:
                edit_files.append(fp)
                if fp not in read_files:
                    violations += 1

    total = len(edit_files)
    compliant = total - violations
    rate = compliant / total if total > 0 else 0

    obs = (f"Session {data['session_id'][:8]}: "
           f"{total} Edit calls, {compliant} had prior Read ({rate:.0%} compliance). "
           f"{violations} violations (Edit without Read).")
    return {
        'has_evidence': True,
        'observation': obs,
        'confidence': 0.6 if total >= 3 else 0.3,
    }


def eval_010_hot_reload(data: dict) -> dict:
    """EXP-010: Editing agent.md doesn't take effect until session restart.

    Look for: Edit calls to SKILL.md or agent.md files within a session.
    """
    skill_edits = [e for e in data['file_edits']
                   if 'SKILL.md' in e['path'] or 'agent.md' in e['path']
                   or '/skills/' in e['path']]

    if not skill_edits:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    obs = (f"Session {data['session_id'][:8]}: "
           f"{len(skill_edits)} edits to skill/agent files: "
           f"{', '.join(e['path'].split('/')[-1] for e in skill_edits[:5])}. "
           f"Check if changes took effect in same session.")
    return {
        'has_evidence': True,
        'observation': obs,
        'confidence': 0.4,  # Can't fully determine from JSONL alone
    }


def eval_012_message_queue(data: dict) -> dict:
    """EXP-012: Messages queue while Claude processes (type during Task execution).

    Look for: user messages that appear between Task tool call and its result.
    """
    # Find Task tool calls and user messages by line number
    task_lines = [(tc['line'], tc) for tc in data['tool_calls'] if tc['name'] == 'Task']
    user_lines = [(msg['line'], msg) for msg in data['user_messages']]

    if not task_lines:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    # Check for user messages during task execution windows
    # (between a Task call and the next ~50 lines which typically contain the result)
    interleaved = 0
    for task_line, _ in task_lines:
        for user_line, user_msg in user_lines:
            if task_line < user_line < task_line + 50:
                interleaved += 1

    if interleaved > 0:
        obs = (f"Session {data['session_id'][:8]}: "
               f"{interleaved} user messages appeared during Task agent execution "
               f"({len(task_lines)} Task calls total). Messages DO queue.")
        return {'has_evidence': True, 'observation': obs, 'confidence': 0.7}

    obs = (f"Session {data['session_id'][:8]}: "
           f"{len(task_lines)} Task calls, 0 interleaved user messages. "
           f"No evidence of queuing (user may not have typed during tasks).")
    return {'has_evidence': True, 'observation': obs, 'confidence': 0.3}


def eval_013_cancel_propagation(data: dict) -> dict:
    """EXP-013: Canceling sub-agent = zero context propagation.

    Look for: TaskStop calls.
    """
    cancels = data['cancel_events']
    if not cancels:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    obs = (f"Session {data['session_id'][:8]}: "
           f"{len(cancels)} TaskStop/cancel events found. "
           f"Check assistant text after cancel for references to canceled work.")
    return {'has_evidence': True, 'observation': obs, 'confidence': 0.5}


def eval_014_compact_focus(data: dict) -> dict:
    """EXP-014: /compact with custom focus produces better summaries.

    Look for: compact events in queue-operations.
    """
    compacts = data['compact_events']
    if not compacts:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    obs = (f"Session {data['session_id'][:8]}: "
           f"{len(compacts)} compact events detected. "
           f"Review transcript for summary quality assessment.")
    return {'has_evidence': True, 'observation': obs, 'confidence': 0.3}


def eval_016_at_file_ref(data: dict) -> dict:
    """EXP-016: @file.md reference syntax works in Claude Code messages.

    Look for: @filename patterns in user messages.
    """
    refs = data['at_file_refs']
    if not refs:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    # Check if Read tool was called for referenced files shortly after
    read_files = {tc['input'].get('file_path', '') for tc in data['tool_calls'] if tc['name'] == 'Read'}
    matched = 0
    for ref in refs:
        ref_name = ref['ref'].lstrip('@')
        if any(ref_name in rf for rf in read_files):
            matched += 1

    obs = (f"Session {data['session_id'][:8]}: "
           f"{len(refs)} @file references found. "
           f"{matched}/{len(refs)} had corresponding Read calls. "
           f"Refs: {', '.join(r['ref'] for r in refs[:5])}")
    return {
        'has_evidence': True,
        'observation': obs,
        'confidence': 0.6 if len(refs) >= 2 else 0.3,
    }


def eval_020_hook_errors(data: dict) -> dict:
    """EXP-020: 3-layer hook system reduces behavioral errors.

    Proxy: count behavioral violations (Edit without Read, missing Skill invocations).
    Compare with hook activity.
    """
    # Count violations
    edit_without_read = 0
    read_files = set()
    for tc in data['tool_calls']:
        if tc['name'] == 'Read':
            fp = tc['input'].get('file_path', '')
            if fp:
                read_files.add(fp)
        elif tc['name'] == 'Edit':
            fp = tc['input'].get('file_path', '')
            if fp and fp not in read_files:
                edit_without_read += 1

    hook_count = len(data['hook_outputs'])
    total_tool_calls = len(data['tool_calls'])

    if total_tool_calls < 5:
        return {'has_evidence': False, 'observation': '', 'confidence': 0.0}

    violation_rate = edit_without_read / max(total_tool_calls, 1)
    obs = (f"Session {data['session_id'][:8]}: "
           f"{total_tool_calls} tool calls, {edit_without_read} Edit-without-Read violations "
           f"({violation_rate:.1%}). {hook_count} hook outputs active. "
           f"{'LOW' if violation_rate < 0.05 else 'MODERATE' if violation_rate < 0.15 else 'HIGH'} error rate.")
    return {
        'has_evidence': True,
        'observation': obs,
        'confidence': 0.5 if total_tool_calls >= 20 else 0.3,
    }


# Map experiment IDs to evaluator functions
EVALUATORS = {
    2: eval_002_skill_gate,
    6: eval_006_hook_context,
    8: eval_008_stop_and_check,
    10: eval_010_hot_reload,
    12: eval_012_message_queue,
    13: eval_013_cancel_propagation,
    14: eval_014_compact_focus,
    16: eval_016_at_file_ref,
    20: eval_020_hook_errors,
}


# ---------------------------------------------------------------------------
# Main Logic
# ---------------------------------------------------------------------------

def load_experiments() -> list:
    if not EXPERIMENTS_JSON.exists():
        return []
    try:
        return json.loads(EXPERIMENTS_JSON.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def save_experiments(experiments: list):
    EXPERIMENTS_JSON.parent.mkdir(parents=True, exist_ok=True)
    EXPERIMENTS_JSON.write_text(json.dumps(experiments, indent=2))


def load_eval_log() -> dict:
    """Track which sessions have been evaluated to avoid duplicate work."""
    if not EVAL_LOG.exists():
        return {'evaluated_sessions': {}}
    try:
        return json.loads(EVAL_LOG.read_text())
    except (json.JSONDecodeError, OSError):
        return {'evaluated_sessions': {}}


def save_eval_log(log: dict):
    EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
    EVAL_LOG.write_text(json.dumps(log, indent=2))


def run_evaluation(last_n: int = 3, session_id: str = '', dry_run: bool = False):
    """Run evaluators against session JSONL files."""
    experiments = load_experiments()
    running = [e for e in experiments if e['status'] == 'running']

    if not running:
        print("No running experiments to evaluate.")
        return

    eval_log = load_eval_log()
    files = get_session_files(last_n=last_n, session_id=session_id)

    if not files:
        print("No session files found.")
        return

    print(f"Evaluating {len(files)} session(s) against {len(running)} running experiments")
    print(f"Evaluators available: {sorted(EVALUATORS.keys())}")
    print()

    total_observations = 0
    observations_by_exp = defaultdict(list)

    for f in files:
        sid = f.stem[:8]

        # Skip already-evaluated sessions (unless specific session requested)
        if not session_id and sid in eval_log.get('evaluated_sessions', {}):
            print(f"  Skipping {sid} (already evaluated)")
            continue

        # Parse session data
        try:
            data = extract_session_data(f)
        except Exception as exc:
            print(f"  Error parsing {sid}: {exc}")
            continue

        file_size_kb = f.stat().st_size / 1024
        print(f"  Session {sid} ({file_size_kb:.0f} KB, {len(data['tool_calls'])} tool calls, "
              f"{len(data['user_messages'])} user msgs)")

        # Run each evaluator for running experiments
        for exp in running:
            exp_id = exp['id']
            evaluator = EVALUATORS.get(exp_id)
            if not evaluator:
                continue

            try:
                result = evaluator(data)
            except Exception as exc:
                print(f"    EXP-{exp_id:03d} evaluator error: {exc}")
                continue

            if result['has_evidence']:
                observations_by_exp[exp_id].append(result)
                total_observations += 1

                confidence_bar = '#' * int(result['confidence'] * 10)
                print(f"    EXP-{exp_id:03d} [{confidence_bar:<10}] {result['observation'][:100]}")

        # Mark session as evaluated
        if not dry_run:
            eval_log.setdefault('evaluated_sessions', {})[sid] = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'experiments_checked': [e['id'] for e in running if e['id'] in EVALUATORS],
            }

    # Write observations to experiment state
    if not dry_run and total_observations > 0:
        for exp_id, results in observations_by_exp.items():
            for exp in experiments:
                if exp['id'] == exp_id:
                    if 'observations' not in exp:
                        exp['observations'] = []
                    for r in results:
                        exp['observations'].append({
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'text': r['observation'],
                            'source': 'auto-evaluator',
                            'confidence': r['confidence'],
                        })
                    break

        save_experiments(experiments)
        save_eval_log(eval_log)

    print()
    print(f"{'[DRY RUN] ' if dry_run else ''}Total: {total_observations} observations across {len(observations_by_exp)} experiments")

    # Check for experiments ready to resolve
    for exp in experiments:
        if exp['status'] == 'running' and exp['id'] in EVALUATORS:
            obs = exp.get('observations', [])
            if len(obs) >= 3:
                high_conf = [o for o in obs if o.get('confidence', 0) >= 0.5]
                print(f"  EXP-{exp['id']:03d}: {len(obs)} observations ({len(high_conf)} high-confidence) — READY TO RESOLVE")


def show_status():
    """Show evaluation coverage: which experiments have evaluators, observation counts."""
    experiments = load_experiments()
    eval_log = load_eval_log()

    print("Experiment Evaluation Status")
    print("=" * 70)
    print()

    for exp in experiments:
        exp_id = exp['id']
        has_evaluator = exp_id in EVALUATORS
        obs_count = len(exp.get('observations', []))
        auto_obs = len([o for o in exp.get('observations', []) if o.get('source') == 'auto-evaluator'])
        status = exp['status']

        evaluator_tag = 'AUTO' if has_evaluator else 'MANUAL'
        status_icon = {'pending': '[ ]', 'running': '[~]', 'completed': '[x]',
                       'failed': '[!]', 'invalidated': '[-]'}.get(status, '[?]')

        print(f"  {status_icon} EXP-{exp_id:03d} [{evaluator_tag}] "
              f"{obs_count} obs ({auto_obs} auto) | {exp['hypothesis'][:50]}")

    sessions_evaluated = len(eval_log.get('evaluated_sessions', {}))
    total_sessions = len(list(JSONL_DIR.glob('*.jsonl')))
    print()
    print(f"Sessions evaluated: {sessions_evaluated}/{total_sessions}")
    print(f"Evaluators defined: {len(EVALUATORS)}/{len(experiments)} experiments")

    # Coverage gaps
    running_no_eval = [e for e in experiments if e['status'] == 'running' and e['id'] not in EVALUATORS]
    if running_no_eval:
        print()
        print("COVERAGE GAPS (running experiments without evaluators):")
        for e in running_no_eval:
            print(f"  EXP-{e['id']:03d}: {e['hypothesis'][:60]}")
            print(f"    → Needs manual observation or new evaluator")


def main():
    parser = argparse.ArgumentParser(description='JSONL Auto-Evaluator for Experiments')
    subparsers = parser.add_subparsers(dest='command')

    run_parser = subparsers.add_parser('run', help='Run evaluation')
    run_parser.add_argument('--session', default='', help='Specific session ID')
    run_parser.add_argument('--last', type=int, default=5, help='Evaluate last N sessions (default: 5)')

    subparsers.add_parser('dry-run', help='Show what would be logged without writing')
    subparsers.add_parser('status', help='Show evaluation coverage')

    args = parser.parse_args()

    if args.command == 'run':
        run_evaluation(last_n=args.last, session_id=args.session)
    elif args.command == 'dry-run':
        run_evaluation(last_n=5, dry_run=True)
    elif args.command == 'status':
        show_status()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
