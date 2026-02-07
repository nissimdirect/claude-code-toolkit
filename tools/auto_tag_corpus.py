#!/usr/bin/env python3
"""
TF-IDF Auto-Tagging for Knowledge Base
Discovers emergent concepts and tags articles with [[wiki-links]]
Run every 2 weeks to keep knowledge graph fresh
"""

import os
import sys
import re
from pathlib import Path
from collections import Counter, defaultdict
import math

class TFIDFTagger:
    def __init__(self, corpus_dirs):
        """
        Args:
            corpus_dirs: List of directories containing markdown articles
        """
        self.corpus_dirs = [Path(d) for d in corpus_dirs]
        self.documents = []
        self.term_freq = defaultdict(Counter)  # {doc_id: {term: count}}
        self.doc_freq = Counter()  # {term: num_docs_containing}
        self.num_docs = 0

    def load_corpus(self):
        """Load all markdown files from corpus directories"""
        print("📚 Loading corpus...")

        for corpus_dir in self.corpus_dirs:
            loaded = 0

            # Pattern 1: articles/*.md (most sources)
            articles_dir = corpus_dir / 'articles'
            if articles_dir.exists():
                for md_file in articles_dir.glob('*.md'):
                    content = md_file.read_text(encoding='utf-8')
                    self.documents.append({
                        'path': md_file,
                        'content': content
                    })
                    loaded += 1

            # Pattern 2: episodes/*/transcript.md (Lenny's Podcast)
            episodes_dir = corpus_dir / 'episodes'
            if episodes_dir.exists():
                for md_file in episodes_dir.glob('*/transcript.md'):
                    content = md_file.read_text(encoding='utf-8')
                    self.documents.append({
                        'path': md_file,
                        'content': content
                    })
                    loaded += 1

            # Pattern 3: how-i-ai/*.md (ChatPRD deep dives)
            howiai_dir = corpus_dir / 'how-i-ai'
            if howiai_dir.exists():
                for md_file in howiai_dir.glob('*.md'):
                    content = md_file.read_text(encoding='utf-8')
                    self.documents.append({
                        'path': md_file,
                        'content': content
                    })
                    loaded += 1

            if loaded == 0:
                print(f"   ⚠️  No content found in {corpus_dir}")
            else:
                print(f"   ✅ {corpus_dir.name}: {loaded} documents")

        self.num_docs = len(self.documents)
        print(f"   Total: {self.num_docs} documents")

    # Comprehensive stop words + web/markdown noise
    STOP_WORDS = {
        # Standard English stop words
        'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was',
        'were', 'been', 'have', 'has', 'had', 'will', 'would', 'could',
        'should', 'can', 'may', 'might', 'must', 'about', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'between', 'under',
        'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
        'why', 'how', 'all', 'both', 'each', 'few', 'more', 'most', 'other',
        'some', 'such', 'only', 'own', 'same', 'than', 'too', 'very',
        'also', 'just', 'like', 'know', 'think', 'want', 'going', 'really',
        'make', 'made', 'much', 'many', 'well', 'back', 'even', 'still',
        'way', 'take', 'come', 'came', 'went', 'look', 'see', 'seen',
        'over', 'down', 'part', 'long', 'what', 'which', 'their', 'them',
        'they', 'your', 'you', 'our', 'his', 'her', 'its', 'does', 'did',
        'doing', 'done', 'being', 'those', 'these', 'because', 'while',
        'until', 'since', 'though', 'actually', 'around', 'never', 'always',
        'right', 'thing', 'things', 'something', 'anything', 'everything',
        'nothing', 'someone', 'anyone', 'everyone', 'people', 'need',
        'first', 'last', 'next', 'every', 'another', 'without', 'within',
        'along', 'across', 'behind', 'beside', 'toward', 'whether',
        'already', 'enough', 'rather', 'maybe', 'often', 'quite',
        'especially', 'simply', 'however', 'although', 'getting',
        'start', 'started', 'says', 'said', 'tell', 'told', 'keep',
        'goes', 'gone', 'give', 'gave', 'given', 'feel', 'felt',
        'trying', 'tried', 'able', 'sure', 'okay',
        # Web/markdown/HTML noise
        'http', 'https', 'www', 'html', 'href', 'image', 'file', 'link',
        'click', 'read', 'subscribe', 'email', 'newsletter', 'sign',
        'free', 'download', 'upload', 'post', 'blog', 'website', 'page',
        'content', 'format', 'auto', 'scale', 'redirect', 'quality',
        'width', 'height', 'display', 'none', 'block', 'inline',
        'media', 'source', 'type', 'text', 'data', 'info', 'update',
        'updates', 'live', 'news', 'list', 'public', 'share', 'view',
        'open', 'close', 'help', 'using', 'used', 'uses',
        'beehiiv', 'utm', 'campaign', 'medium', 'referral',
        # Podcast/transcript noise
        'yeah', 'okay', 'sort', 'kind', 'mean', 'guess', 'stuff',
    }

    def tokenize(self, text):
        """Extract meaningful terms (multi-word phrases preferred over singles)"""
        # Remove existing [[wiki-links]] to avoid re-tagging
        text = re.sub(r'\[\[(.*?)\]\]', r'\1', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Remove markdown image/link syntax
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[.*?\]\(.*?\)', '', text)

        text = text.lower()

        # Extract multi-word phrases (2-3 words, all 4+ char words)
        phrases = re.findall(r'\b([a-z]{4,}(?:\s+[a-z]{4,}){1,2})\b', text)
        # Filter phrases containing stop words
        phrases = [
            p for p in phrases
            if not any(w in self.STOP_WORDS for w in p.split())
        ]

        # Single words: 5+ chars, not stop words
        words = [
            word for word in re.findall(r'\b[a-z]{5,}\b', text)
            if word not in self.STOP_WORDS
        ]

        return phrases + words

    def compute_tfidf(self):
        """Compute TF-IDF scores for all terms"""
        print("🔢 Computing TF-IDF scores...")

        # Calculate term frequencies and document frequencies
        for doc_id, doc in enumerate(self.documents):
            tokens = self.tokenize(doc['content'])
            self.term_freq[doc_id] = Counter(tokens)

            # Document frequency (how many docs contain this term)
            unique_terms = set(tokens)
            for term in unique_terms:
                self.doc_freq[term] += 1

        # Calculate TF-IDF for each document
        tfidf_scores = defaultdict(dict)

        for doc_id in range(self.num_docs):
            tf = self.term_freq[doc_id]

            for term, count in tf.items():
                # TF: normalized frequency
                tf_normalized = count / sum(tf.values())

                # IDF: inverse document frequency
                idf = math.log(self.num_docs / (1 + self.doc_freq[term]))

                # TF-IDF score
                tfidf_scores[doc_id][term] = tf_normalized * idf

        print(f"   Computed scores for {len(self.doc_freq)} unique terms")
        return tfidf_scores

    def extract_top_concepts(self, min_tfidf=0.01, min_doc_freq=10,
                             max_doc_ratio=0.4, max_concepts=200):
        """Extract top concepts across entire corpus

        Args:
            min_tfidf: Minimum aggregated TF-IDF score
            min_doc_freq: Must appear in at least this many docs
            max_doc_ratio: Skip terms appearing in more than this fraction of docs
            max_concepts: Maximum number of concepts to return
        """
        print("🎯 Extracting top concepts...")

        tfidf_scores = self.compute_tfidf()
        max_doc_count = int(self.num_docs * max_doc_ratio)

        # Aggregate TF-IDF scores across all documents
        concept_scores = Counter()

        for doc_id, scores in tfidf_scores.items():
            for term, score in scores.items():
                df = self.doc_freq[term]
                # Band-pass filter: not too rare, not too common
                if min_doc_freq <= df <= max_doc_count:
                    concept_scores[term] += score

        # Get top concepts
        top_concepts = [
            term for term, score in concept_scores.most_common(max_concepts)
            if score >= min_tfidf
        ]

        print(f"   Found {len(top_concepts)} concepts "
              f"(doc_freq: {min_doc_freq}-{max_doc_count}, "
              f"max_doc_ratio: {max_doc_ratio})")
        return top_concepts

    def tag_document(self, content, concepts):
        """Add [[wiki-links]] to content for discovered concepts.
        Only tags first occurrence per concept to avoid over-linking."""
        # Sort concepts by length (longest first) to avoid partial matches
        concepts = sorted(concepts, key=len, reverse=True)

        for concept in concepts:
            pattern = re.compile(r'\b(' + re.escape(concept) + r')\b', re.IGNORECASE)

            # Tag only first occurrence (count=1) to keep articles readable
            def make_replacer(full_content):
                def replace_if_not_tagged(match):
                    start = max(0, match.start() - 3)
                    end = min(len(full_content), match.end() + 3)
                    context = full_content[start:end]
                    if '[[' in context or ']]' in context:
                        return match.group(0)
                    return f"[[{match.group(0)}]]"
                return replace_if_not_tagged

            content = pattern.sub(make_replacer(content), content, count=1)

        return content

    def tag_corpus(self, concepts, dry_run=False):
        """Tag all documents with discovered concepts"""
        print(f"🏷️  Tagging corpus {'(DRY RUN)' if dry_run else ''}...")

        tagged_count = 0

        for doc in self.documents:
            tagged_content = self.tag_document(doc['content'], concepts)

            if tagged_content != doc['content']:
                tagged_count += 1

                if not dry_run:
                    doc['path'].write_text(tagged_content, encoding='utf-8')

        print(f"   Tagged {tagged_count}/{self.num_docs} documents")
        return tagged_count

    def generate_concept_index(self, concepts, output_path):
        """Generate INDEX of discovered concepts with counts"""
        print("📝 Generating concept index...")

        # Count occurrences of each concept
        concept_counts = Counter()

        for doc in self.documents:
            content = doc['content'].lower()
            for concept in concepts:
                if concept in content:
                    concept_counts[concept] += 1

        # Generate markdown
        index_content = f"""# Knowledge Graph Concepts

**Auto-generated via TF-IDF analysis**
**Last updated:** {Path(__file__).stat().st_mtime}
**Total concepts:** {len(concepts)}
**Corpus size:** {self.num_docs} articles

## Top Concepts by Frequency

"""

        for concept, count in concept_counts.most_common():
            index_content += f"- [[{concept}]] ({count} articles)\n"

        Path(output_path).write_text(index_content, encoding='utf-8')
        print(f"   Saved to {output_path}")


def main():
    """Run TF-IDF tagging on all advisor knowledge bases"""
    # Corpus directories
    corpora = [
        '~/Development/jesse-cannon',
        '~/Development/cherie-hu',
        '~/Development/chatprd-blog',
        '~/Development/lennys-podcast-transcripts',
        '~/Development/indie-hackers/pieter-levels',
        '~/Development/indie-hackers/justin-welsh',
        '~/Development/indie-hackers/daniel-vassallo'
    ]

    # Expand home directory
    corpora = [os.path.expanduser(d) for d in corpora]

    print("🚀 TF-IDF Auto-Tagging System\n")

    # Initialize tagger
    tagger = TFIDFTagger(corpora)

    # Load corpus
    tagger.load_corpus()

    # Extract concepts with band-pass filter
    concepts = tagger.extract_top_concepts(
        min_tfidf=0.01,       # Minimum TF-IDF score
        min_doc_freq=10,      # Must appear in at least 10 articles
        max_doc_ratio=0.4,    # Skip terms in >40% of docs (too common)
        max_concepts=200      # Top 200 concepts max
    )

    print(f"\n📊 Top 20 Concepts:")
    for i, concept in enumerate(concepts[:20], 1):
        print(f"   {i}. {concept}")

    # Tag corpus (dry run first)
    print("\n🔍 Testing tagging (dry run)...")
    tagger.tag_corpus(concepts, dry_run=True)

    # Confirm before actually tagging
    if '--auto-confirm' in sys.argv:
        response = 'yes'
    else:
        response = input("\n⚠️  Tag corpus for real? This will modify files. (yes/no): ")

    if response.lower() == 'yes':
        tagger.tag_corpus(concepts, dry_run=False)

        # Generate concept index
        index_path = os.path.expanduser('~/Documents/Obsidian/KNOWLEDGE-GRAPH-CONCEPTS.md')
        tagger.generate_concept_index(concepts, index_path)

        print("\n✅ Complete!")
    else:
        print("\n❌ Cancelled")


if __name__ == '__main__':
    main()
