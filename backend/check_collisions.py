import chromadb
from collections import defaultdict

db = chromadb.PersistentClient('./data/chroma_db')
col = db.get_collection('documents')

# Get all metadata
r = col.get(include=['metadatas'], limit=10000)

# Group by doc_id, collect unique sources
doc_sources = defaultdict(set)
for m in r['metadatas']:
    doc_id = m.get('doc_id', '')
    source = m.get('source', '')
    if doc_id:
        doc_sources[doc_id].add(source)

# Find doc_ids with multiple different sources (hash collision)
collisions = {k: v for k, v in doc_sources.items() if len(v) > 1}
print(f"Total unique doc_ids: {len(doc_sources)}")
print(f"Hash collisions (doc_id with multiple sources): {len(collisions)}")
for doc_id, sources in list(collisions.items())[:10]:
    print(f"  {doc_id}: {sources}")

# Also check: search result for a sample cross-year doc
# Find doc_ids that appear in more than one year
from collections import defaultdict
doc_dates = defaultdict(set)
for m in r['metadatas']:
    doc_id = m.get('doc_id', '')
    date = m.get('date', '')
    if doc_id and date:
        doc_dates[doc_id].add(date)

multi_year = {k: v for k, v in doc_dates.items() if len(v) > 1}
print(f"\nDoc_ids spanning multiple years (content identical across years): {len(multi_year)}")
for doc_id, dates in list(multi_year.items())[:5]:
    sources = doc_sources[doc_id]
    print(f"  {doc_id}: dates={dates} sources={sources}")
