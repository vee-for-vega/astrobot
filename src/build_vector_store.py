"""
AstroBot — build_vector_store.py
=======================================

What this does:
    1. Loads the astronomy_corpus.yml (output of scrape_data.py + clean_corpus.py)
    2. Filters out junk entries (duplicates, very short answers)
    3. Chunks long answers into smaller pieces for better retrieval
    4. Embeds each chunk using a sentence-transformer model
    5. Stores embeddings + metadata in ChromaDB (persistent, on-disk)

Usage:
    python src/build_vector_store.py
    
    This only needs to run once (or whenever you re-scrape new data).
    The vector store persists to disk at data/chroma_db/.
"""

import os
import re
import yaml
import chromadb
from sentence_transformers import SentenceTransformer

# =============================================================================
# CONFIGURATION
# =============================================================================

CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_SCRIPT_DIR)

CORPUS_PATH = os.path.join(PROJECT_ROOT, 'data', 'astronomy_corpus.yml')
CHROMA_DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'chroma_db')

EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
COLLECTION_NAME = 'astronomy_qa'

MAX_CHUNK_CHARS = 800
CHUNK_OVERLAP_SENTENCES = 1


# =============================================================================
# LOAD AND FILTER CORPUS
# =============================================================================

def load_corpus(path: str) -> list[list[str]]:
    """Load Q&A pairs from the YAML corpus."""
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    if not data or 'conversations' not in data:
        print("[ERROR] Invalid YAML structure — expected 'conversations' key")
        return []
    
    return data['conversations']


def filter_corpus(pairs: list[list[str]]) -> list[list[str]]:
    """
    Remove junk entries that would hurt retrieval quality.
    
    Filters:
        - Duplicates (keep first occurrence)
        - Entries with very short answers (< 30 chars = probably garbage)
    
    NOTE: Video link entries from Cool Cosmos are KEPT — the URLs are valid
    and provide useful supplementary content alongside LLM-generated answers.
    """
    seen_questions = set()
    filtered = []
    removed_dupes = 0
    removed_short = 0

    for pair in pairs:
        if len(pair) < 2:
            continue
        
        question, answer = pair[0], pair[1]

        # Filter: duplicates (by question text)
        q_normalized = question.strip().lower()
        if q_normalized in seen_questions:
            removed_dupes += 1
            continue
        seen_questions.add(q_normalized)

        # Filter: very short answers
        if len(answer.strip()) < 30:
            removed_short += 1
            continue

        filtered.append([question, answer])

    print(f"[FILTER] Kept {len(filtered)} pairs")
    print(f"   Removed: {removed_dupes} duplicates, {removed_short} too-short")
    
    return filtered


# =============================================================================
# CHUNKING
# =============================================================================

def split_into_sentences(text: str) -> list[str]:
    """Simple sentence splitter."""
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_qa_pair(question: str, answer: str) -> list[dict]:
    """
    Chunks a single Q&A pair into retrieval-ready documents.
    
    Strategy:
        - Short answers (< MAX_CHUNK_CHARS): keep as one chunk, prepend question
        - Long answers: split into sentence groups with overlap, 
          prepend question to each chunk so retrieval knows what topic it's about
    """
    chunks = []

    if len(answer) <= MAX_CHUNK_CHARS:
        chunks.append({
            'text': f"Q: {question}\nA: {answer}",
            'question': question,
            'answer_full': answer,
            'chunk_index': 0,
        })
        return chunks

    sentences = split_into_sentences(answer)
    
    if len(sentences) <= 2:
        chunks.append({
            'text': f"Q: {question}\nA: {answer}",
            'question': question,
            'answer_full': answer,
            'chunk_index': 0,
        })
        return chunks

    current_group = []
    current_len = 0
    chunk_index = 0

    for i, sentence in enumerate(sentences):
        current_group.append(sentence)
        current_len += len(sentence)

        if current_len >= MAX_CHUNK_CHARS or i == len(sentences) - 1:
            chunk_text = ' '.join(current_group)
            chunks.append({
                'text': f"Q: {question}\nA: {chunk_text}",
                'question': question,
                'answer_full': answer,
                'chunk_index': chunk_index,
            })
            chunk_index += 1

            if CHUNK_OVERLAP_SENTENCES > 0 and i < len(sentences) - 1:
                current_group = current_group[-CHUNK_OVERLAP_SENTENCES:]
                current_len = sum(len(s) for s in current_group)
            else:
                current_group = []
                current_len = 0

    return chunks


def chunk_all_pairs(pairs: list[list[str]]) -> list[dict]:
    """Chunk all Q&A pairs and return flat list of chunk dicts."""
    all_chunks = []
    
    for pair in pairs:
        question, answer = pair[0], pair[1]
        chunks = chunk_qa_pair(question, answer)
        all_chunks.extend(chunks)
    
    single_chunk_count = sum(1 for p in pairs if len(p[1]) <= MAX_CHUNK_CHARS)
    multi_chunk_count = len(pairs) - single_chunk_count
    
    print(f"[CHUNK] {len(pairs)} Q&A pairs → {len(all_chunks)} chunks")
    print(f"   {single_chunk_count} kept as single chunks, {multi_chunk_count} were split")
    
    return all_chunks


# =============================================================================
# EMBEDDING + VECTOR STORE
# =============================================================================

def build_vector_store(chunks: list[dict]):
    """Embeds all chunks and stores them in ChromaDB."""
    print(f"\n[EMBED] Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)

    texts = [chunk['text'] for chunk in chunks]
    print(f"[EMBED] Embedding {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True)

    print(f"[STORE] Writing to ChromaDB at {CHROMA_DB_PATH}")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"[STORE] Deleted existing '{COLLECTION_NAME}' collection")
    except Exception:
        pass  # Collection doesn't exist yet — that's fine on first run

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "AstroBot astronomy Q&A corpus",
            "hnsw:space": "cosine"  # cosine similarity — less sensitive to minor wording differences than L2
        }
    )

    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            'question': chunk['question'],
            'chunk_index': chunk['chunk_index'],
            'char_length': len(chunk['text']),
            'answer_full': chunk['answer_full'],
        }
        for chunk in chunks
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings.tolist(),
        documents=texts,
        metadatas=metadatas,
    )

    print(f"[STORE] Stored {len(ids)} chunks in collection '{COLLECTION_NAME}'")
    print(f"[DONE] Vector store ready at {CHROMA_DB_PATH}")

    print(f"\n--- Corpus Stats ---")
    print(f"Total chunks:     {len(chunks)}")
    avg_len = sum(len(c['text']) for c in chunks) / len(chunks)
    print(f"Avg chunk length: {avg_len:.0f} chars")
    max_len = max(len(c['text']) for c in chunks)
    min_len = min(len(c['text']) for c in chunks)
    print(f"Range:            {min_len} - {max_len} chars")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("  AstroBot — Build Vector Store")
    print("=" * 50)

    print(f"\n[LOAD] Reading corpus from {CORPUS_PATH}")
    raw_pairs = load_corpus(CORPUS_PATH)
    print(f"[LOAD] Found {len(raw_pairs)} raw Q&A pairs")

    if not raw_pairs:
        print("[ERROR] No data found. Run scrape_data.py first.")
        exit(1)

    clean_pairs = filter_corpus(raw_pairs)
    chunks = chunk_all_pairs(clean_pairs)
    build_vector_store(chunks)

    print("\nVector store build complete. You can now run bot_controller.py.")
