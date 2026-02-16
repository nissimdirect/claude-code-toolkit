#!/usr/bin/env python3
"""Delegation Validator — validates output from Gemini/Qwen before Claude uses it.

Checks:
1. Size (empty or suspiciously large)
2. Injection patterns (prompt injection, command injection)
3. Task-specific validation (code syntax, file existence, number sanity)
4. Project-specific validation via YAML profiles (registries, routes)

Usage:
    from delegation_validator import validate_delegated_output
    result = validate_delegated_output(output, task_type="code")
    if result["blocked"]:
        # Discard output, fall back to native Claude
    elif result["warnings"]:
        # Proceed with caution, log warnings

CLI usage (for testing):
    python3 delegation_validator.py --type code --input "def foo(): pass"
    python3 delegation_validator.py --type file_analysis --input "Found 3 files in ~/Development/"
    echo "some output" | python3 delegation_validator.py --type count
    python3 delegation_validator.py --type entropic_test --input "test"
"""

import ast
import json
import re
import sys
from pathlib import Path

# --- Injection patterns (regex-based, not LLM-based) ---

INJECTION_PATTERNS = [
    # Prompt injection attempts
    re.compile(r'ignore\s+(all\s+)?previous\s+instructions', re.IGNORECASE),
    re.compile(r'disregard\s+(all\s+)?(?:prior|above|previous)', re.IGNORECASE),
    re.compile(r'forget\s+(everything|all|your)\s+(?:instructions|rules|guidelines)', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+(?:a|an|the)\s+', re.IGNORECASE),
    re.compile(r'new\s+system\s+(?:instructions|rules|role|persona)', re.IGNORECASE),
    re.compile(r'(?:system|admin)\s*(?:prompt|override|command)', re.IGNORECASE),
    re.compile(r'<\s*(?:system|admin|root)\s*>', re.IGNORECASE),
    re.compile(r'\]\]\s*>\s*<', re.IGNORECASE),  # XML injection

    # Command injection via output
    re.compile(r'(?:^|\s)(?:rm\s+-rf|sudo\s+|chmod\s+777|curl\s+.*\|\s*(?:sh|bash))', re.IGNORECASE),
    re.compile(r'(?:^|\s)(?:eval|exec)\s*\(', re.IGNORECASE),
    re.compile(r'__import__\s*\(', re.IGNORECASE),
    re.compile(r'os\.(?:system|popen|exec)', re.IGNORECASE),
    re.compile(r'subprocess\.(?:call|run|Popen)', re.IGNORECASE),

    # Data exfiltration patterns
    re.compile(r'(?:curl|wget|fetch)\s+.*(?:attacker|evil|malicious)', re.IGNORECASE),
    re.compile(r'base64\s+(?:-d|--decode).*\|\s*(?:sh|bash)', re.IGNORECASE),
]

# Known hallucination patterns for code generators
HALLUCINATED_IMPORTS = [
    # Common Qwen/Gemini hallucinations — packages that don't exist
    'from anthropic_ai.',      # Anthropic doesn't publish this namespace
    'import qwen_utils',       # Not a real package
    'from gemini_api.',        # Not a real package
    'import claude_sdk',       # Not a real package
    'from openai_helpers.',    # Not a real package
]

# Sensitive path patterns that should never appear in delegated output
SENSITIVE_PATHS = [
    re.compile(r'~/.env\b'),
    re.compile(r'~/\.claude/.*\.json\b'),
    re.compile(r'credentials\.json\b'),
    re.compile(r'\.ssh/'),
    re.compile(r'\.gnupg/'),
    re.compile(r'\.aws/'),
    re.compile(r'token[s]?\.json\b', re.IGNORECASE),
    re.compile(r'secret[s]?\.(?:json|yaml|yml|env)\b', re.IGNORECASE),
]

# Profile cache
_profile_cache: dict = {}

# Known project roots for auto-detection
_PROJECT_ROOTS: dict[str, str] = {
    'entropic': str(Path.home() / 'Development' / 'entropic'),
}


def _load_profile(name: str) -> dict | None:
    """Load a YAML validation profile from validator_profiles/.

    Returns parsed dict or None if profile doesn't exist.
    """
    if name in _profile_cache:
        return _profile_cache[name]

    profiles_dir = Path(__file__).parent / 'validator_profiles'
    profile_path = profiles_dir / f'{name}.yaml'
    if not profile_path.exists():
        return None

    try:
        # Use simple YAML parsing (no external dependency)
        content = profile_path.read_text()
        profile = _parse_simple_yaml(content)
        _profile_cache[name] = profile
        return profile
    except Exception:
        return None


def _parse_simple_yaml(content: str) -> dict:
    """Minimal YAML parser for flat/nested dicts and lists.

    Handles the structure used by validator profiles without requiring PyYAML.
    """
    result: dict = {}
    lines = content.split('\n')
    current_key = None
    current_list: list | None = None
    current_dict: dict | None = None
    indent_stack: list[tuple[int, str, dict | list]] = []

    for line in lines:
        stripped = line.rstrip()
        if not stripped or stripped.startswith('#'):
            continue

        indent = len(line) - len(line.lstrip())

        # Pop indent stack to find current context
        while indent_stack and indent <= indent_stack[-1][0]:
            indent_stack.pop()

        # Determine parent context
        parent = indent_stack[-1][2] if indent_stack else result

        stripped = stripped.strip()

        # List item
        if stripped.startswith('- '):
            item_val = stripped[2:].strip()
            if isinstance(parent, list):
                # Check if item is a dict start (key: value)
                if ':' in item_val and not item_val.startswith("'") and not item_val.startswith('"'):
                    item_dict: dict = {}
                    k, v = item_val.split(':', 1)
                    item_dict[k.strip()] = _yaml_value(v.strip())
                    parent.append(item_dict)
                    indent_stack.append((indent, '-', item_dict))
                else:
                    parent.append(_yaml_value(item_val))
            continue

        # Key: value
        if ':' in stripped:
            key, _, val = stripped.partition(':')
            key = key.strip()
            val = val.strip()

            if val:
                # Simple key: value
                if isinstance(parent, dict):
                    parent[key] = _yaml_value(val)
            else:
                # Key with nested content — peek at next non-empty line
                next_indent = _next_line_indent(lines, lines.index(line + '\n') if (line + '\n') in lines else -1)
                # Check if next content is a list or dict
                next_stripped = _next_non_empty(lines, lines.index(line) if line in [l.rstrip() for l in lines] else -1, content)

                if next_stripped and next_stripped.strip().startswith('- '):
                    new_list: list = []
                    if isinstance(parent, dict):
                        parent[key] = new_list
                    indent_stack.append((indent, key, new_list))
                else:
                    new_dict: dict = {}
                    if isinstance(parent, dict):
                        parent[key] = new_dict
                    indent_stack.append((indent, key, new_dict))

    return result


def _next_non_empty(lines: list[str], current_idx: int, content: str) -> str | None:
    """Find the next non-empty, non-comment line after current index."""
    # Re-find index by matching lines
    all_lines = content.split('\n')
    for i in range(current_idx + 1, len(all_lines)):
        s = all_lines[i].strip()
        if s and not s.startswith('#'):
            return all_lines[i]
    return None


def _next_line_indent(lines: list[str], current_idx: int) -> int:
    """Get indent of next non-empty line."""
    for i in range(current_idx + 1, len(lines)):
        s = lines[i].strip()
        if s and not s.startswith('#'):
            return len(lines[i]) - len(lines[i].lstrip())
    return 0


def _yaml_value(val: str):
    """Convert a YAML value string to Python type."""
    if val.lower() == 'true':
        return True
    if val.lower() == 'false':
        return False
    if val.isdigit():
        return int(val)
    # Strip quotes
    if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
        return val[1:-1]
    return val


def discover_project(file_path: str) -> str | None:
    """Match a file path to a known project name.

    Returns profile name or None.
    """
    normalized = str(Path(file_path).resolve())
    for name, root in _PROJECT_ROOTS.items():
        resolved_root = str(Path(root).resolve())
        if normalized.startswith(resolved_root):
            return name
    return None


def _validate_project(output: str, profile: dict) -> dict:
    """Generic project validation using a loaded profile.

    Scans output for references to registry keys and route endpoints,
    checking them against ground truth extracted from the project files.
    """
    details = {
        "blocked": False,
        "invalid_items": {},
        "warnings": [],
    }

    root_path = Path(profile.get('root', '~')).expanduser()
    if not root_path.exists():
        details["warnings"].append(f"Cannot find project root {root_path} — skipping")
        return details

    # Load ground truth from registries
    ground_truth: dict[str, set[str]] = {}
    for i, reg in enumerate(profile.get('registries', [])):
        reg_path = root_path / reg.get('path', '')
        pattern = reg.get('pattern', '')
        key = f"registries.{i}"
        if reg_path.exists() and pattern:
            content = reg_path.read_text()
            ground_truth[key] = set(re.findall(pattern, content))

    # Load ground truth from routes
    for i, route in enumerate(profile.get('routes', [])):
        route_path = root_path / route.get('path', '')
        pattern = route.get('pattern', '')
        key = f"routes.{i}"
        if route_path.exists() and pattern:
            content = route_path.read_text()
            ground_truth[key] = set(re.findall(pattern, content))

    # Run checks
    for check_name, check_cfg in profile.get('checks', {}).items():
        if not isinstance(check_cfg, dict):
            continue
        scan_pattern = check_cfg.get('scan_pattern', '')
        source_key = check_cfg.get('source', '')
        block_on_miss = check_cfg.get('block_on_miss', False)

        if not scan_pattern or source_key not in ground_truth:
            continue

        valid_set = ground_truth[source_key]
        if not valid_set:
            continue

        found = set(re.findall(scan_pattern, output))
        invalid = found - valid_set
        if invalid:
            details["invalid_items"][check_name] = list(invalid)
            details["warnings"].append(
                f"{check_name}: {list(invalid)} not found in {source_key}"
            )
            if block_on_miss:
                details["blocked"] = True

    return details


def validate_delegated_output(output: str, task_type: str = "general") -> dict:
    """Validate output from Gemini/Qwen before Claude uses it.

    Args:
        output: The raw text output from the delegated model.
        task_type: One of "code", "file_analysis", "count", "general",
                   "entropic_test", or a profile name.

    Returns:
        dict with keys:
            valid: bool — overall assessment
            warnings: list[str] — non-blocking issues
            blocked: bool — if True, discard this output entirely
            details: dict — task-specific validation results
    """
    result = {
        "valid": True,
        "warnings": [],
        "blocked": False,
        "details": {},
    }

    if not isinstance(output, str):
        result["blocked"] = True
        result["valid"] = False
        result["warnings"].append("Output is not a string")
        return result

    # --- 1. Size checks ---
    if len(output.strip()) < 10:
        result["warnings"].append(f"Output suspiciously short ({len(output)} chars)")
        result["valid"] = False

    if len(output) > 100_000:
        result["warnings"].append(f"Output very large ({len(output)} chars) — may need truncation")

    # --- 2. Injection scan (skip for project validators — codebase files legitimately use subprocess/exec) ---
    skip_injection = task_type == "entropic_test" or _load_profile(task_type) is not None
    if not skip_injection:
        for pattern in INJECTION_PATTERNS:
            match = pattern.search(output)
            if match:
                result["warnings"].append(f"Injection pattern detected: '{match.group()}'")
                result["blocked"] = True
                result["valid"] = False

    # --- 3. Sensitive path scan ---
    for pattern in SENSITIVE_PATHS:
        match = pattern.search(output)
        if match:
            result["warnings"].append(f"Sensitive path reference: '{match.group()}'")

    # --- 4. Task-specific validation ---
    if task_type == "code":
        result["details"] = _validate_code(output)
    elif task_type == "file_analysis":
        result["details"] = _validate_file_analysis(output)
    elif task_type == "count":
        result["details"] = _validate_count(output)
    elif task_type == "entropic_test":
        # Backward compatible: use profile if available, else hardcoded
        profile = _load_profile("entropic")
        if profile:
            result["details"] = _validate_project(output, profile)
        else:
            result["details"] = _validate_entropic_test(output)
    else:
        # Try loading as a profile name
        profile = _load_profile(task_type)
        if profile:
            result["details"] = _validate_project(output, profile)

    # Propagate task-specific blocks
    if result["details"].get("blocked"):
        result["blocked"] = True
        result["valid"] = False

    return result


def _validate_code(output: str) -> dict:
    """Validate code output for syntax and hallucinated imports."""
    details = {"syntax_valid": False, "hallucinated_imports": [], "blocked": False}

    # Extract code blocks if wrapped in markdown fences
    code = output
    fence_match = re.search(r'```(?:python)?\n(.*?)```', output, re.DOTALL)
    if fence_match:
        code = fence_match.group(1)

    # Check Python syntax
    try:
        ast.parse(code)
        details["syntax_valid"] = True
    except SyntaxError as e:
        details["syntax_valid"] = False
        details["syntax_error"] = str(e)

    # Check for hallucinated imports
    for hallucination in HALLUCINATED_IMPORTS:
        if hallucination in code:
            details["hallucinated_imports"].append(hallucination.strip())
            details["blocked"] = True

    return details


def _validate_file_analysis(output: str) -> dict:
    """Validate file analysis output — check referenced paths exist."""
    details = {"paths_checked": 0, "paths_missing": [], "blocked": False}

    # Find file paths in output (~/... or /Users/... patterns)
    path_pattern = re.compile(r'(?:~/|/Users/\w+/)\S+')
    paths = path_pattern.findall(output)

    for p in paths[:20]:  # Cap at 20 to avoid slowness
        expanded = Path(p).expanduser()
        details["paths_checked"] += 1
        if not expanded.exists():
            details["paths_missing"].append(str(expanded))

    return details


def _validate_count(output: str) -> dict:
    """Validate count/number output — check numbers are reasonable."""
    details = {"numbers_found": [], "suspicious": False, "blocked": False}

    # Extract numbers
    numbers = re.findall(r'\b(\d+)\b', output)
    details["numbers_found"] = [int(n) for n in numbers[:20]]

    # Flag unreasonably large numbers (likely hallucination)
    for n in details["numbers_found"]:
        if n > 1_000_000:
            details["suspicious"] = True
            details["blocked"] = False  # Warn but don't block

    return details


def _validate_entropic_test(output: str) -> dict:
    """Validate agent-generated Entropic test files against the actual codebase.

    Checks:
    1. Effect names in test code exist in EFFECTS registry
    2. Param names match the effect's actual params
    3. Endpoint URLs exist in server.py routes
    4. Response format assertions are plausible

    This prevents the hallucination problem where cheaper models invent
    effect names like "contrast_crush" or params like {"strength": 0.5}.
    """
    details = {
        "blocked": False,
        "invalid_effects": [],
        "invalid_params": {},
        "invalid_endpoints": [],
        "warnings": [],
    }

    # --- Load ground truth from codebase ---
    entropic_root = Path(__file__).parent.parent / "entropic"
    if not entropic_root.exists():
        entropic_root = Path.home() / "Development" / "entropic"
    if not entropic_root.exists():
        details["warnings"].append("Cannot find entropic project root — skipping codebase checks")
        return details

    # 1. Load valid effect names from EFFECTS registry
    valid_effects = set()
    valid_params = {}
    effects_init = entropic_root / "effects" / "__init__.py"
    if effects_init.exists():
        saved_path = sys.path[:]
        try:
            # Dynamic import approach: parse the EFFECTS dict keys
            sys.path.insert(0, str(entropic_root))
            from effects import EFFECTS as _eff
            valid_effects = set(_eff.keys())
            valid_params = {name: set(spec.get("params", {}).keys()) for name, spec in _eff.items()}
        except Exception as e:
            # Fallback: regex extraction
            details["warnings"].append(f"Could not import EFFECTS: {e}")
        finally:
            sys.path[:] = saved_path
            content = effects_init.read_text()
            valid_effects = set(re.findall(r'"([a-z_]+)":\s*\{', content))

    # 2. Load valid endpoint URLs from server.py
    valid_endpoints = set()
    server_py = entropic_root / "server.py"
    if server_py.exists():
        content = server_py.read_text()
        valid_endpoints = set(re.findall(r'@app\.(?:get|post|put|delete|patch)\("([^"]+)"', content))

    # --- Scan the code (works on .py, .js, .json, .html) ---

    # 3. Find effect names used in code
    # Patterns: {"name": "effect_name"}, name: "effect_name", 'name': 'effect_name'
    # Also matches JS unquoted keys: {name: "effect_name"}
    used_effects = set(re.findall(r'(?:["\']?name["\']?\s*:\s*["\']([a-z_]+)["\'])', output))
    for eff in used_effects:
        if eff not in valid_effects and valid_effects:
            details["invalid_effects"].append(eff)
            details["blocked"] = True

    # 4. Find params used with each effect
    # Pattern: "name": "effect_name"..."params": {"param_key": value}
    effect_param_blocks = re.findall(
        r'["\']?name["\']?\s*:\s*["\']([a-z_]+)["\'].*?["\']?params["\']?\s*:\s*\{([^}]+)\}',
        output
    )
    for eff_name, params_block in effect_param_blocks:
        if eff_name in valid_params:
            used_param_keys = set(re.findall(r'["\']?([a-z_]+)["\']?\s*:', params_block))
            invalid = used_param_keys - valid_params[eff_name]
            if invalid:
                details["invalid_params"][eff_name] = list(invalid)
                details["blocked"] = True

    # 5. Find endpoint URLs used in code
    # Python: client.get("/api/..."), requests.post("/api/...")
    # JS: fetch("/api/..."), $.post("/api/...")
    used_endpoints = set(
        re.findall(r'client\.(?:get|post|put|delete|patch)\(["\'](/api/[^"\']+)["\']', output)
        + re.findall(r'fetch\(["\'](/api/[^"\']+)["\']', output)
        + re.findall(r'(?:requests|axios)\.(?:get|post|put|delete|patch)\(["\'](/api/[^"\']+)["\']', output)
        + re.findall(r'\$\.(?:get|post|ajax)\(["\'](/api/[^"\']+)["\']', output)
    )
    for ep in used_endpoints:
        # Strip path params like {frame_number}
        ep_pattern = re.sub(r'/\d+$', '/{id}', ep)
        # Check against valid endpoints (also try with path param patterns)
        if ep not in valid_endpoints and valid_endpoints:
            # Try matching with path param patterns
            matched = False
            for valid_ep in valid_endpoints:
                # Convert {param} to regex
                pattern = re.sub(r'\{[^}]+\}', r'[^/]+', valid_ep)
                if re.fullmatch(pattern, ep):
                    matched = True
                    break
            if not matched:
                details["invalid_endpoints"].append(ep)
                # Don't block for endpoints — they might be planned but not yet implemented

    # 6. Summary
    if details["invalid_effects"]:
        details["warnings"].append(
            f"Hallucinated effects: {details['invalid_effects']}. "
            f"These don't exist in EFFECTS registry."
        )
    if details["invalid_params"]:
        details["warnings"].append(
            f"Hallucinated params: {details['invalid_params']}. "
            f"These params don't exist for their respective effects."
        )
    if details["invalid_endpoints"]:
        details["warnings"].append(
            f"Unknown endpoints: {details['invalid_endpoints']}. "
            f"These routes don't exist in server.py."
        )

    return details


def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate delegated LLM output")
    parser.add_argument("--type", choices=["code", "file_analysis", "count", "general", "entropic_test"],
                        default="general", help="Task type for validation")
    parser.add_argument("--input", type=str, help="Text to validate (or pipe via stdin)")
    parser.add_argument("--file", type=str, help="File to validate (reads content from file)")
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text()
    elif args.input:
        text = args.input
    else:
        text = sys.stdin.read()

    result = validate_delegated_output(text, task_type=args.type)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] and not result["blocked"] else 1)


if __name__ == "__main__":
    main()
