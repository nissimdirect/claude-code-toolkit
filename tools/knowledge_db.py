#!/usr/bin/env python3
"""SQLite FTS5 database for knowledge base indexing

Provides fast full-text search, faceted filtering, and analytics for knowledge base articles.
Syncs with YAML frontmatter files (YAML = source of truth).
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import yaml


class KnowledgeDB:
    """SQLite FTS5 wrapper for knowledge base"""

    def __init__(self, db_path: str = "~/Development/knowledge.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Create tables if not exists"""
        cursor = self.conn.cursor()

        # Main articles table with metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                file_hash TEXT NOT NULL,

                -- Core metadata
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                source TEXT NOT NULL,
                source_url TEXT,
                skill TEXT NOT NULL,

                -- Temporal
                date_published TEXT,
                date_scraped TEXT,
                date_analyzed TEXT,
                date_indexed TEXT,

                -- Classification
                type TEXT,

                -- Content
                content TEXT NOT NULL,
                word_count INTEGER,

                -- Domain-specific (JSON field)
                domain_metadata TEXT,  -- JSON blob for flexible fields

                -- Timestamps
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tags table (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT UNIQUE NOT NULL,
                count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_tags (
                article_id INTEGER,
                tag_id INTEGER,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (article_id, tag_id)
            )
        """)

        # Topics table (many-to-many)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT UNIQUE NOT NULL,
                count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_topics (
                article_id INTEGER,
                topic_id INTEGER,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE,
                PRIMARY KEY (article_id, topic_id)
            )
        """)

        # Full-text search (FTS5)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                title,
                author,
                content,
                tags,
                topics,
                content='articles',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
                INSERT INTO articles_fts(rowid, title, author, content, tags, topics)
                VALUES (new.id, new.title, new.author, new.content, '', '');
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
                DELETE FROM articles_fts WHERE rowid = old.id;
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
                UPDATE articles_fts SET title = new.title, author = new.author, content = new.content
                WHERE rowid = new.id;
            END
        """)

        # Indexes for fast queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON articles(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_skill ON articles(skill)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_type ON articles(type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_date_published ON articles(date_published)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON articles(file_hash)")

        self.conn.commit()

    def add_article(self, file_path: Path, metadata: Dict, content: str) -> int:
        """Add article to database"""
        cursor = self.conn.cursor()

        # Calculate file hash
        file_hash = self._hash_content(content)

        # Coerce date objects to strings (YAML parses bare dates as date objects)
        for key in list(metadata.keys()):
            if hasattr(metadata[key], 'isoformat'):
                metadata[key] = metadata[key].isoformat()

        # Extract domain-specific metadata
        domain_fields = {}
        known_fields = {'title', 'author', 'source', 'source_url', 'skill', 'date_published',
                       'date_scraped', 'date_analyzed', 'type', 'tags', 'topics'}
        for key, value in metadata.items():
            if key not in known_fields:
                domain_fields[key] = value

        # Insert article
        cursor.execute("""
            INSERT OR REPLACE INTO articles
            (file_path, file_hash, title, author, source, source_url, skill,
             date_published, date_scraped, date_analyzed, date_indexed,
             type, content, word_count, domain_metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(file_path),
            file_hash,
            metadata.get('title', 'Untitled'),
            metadata.get('author', 'Unknown'),
            metadata.get('source', ''),
            metadata.get('source_url', ''),
            metadata.get('skill', ''),
            metadata.get('date_published', ''),
            metadata.get('date_scraped', ''),
            metadata.get('date_analyzed', ''),
            datetime.now().isoformat(),
            metadata.get('type', 'article'),
            content,
            len(content.split()),
            json.dumps(domain_fields, default=str) if domain_fields else None
        ))

        article_id = cursor.lastrowid

        # Add tags
        tags = metadata.get('tags', [])
        if tags:
            self._add_tags(article_id, tags)

        # Add topics
        topics = metadata.get('topics', [])
        if topics:
            self._add_topics(article_id, topics)

        self.conn.commit()
        return article_id

    def _add_tags(self, article_id: int, tags: List[str]):
        """Add tags for article"""
        cursor = self.conn.cursor()

        for tag in tags:
            # Insert or increment tag
            cursor.execute("""
                INSERT INTO tags (tag, count) VALUES (?, 1)
                ON CONFLICT(tag) DO UPDATE SET count = count + 1
            """, (tag,))

            # Link to article
            cursor.execute("SELECT id FROM tags WHERE tag = ?", (tag,))
            tag_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT OR IGNORE INTO article_tags (article_id, tag_id)
                VALUES (?, ?)
            """, (article_id, tag_id))

    def _add_topics(self, article_id: int, topics: List[str]):
        """Add topics for article"""
        cursor = self.conn.cursor()

        for topic in topics:
            # Insert or increment topic
            cursor.execute("""
                INSERT INTO topics (topic, count) VALUES (?, 1)
                ON CONFLICT(topic) DO UPDATE SET count = count + 1
            """, (topic,))

            # Link to article
            cursor.execute("SELECT id FROM topics WHERE topic = ?", (topic,))
            topic_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT OR IGNORE INTO article_topics (article_id, topic_id)
                VALUES (?, ?)
            """, (article_id, topic_id))

    def search(self, query: str, filters: Optional[Dict] = None, limit: int = 20) -> List[Dict]:
        """Full-text search with optional filters"""
        cursor = self.conn.cursor()

        # Base FTS query
        sql = """
            SELECT a.*,
                   GROUP_CONCAT(DISTINCT t.tag) as tags,
                   GROUP_CONCAT(DISTINCT tp.topic) as topics,
                   articles_fts.rank
            FROM articles_fts
            JOIN articles a ON articles_fts.rowid = a.id
            LEFT JOIN article_tags at ON a.id = at.article_id
            LEFT JOIN tags t ON at.tag_id = t.id
            LEFT JOIN article_topics atop ON a.id = atop.article_id
            LEFT JOIN topics tp ON atop.topic_id = tp.id
            WHERE articles_fts MATCH ?
        """

        params = [query]

        # Apply filters
        if filters:
            if 'source' in filters:
                sql += " AND a.source = ?"
                params.append(filters['source'])

            if 'skill' in filters:
                sql += " AND a.skill = ?"
                params.append(filters['skill'])

            if 'type' in filters:
                sql += " AND a.type = ?"
                params.append(filters['type'])

            if 'date_from' in filters:
                sql += " AND a.date_published >= ?"
                params.append(filters['date_from'])

            if 'date_to' in filters:
                sql += " AND a.date_published <= ?"
                params.append(filters['date_to'])

        sql += " GROUP BY a.id ORDER BY rank LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_by_source(self, source: str) -> List[Dict]:
        """Get all articles from a source"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT a.*,
                   GROUP_CONCAT(DISTINCT t.tag) as tags,
                   GROUP_CONCAT(DISTINCT tp.topic) as topics
            FROM articles a
            LEFT JOIN article_tags at ON a.id = at.article_id
            LEFT JOIN tags t ON at.tag_id = t.id
            LEFT JOIN article_topics atop ON a.id = atop.article_id
            LEFT JOIN topics tp ON atop.topic_id = tp.id
            WHERE a.source = ?
            GROUP BY a.id
            ORDER BY a.date_published DESC
        """, (source,))

        return [dict(row) for row in cursor.fetchall()]

    def get_by_skill(self, skill: str) -> List[Dict]:
        """Get all articles for a skill"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT a.*,
                   GROUP_CONCAT(DISTINCT t.tag) as tags,
                   GROUP_CONCAT(DISTINCT tp.topic) as topics
            FROM articles a
            LEFT JOIN article_tags at ON a.id = at.article_id
            LEFT JOIN tags t ON at.tag_id = t.id
            LEFT JOIN article_topics atop ON a.id = atop.article_id
            LEFT JOIN topics tp ON atop.topic_id = tp.id
            WHERE a.skill = ?
            GROUP BY a.id
            ORDER BY a.date_published DESC
        """, (skill,))

        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict:
        """Get database statistics"""
        cursor = self.conn.cursor()

        stats = {}

        # Total articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        stats['total_articles'] = cursor.fetchone()[0]

        # By source
        cursor.execute("SELECT source, COUNT(*) as count FROM articles GROUP BY source ORDER BY count DESC")
        stats['by_source'] = {row['source']: row['count'] for row in cursor.fetchall()}

        # By skill
        cursor.execute("SELECT skill, COUNT(*) as count FROM articles GROUP BY skill ORDER BY count DESC")
        stats['by_skill'] = {row['skill']: row['count'] for row in cursor.fetchall()}

        # By type
        cursor.execute("SELECT type, COUNT(*) as count FROM articles GROUP BY type ORDER BY count DESC")
        stats['by_type'] = {row['type']: row['count'] for row in cursor.fetchall()}

        # Top tags
        cursor.execute("SELECT tag, count FROM tags ORDER BY count DESC LIMIT 20")
        stats['top_tags'] = {row['tag']: row['count'] for row in cursor.fetchall()}

        # Top topics
        cursor.execute("SELECT topic, count FROM topics ORDER BY count DESC LIMIT 20")
        stats['top_topics'] = {row['topic']: row['count'] for row in cursor.fetchall()}

        return stats

    def _hash_content(self, content: str) -> str:
        """Simple hash of content for change detection"""
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()

    def close(self):
        """Close database connection"""
        self.conn.close()


def sync_from_yaml(source_dir: Path, db: KnowledgeDB):
    """Sync articles from YAML frontmatter files into database"""
    synced = 0
    errors = 0

    for md_file in source_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding='utf-8')

            # Extract YAML frontmatter
            if not content.startswith('---'):
                continue

            parts = content.split('---', 2)
            if len(parts) < 3:
                continue

            metadata = yaml.safe_load(parts[1])
            article_content = parts[2].strip()

            # Add to database
            db.add_article(md_file, metadata, article_content)
            synced += 1

        except Exception as e:
            print(f"ERROR syncing {md_file}: {e}")
            errors += 1

    return synced, errors


def main():
    """CLI for knowledge database"""
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge base database tool")
    parser.add_argument("command", choices=['sync', 'stats', 'search', 'query'])
    parser.add_argument("--db", default="~/Development/knowledge.db", help="Database path")
    parser.add_argument("--source", help="Source directory to sync")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--skill", help="Filter by skill")
    parser.add_argument("--limit", type=int, default=20, help="Result limit")

    args = parser.parse_args()

    db = KnowledgeDB(args.db)

    if args.command == 'sync':
        if not args.source:
            print("ERROR: --source required for sync")
            return 1

        source_path = Path(args.source).expanduser()
        print(f"Syncing from {source_path}...")
        synced, errors = sync_from_yaml(source_path, db)
        print(f"✅ Synced {synced} articles ({errors} errors)")

    elif args.command == 'stats':
        stats = db.get_stats()
        print(f"\n📊 Knowledge Base Statistics")
        print(f"Total articles: {stats['total_articles']}")

        print(f"\nBy source:")
        for source, count in stats['by_source'].items():
            print(f"  {source}: {count}")

        print(f"\nBy skill:")
        for skill, count in stats['by_skill'].items():
            print(f"  {skill}: {count}")

        print(f"\nTop tags:")
        for tag, count in list(stats['top_tags'].items())[:10]:
            print(f"  {tag}: {count}")

    elif args.command == 'search':
        if not args.query:
            print("ERROR: --query required for search")
            return 1

        filters = {}
        if args.skill:
            filters['skill'] = args.skill

        results = db.search(args.query, filters=filters, limit=args.limit)
        print(f"\n🔍 Found {len(results)} results for '{args.query}'")

        for result in results:
            print(f"\n{result['title']}")
            print(f"  By {result['author']} | {result['source']} | {result['date_published']}")
            print(f"  Tags: {result.get('tags', 'None')}")
            print(f"  {result['file_path']}")

    elif args.command == 'query':
        if args.skill:
            results = db.get_by_skill(args.skill)
            print(f"\n📚 {len(results)} articles for skill '{args.skill}'")
            for result in results:
                print(f"  - {result['title']} ({result['source']})")

    db.close()


if __name__ == "__main__":
    main()
