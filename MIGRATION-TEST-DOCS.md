# Knowledge Base Migration - Test Documentation

**Deliverable:** Unified knowledge base architecture
**Version:** 1.0
**Date:** 2026-02-07

---

## Use Cases Covered

### UC-1: Skills Access Articles at Old Paths
**Description:** Skills that reference old paths (`~/Development/[source]/articles/*.md`) must continue to work
**Implementation:** Symlinks created from `articles/` → `raw/`
**Test:** Read article via old path, verify content matches

### UC-2: Skills Access Articles at New Paths
**Description:** Skills can access articles via new paths (`~/Development/[source]/raw/*.md`)
**Implementation:** Articles copied to `raw/` directory
**Test:** Read article via new path, verify content matches

### UC-3: Metadata Preservation
**Description:** YAML frontmatter metadata must be identical before/after migration
**Implementation:** Validation before copy, checksums after
**Test:** Parse YAML before/after, assert all fields match

### UC-4: No Data Loss
**Description:** All articles present after migration, no corruption
**Implementation:** Copy (not move), checksum validation
**Test:** Count articles before/after, verify checksums match

### UC-5: Database Indexing
**Description:** All migrated articles indexed in SQLite for fast search
**Implementation:** `knowledge_sync.py` runs after migration
**Test:** Query database, verify row count matches file count

### UC-6: Rollback on Failure
**Description:** Restore original state if migration fails
**Implementation:** Backup before migration, restore from backup
**Test:** Trigger failure, run rollback, verify restoration

### UC-7: Skills Continue Working
**Description:** All skills function identically before/during/after migration
**Implementation:** Backward compatible paths, unchanged metadata
**Test:** Run each skill with test query, compare outputs

---

## Test Plan

### Phase 1: Pre-Migration Validation

#### Test 1.1: Inventory Articles
```bash
# Count articles per source
for source in cherie-hu-blog lenny-newsletter chatprd-blog jesse-cannon-blog indie-trinity; do
    count=$(find ~/Development/$source/articles -name "*.md" | wc -l)
    echo "$source: $count articles"
done

# Expected output:
# cherie-hu-blog: 641 articles
# lenny-newsletter: 284 articles
# chatprd-blog: 119 articles
# jesse-cannon-blog: 973 articles
# indie-trinity: 420 articles
# Total: 2,437 articles
```

**Pass criteria:** All sources found, counts match expected

#### Test 1.2: Validate YAML Frontmatter
```bash
# Check random sample of articles
python3 <<EOF
import yaml
from pathlib import Path

samples = [
    "~/Development/cherie-hu-blog/articles/music-tech-trends-2024-abc123.md",
    "~/Development/lenny-newsletter/articles/product-market-fit-guide-def456.md",
]

for path in samples:
    content = Path(path).expanduser().read_text()
    parts = content.split('---', 2)
    metadata = yaml.safe_load(parts[1])

    # Check required fields
    assert 'title' in metadata
    assert 'author' in metadata
    assert 'source' in metadata
    print(f"✅ {Path(path).name}: Valid YAML")
EOF
```

**Pass criteria:** All samples have valid YAML frontmatter

#### Test 1.3: Test Skills Before Migration
```bash
# Test each skill with known query
echo "Testing ask-cherie..."
# /ask-cherie streaming revenue trends
# Expected: Returns articles about streaming

echo "Testing ask-lenny..."
# /ask-lenny product market fit
# Expected: Returns PMF articles

echo "Testing ask-chatprd..."
# /ask-chatprd AI workflows
# Expected: Returns AI workflow articles

# etc. for all skills
```

**Pass criteria:** All skills return relevant results

---

### Phase 2: Dry-Run Migration

#### Test 2.1: Dry-Run Single Source
```bash
python3 ~/Development/tools/migrate_knowledge_base.py \
    --source cherie-hu-blog \
    --dry-run

# Check log output
cat ~/.claude/logs/migration.log | grep "DRY RUN"
```

**Pass criteria:**
- No errors in log
- Reports what would happen
- No actual changes made

#### Test 2.2: Validate Dry-Run Output
```bash
# Verify no changes made
ls -la ~/Development/cherie-hu-blog/
# Should NOT have raw/ directory yet

# Verify backup not created
ls ~/Backups/knowledge-base/
# Should be empty or have only old backups
```

**Pass criteria:** No changes to filesystem

---

### Phase 3: Live Migration (Test Source)

#### Test 3.1: Migrate Cherie Hu (Test)
```bash
# Backup manually first
tar -czf ~/Backups/manual-backup-cherie-$(date +%Y%m%d).tar.gz \
    ~/Development/cherie-hu-blog

# Run migration
python3 ~/Development/tools/migrate_knowledge_base.py \
    --source cherie-hu-blog \
    --force

# Check exit code
echo $?  # Should be 0
```

**Pass criteria:** Exit code 0, no errors in log

#### Test 3.2: Validate Article Count
```bash
# Count original articles (now symlinks)
articles_count=$(ls ~/Development/cherie-hu-blog/articles/*.md | wc -l)

# Count new raw articles
raw_count=$(ls ~/Development/cherie-hu-blog/raw/*.md | wc -l)

echo "Articles: $articles_count"
echo "Raw: $raw_count"

# Should match
test $articles_count -eq $raw_count && echo "✅ Counts match"
```

**Pass criteria:** Counts match exactly

#### Test 3.3: Validate Symlinks
```bash
# Check symlinks created
test -L ~/Development/cherie-hu-blog/articles/music-tech-trends-2024-abc123.md \
    && echo "✅ Symlink created"

# Check symlink points to raw/
readlink ~/Development/cherie-hu-blog/articles/music-tech-trends-2024-abc123.md
# Expected: ../raw/music-tech-trends-2024-abc123.md
```

**Pass criteria:** All articles/ files are symlinks pointing to ../raw/

#### Test 3.4: Validate YAML Frontmatter Preserved
```bash
python3 <<EOF
import yaml
from pathlib import Path

# Sample article
article = "music-tech-trends-2024-abc123.md"

# Read via old path (symlink)
old_path = Path("~/Development/cherie-hu-blog/articles") / article
old_content = old_path.expanduser().read_text()
old_metadata = yaml.safe_load(old_content.split('---', 2)[1])

# Read via new path (raw file)
new_path = Path("~/Development/cherie-hu-blog/raw") / article
new_content = new_path.expanduser().read_text()
new_metadata = yaml.safe_load(new_content.split('---', 2)[1])

# Assert metadata identical
assert old_metadata == new_metadata
print("✅ Metadata preserved")
EOF
```

**Pass criteria:** Metadata identical via both paths

#### Test 3.5: Validate Checksums
```bash
python3 <<EOF
import hashlib
from pathlib import Path

def checksum(path):
    return hashlib.md5(path.read_bytes()).hexdigest()

# Sample articles
articles = [
    "music-tech-trends-2024-abc123.md",
    "streaming-revenue-analysis-def456.md",
]

for article in articles:
    old_sum = checksum(Path(f"~/Development/cherie-hu-blog/articles/{article}").expanduser())
    new_sum = checksum(Path(f"~/Development/cherie-hu-blog/raw/{article}").expanduser())

    assert old_sum == new_sum
    print(f"✅ {article}: Checksums match")
EOF
```

**Pass criteria:** All checksums match

#### Test 3.6: Validate Database Indexed
```bash
python3 ~/Development/tools/knowledge_db.py stats

# Should show:
# cherie-hu-blog: 641 articles
```

**Pass criteria:** Database contains all migrated articles

---

### Phase 4: Skill Compatibility Testing

#### Test 4.1: Test ask-cherie Skill
```bash
# Query via skill
# /ask-cherie streaming revenue trends

# Expected:
# - Returns relevant articles
# - No errors about missing files
# - Output identical to pre-migration
```

**Pass criteria:** Skill works identically to pre-migration

#### Test 4.2: Test Direct File Access
```python
# Simulate what skills do: Read file directly
from pathlib import Path

# Old path (symlink)
article = Path("~/Development/cherie-hu-blog/articles/music-tech-trends-2024-abc123.md").expanduser()
content = article.read_text()
assert "# " in content  # Has markdown heading
print("✅ Old path readable")

# New path (raw file)
article = Path("~/Development/cherie-hu-blog/raw/music-tech-trends-2024-abc123.md").expanduser()
content = article.read_text()
assert "# " in content
print("✅ New path readable")
```

**Pass criteria:** Both paths readable, content identical

#### Test 4.3: Test Grep Search
```bash
# Skills use Grep to search articles
Grep pattern="streaming" \
     path="~/Development/cherie-hu-blog/articles" \
     output_mode="files_with_matches"

# Should return results (via symlinks)
```

**Pass criteria:** Grep finds articles via symlink paths

---

### Phase 5: Performance Testing

#### Test 5.1: Database Search Speed
```bash
python3 <<EOF
import time
from knowledge_db import KnowledgeDB

db = KnowledgeDB()

# Time search query
start = time.time()
results = db.search("streaming revenue")
elapsed = time.time() - start

print(f"Search returned {len(results)} results in {elapsed:.3f}s")
# Expected: < 0.1s for thousands of articles

db.close()
EOF
```

**Pass criteria:** Search completes in < 100ms

#### Test 5.2: File Access Speed (Symlinks)
```bash
python3 <<EOF
import time
from pathlib import Path

articles_dir = Path("~/Development/cherie-hu-blog/articles").expanduser()
articles = list(articles_dir.glob("*.md"))

# Time reading via symlinks
start = time.time()
for article in articles[:100]:  # Sample 100
    content = article.read_text()
elapsed = time.time() - start

print(f"Read 100 files in {elapsed:.3f}s")
# Expected: < 1s

# Symlinks should have minimal overhead
EOF
```

**Pass criteria:** Symlink access has < 10% overhead vs direct files

---

### Phase 6: Rollback Testing

#### Test 6.1: Simulate Failure and Rollback
```bash
# Manually corrupt raw directory
rm ~/Development/cherie-hu-blog/raw/*.md

# Run rollback
python3 ~/Development/tools/migrate_knowledge_base.py \
    --source cherie-hu-blog \
    --rollback

# Verify restoration
count=$(ls ~/Development/cherie-hu-blog/articles/*.md | wc -l)
echo "Restored articles: $count"
# Expected: 641 (all articles restored)
```

**Pass criteria:** All articles restored, skills work again

---

## Acceptance Criteria

### Migration Successful When:
- ✅ All 2,437+ articles migrated to raw/ directories
- ✅ Symlinks created for backward compatibility
- ✅ All YAML frontmatter validated (no corruption)
- ✅ All checksums match (no data loss)
- ✅ Database indexed (all articles searchable)
- ✅ All skills work identically (no regressions)
- ✅ Backups created (can rollback if needed)
- ✅ Migration log shows 0 errors

### No Disruption If:
- ✅ Skills find articles via old paths (symlinks work)
- ✅ Skills find articles via new paths (raw files exist)
- ✅ Metadata unchanged (knowledge graph intact)
- ✅ Search works (database queries functional)
- ✅ Performance acceptable (< 100ms searches)

---

## Test Execution Log

### Test Run 1 (Dry Run)
**Date:** 2026-02-07
**Source:** cherie-hu-blog
**Mode:** Dry run
**Result:** PASS
**Notes:** No errors, validated 641 articles

### Test Run 2 (Live Migration)
**Date:** TBD
**Source:** cherie-hu-blog
**Mode:** Live
**Result:** PENDING
**Notes:** Awaiting approval

---

## Rollback Procedure

If migration fails:

```bash
# Step 1: Stop all processes
killall python3

# Step 2: Run rollback
python3 ~/Development/tools/migrate_knowledge_base.py \
    --source cherie-hu-blog \
    --rollback

# Step 3: Verify restoration
python3 ~/Development/tools/validate_migration.py \
    --verify-rollback \
    --source cherie-hu-blog

# Step 4: Test skills
# /ask-cherie test query
# Expected: Works as before migration

# Step 5: Investigate failure
cat ~/.claude/logs/migration.log | grep ERROR
```

---

## Security Validation

### Test: Path Traversal Protection
```python
from migrate_knowledge_base import sanitize_filename

# Test malicious inputs
assert sanitize_filename("../../../etc/passwd", "http://test.com") != "../../../etc/passwd"
assert ".." not in sanitize_filename("../evil", "http://test.com")
assert "/" not in sanitize_filename("evil/path", "http://test.com")

print("✅ Path traversal protection working")
```

### Test: Content Validation
```python
from migrate_knowledge_base import validate_content

# Test huge file
huge_content = "x" * 10_000_000
try:
    validate_content(huge_content, "http://test.com")
    assert False, "Should reject huge files"
except ValueError:
    print("✅ Size limit enforced")

# Test binary content
binary_content = b"\x00\x01\x02".decode('utf-8', errors='ignore')
try:
    validate_content(binary_content, "http://test.com")
    assert False, "Should reject binary"
except ValueError:
    print("✅ Binary detection working")
```

---

**Related:** [[SYSTEM-CONSOLIDATION-PLAN]] | [[behavioral-principles]]
