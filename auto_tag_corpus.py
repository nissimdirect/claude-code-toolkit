#!/usr/bin/env python3
"""
TF-IDF Auto-Tagging for Knowledge Base
Discovers emergent concepts and tags articles with [[wiki-links]]
Run every 2 weeks to keep knowledge graph fresh
"""

import os
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
            articles_dir = corpus_dir / 'articles'
            if not articles_dir.exists():
                print(f"   ⚠️  {articles_dir} not found, skipping")
                continue

            for md_file in articles_dir.glob('*.md'):
                content = md_file.read_text(encoding='utf-8')
                self.documents.append({
                    'path': md_file,
                    'content': content
                })

        self.num_docs = len(self.documents)
        print(f"   Loaded {self.num_docs} articles")

    def tokenize(self, text):
        """Extract meaningful terms (2-3 word phrases and single words)"""
        # Remove existing [[wiki-links]] to avoid re-tagging
        text = re.sub(r'\[\[(.*?)\]\]', r'\1', text)

        # Convert to lowercase
        text = text.lower()

        # Extract multi-word phrases (2-3 words)
        # Pattern: word word OR word word word
        phrases = re.findall(r'\b([a-z]+(?:\s+[a-z]+){1,2})\b', text)

        # Extract single words (longer than 3 chars, not common stop words)
        stop_words = {
            'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was',
            'were', 'been', 'have', 'has', 'had', 'will', 'would', 'could',
            'should', 'can', 'may', 'might', 'must', 'about', 'into', 'through',
            'during', 'before', 'after', 'above', 'below', 'between', 'under',
            'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
            'why', 'how', 'all', 'both', 'each', 'few', 'more', 'most', 'other',
            'some', 'such', 'only', 'own', 'same', 'than', 'too', 'very'
        }

        words = [
            word for word in re.findall(r'\b[a-z]{4,}\b', text)
            if word not in stop_words
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

    def extract_top_concepts(self, min_tfidf=0.01, min_doc_freq=3, max_concepts=500):
        """Extract top concepts across entire corpus"""
        print("🎯 Extracting top concepts...")

        tfidf_scores = self.compute_tfidf()

        # Aggregate TF-IDF scores across all documents
        concept_scores = Counter()

        for doc_id, scores in tfidf_scores.items():
            for term, score in scores.items():
                # Only include terms that appear in multiple documents
                if self.doc_freq[term] >= min_doc_freq:
                    concept_scores[term] += score

        # Get top concepts
        top_concepts = [
            term for term, score in concept_scores.most_common(max_concepts)
            if score >= min_tfidf
        ]

        print(f"   Found {len(top_concepts)} top concepts")
        return top_concepts

    def tag_document(self, content, concepts):
        """Add [[wiki-links]] to content for discovered concepts"""
        # Sort concepts by length (longest first) to avoid partial matches
        concepts = sorted(concepts, key=len, reverse=True)

        for concept in concepts:
            # Case-insensitive match, preserve original case
            pattern = re.compile(r'\b(' + re.escape(concept) + r')\b', re.IGNORECASE)

            def replace_if_not_tagged(match):
                # Check if already inside [[...]] or [...](...)
                start = max(0, match.start() - 3)
                end = min(len(content), match.end() + 3)
                context = content[start:end]

                if '[[' in context or ']]' in context:
                    return match.group(0)
                if context[match.start()-start-1:match.start()-start] == '[':
                    return match.group(0)

                return f"[[{match.group(0)}]]"

            content = pattern.sub(replace_if_not_tagged, content)

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
        '~/Development/chatprd',
        '~/Development/lenny',
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

    # Extract concepts
    concepts = tagger.extract_top_concepts(
        min_tfidf=0.01,      # Minimum TF-IDF score
        min_doc_freq=5,      # Must appear in at least 5 articles
        max_concepts=300     # Top 300 concepts max
    )

    print(f"\n📊 Top 20 Concepts:")
    for i, concept in enumerate(concepts[:20], 1):
        print(f"   {i}. {concept}")

    # Tag corpus (dry run first)
    print("\n🔍 Testing tagging (dry run)...")
    tagger.tag_corpus(concepts, dry_run=True)

    # Confirm before actually tagging
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
