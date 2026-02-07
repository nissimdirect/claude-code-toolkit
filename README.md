# Claude Code Toolkit

A collection of tools, skills, and infrastructure for Claude Code power users.

## Tools
- **session_tracker.py** — Stop hook for multi-session coordination, heartbeats, conflict detection, resource tracking
- **rotate_input_log.py** — Log rotation with monthly archives (200-line cap)
- **auto_tag_corpus.py** — TF-IDF wiki-link tagger for Obsidian knowledge graphs
- **add_frontmatter.py** — YAML frontmatter generator from metadata.json
- **strip_wikilinks.py** — Bulk wiki-link removal from markdown files
- **context_db.py** — Semantic caching and file freshness tracking

## Skills
Reusable prompt templates for specialized workflows. See `skills/` directory.

## Setup
1. Clone this repo
2. Copy tools to `~/Development/tools/`
3. Copy skills to `~/.claude/skills/`
4. Configure stop hook in `~/.claude/settings.local.json`

## License
MIT

