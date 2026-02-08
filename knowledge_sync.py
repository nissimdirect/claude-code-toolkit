#!/usr/bin/env python3
"""Sync YAML frontmatter + markdown-header files <-> SQLite database

YAML/Markdown = source of truth. Database is index for fast queries.
Run this after scraping or LLM enrichment to keep DB current.
"""

import argparse
from pathlib import Path
from knowledge_db import KnowledgeDB, sync_from_yaml

# Knowledge base directories with source and skill hints
# source_hint: identifies the content source
# skill_hint: which skill/advisor this content routes to
KNOWLEDGE_DIRS = {
    # ── YAML Frontmatter Sources ──
    "cherie-hu": {
        "path": "~/Development/cherie-hu",
        "source_hint": "cherie-hu",
        "skill_hint": "cherie",
    },
    "lenny": {
        "path": "~/Development/lennys-podcast-transcripts",
        "source_hint": "lenny",
        "skill_hint": "lenny",
    },
    "chatprd": {
        "path": "~/Development/chatprd-blog",
        "source_hint": "chatprd",
        "skill_hint": "chatprd",
    },
    "jesse-cannon": {
        "path": "~/Development/jesse-cannon",
        "source_hint": "jesse-cannon",
        "skill_hint": "jesse",
    },
    "pieter-levels": {
        "path": "~/Development/indie-hackers/pieter-levels",
        "source_hint": "pieter-levels",
        "skill_hint": "indie-trinity",
    },
    "justin-welsh": {
        "path": "~/Development/indie-hackers/justin-welsh",
        "source_hint": "justin-welsh",
        "skill_hint": "indie-trinity",
    },
    "daniel-vassallo": {
        "path": "~/Development/indie-hackers/daniel-vassallo",
        "source_hint": "daniel-vassallo",
        "skill_hint": "indie-trinity",
    },
    # ── Markdown-Header Sources (New Scrapers) ──
    "don-norman": {
        "path": "~/Development/don-norman",
        "source_hint": "don-norman",
        "skill_hint": "lenny",
    },
    "nngroup": {
        "path": "~/Development/nngroup",
        "source_hint": "nngroup",
        "skill_hint": "lenny",
    },
    "valhalla-dsp": {
        "path": "~/Development/plugin-devs/valhalla-dsp",
        "source_hint": "valhalla-dsp",
        "skill_hint": "cto",
    },
    "airwindows": {
        "path": "~/Development/plugin-devs/airwindows",
        "source_hint": "airwindows",
        "skill_hint": "cto",
    },
    "fabfilter": {
        "path": "~/Development/plugin-devs/fabfilter",
        "source_hint": "fabfilter",
        "skill_hint": "cto",
    },
    "e-flux": {
        "path": "~/Development/art-criticism/e-flux-journal",
        "source_hint": "e-flux",
        "skill_hint": "atrium",
    },
    "hyperallergic": {
        "path": "~/Development/art-criticism/hyperallergic",
        "source_hint": "hyperallergic",
        "skill_hint": "atrium",
    },
    "creative-capital": {
        "path": "~/Development/art-criticism/creative-capital",
        "source_hint": "creative-capital",
        "skill_hint": "atrium",
    },
}


def sync_all(db_path: str, verbose: bool = True):
    """Sync all knowledge bases to database"""
    db = KnowledgeDB(db_path)

    total_synced = 0
    total_errors = 0

    for source_id, config in KNOWLEDGE_DIRS.items():
        source_path = Path(config["path"]).expanduser()

        if not source_path.exists():
            if verbose:
                print(f"  Skipping {source_id} (not found: {source_path})")
            continue

        if verbose:
            print(f"\n  Syncing {source_id}...")

        synced, errors = sync_from_yaml(
            source_path, db,
            source_hint=config["source_hint"],
            skill_hint=config["skill_hint"]
        )

        if verbose:
            print(f"   {synced} articles ({errors} errors)")

        total_synced += synced
        total_errors += errors

    if verbose:
        print(f"\n  Complete! Synced {total_synced} total articles ({total_errors} errors)")
        print(f"\n  Database statistics:")
        stats = db.get_stats()
        print(f"   Total: {stats['total_articles']} articles")
        print(f"\n   By source:")
        for source, count in stats['by_source'].items():
            print(f"     {source}: {count}")
        print(f"\n   By skill:")
        for skill, count in stats['by_skill'].items():
            print(f"     {skill}: {count}")

    db.close()

    return total_synced, total_errors


def sync_source(source_id: str, db_path: str, verbose: bool = True):
    """Sync single source to database"""
    if source_id not in KNOWLEDGE_DIRS:
        print(f"ERROR: Unknown source '{source_id}'")
        print(f"Available sources: {', '.join(KNOWLEDGE_DIRS.keys())}")
        return 0, 0

    config = KNOWLEDGE_DIRS[source_id]
    source_path = Path(config["path"]).expanduser()

    if not source_path.exists():
        print(f"ERROR: Source directory not found: {source_path}")
        return 0, 0

    db = KnowledgeDB(db_path)

    if verbose:
        print(f"Syncing {source_id} from {source_path}...")

    synced, errors = sync_from_yaml(
        source_path, db,
        source_hint=config["source_hint"],
        skill_hint=config["skill_hint"]
    )

    if verbose:
        print(f"Synced {synced} articles ({errors} errors)")

    db.close()

    return synced, errors


def main():
    parser = argparse.ArgumentParser(description="Sync knowledge bases to database")
    parser.add_argument("--db", default="~/Development/knowledge.db", help="Database path")
    parser.add_argument("--source", help="Sync specific source only")
    parser.add_argument("--all", action="store_true", help="Sync all knowledge bases")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    verbose = not args.quiet

    if args.all:
        sync_all(args.db, verbose=verbose)
    elif args.source:
        sync_source(args.source, args.db, verbose=verbose)
    else:
        print("ERROR: Must specify --all or --source <source_id>")
        print(f"Available sources: {', '.join(KNOWLEDGE_DIRS.keys())}")
        return 1


if __name__ == "__main__":
    main()
