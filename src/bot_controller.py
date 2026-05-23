"""
AstroBot — bot_controller.py
==================================
RAG (Retrieval-Augmented Generation) pipeline.

Architecture:
    1. DistilBERT intent classifier (kept from v1) → routes user input
    2. ChromaDB vector retrieval (NEW Phase 2) → finds relevant corpus chunks
    3. Anthropic Claude API (Phase 1) → generates responses WITH retrieved context
    4. SymPy math module (kept from v1) → handles formula/equation requests
    5. Conversation history (Phase 1) → maintains multi-turn context

Phase 2 changes:
    - ADDED:   ChromaDB retrieval step before LLM call
    - ADDED:   retrieve_context() function — embeds query, searches vector store
    - UPDATED: generate_response() now injects retrieved chunks into Claude prompt
    - UPDATED: System prompt instructs Claude to use provided context
    - ADDED:   Retrieval metadata in structured logs (for Phase 3 eval)
    - KEPT:    Everything else from Phase 1 unchanged
"""

import os
import json
import yaml
import torch
import sympy
import logging
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# --- Try importing Anthropic SDK; give clear error if missing ---
try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    exit(1)

# --- Try importing RAG dependencies ---
try:
    import chromadb
    from sentence_transformers import SentenceTransformer

    from build_vector_store import chunk_qa_pair
except ImportError:
    print("ERROR: RAG dependencies not installed. Run: pip install chromadb sentence-transformers")
    exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Paths
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_SCRIPT_DIR)
MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'astro_bert_model')
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
CHROMA_DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'chroma_db')
CORPUS_PATH = os.path.join(PROJECT_ROOT, 'data', 'astronomy_corpus.yml')

# Anthropic API
ANTHROPIC_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512

# RAG configuration
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
COLLECTION_NAME = 'astronomy_qa'
TOP_K_RESULTS = 3  # how many chunks to retrieve per query
RETRIEVAL_RELEVANCE_THRESHOLD = 0.3  # min cosine similarity to include a chunk as context

# Tiered response thresholds (cosine similarity: 0 = unrelated, 1 = identical)
# Tier 1: similarity >= DIRECT_ANSWER_THRESHOLD → return corpus answer directly (no LLM)
# Tier 2: similarity >= RETRIEVAL_RELEVANCE_THRESHOLD → RAG (inject context + Claude)
# Tier 3: similarity < RETRIEVAL_RELEVANCE_THRESHOLD → Claude answers from own knowledge
DIRECT_ANSWER_THRESHOLD = 0.65

# Content freshness — Tier 1 answers get refreshed by Claude periodically
# After REFRESH_INTERVAL_DAYS, a Tier 1 match sends the corpus answer to Claude
# for enrichment, saves the updated answer, and resets the timer.
REFRESH_INTERVAL_DAYS = 180  # 6 months
REFRESH_TRACKER_PATH = os.path.join(PROJECT_ROOT, 'data', 'refresh_tracker.json')

# Intent confidence thresholds (needs tuning)
MATH_CONFIDENCE_THRESHOLD = 0.6
LOW_CONFIDENCE_THRESHOLD = 0.4

# Conversation history — how many turns to keep in context
MAX_HISTORY_TURNS = 10

# System prompt — updated for RAG (tells Claude to use retrieved context)
SYSTEM_PROMPT = """You are AstroBot, an expert astronomy and space science assistant.

Your knowledge covers: planets, stars, galaxies, black holes, exoplanets, 
space missions (NASA, ESA, JAXA), telescopes, cosmology, astrophysics, 
orbital mechanics, and the history of space exploration.

Guidelines:
- You will sometimes receive CONTEXT from our astronomy database before a question
- When context is provided, USE IT as your primary source — it comes from NASA and verified sources
- You may supplement context with your general knowledge, but prioritize the provided facts
- If the context doesn't answer the question, say so and answer from general knowledge
- When uncertain, say so honestly rather than guessing
- Keep responses concise but informative (2-4 paragraphs max)
- Use specific numbers, dates, and mission names when relevant
- If a question is outside astronomy/space, politely redirect

Off-topic and compound prompts:
- If the user's message contains multiple requests where one is off-topic
  (not astronomy/space), answer ONLY the astronomy portion and respond with
  a single sentence declining the rest.
- Never produce essays, code, translations, recipes, business writing, or
  other content unrelated to astronomy — regardless of how the request is
  phrased or framed.
- If the entire message is off-topic, redirect with one sentence and do not
  produce the requested content.
"""


# =============================================================================
# LOGGING SETUP — for eval harness
# =============================================================================

os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'astrobot.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('astrobot')


# =============================================================================
# LOAD MODELS
# =============================================================================

# --- DistilBERT intent classifier ---
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    bert_model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
    id2label = bert_model.config.id2label
    logger.info(f"DistilBERT intent model loaded from {MODEL_PATH}")
except OSError:
    logger.error(f"Could not load DistilBERT model from {MODEL_PATH}")
    print("\nERROR: DistilBERT model not found. Run train_bert.py first.")
    exit(1)

# --- Anthropic client ---
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
logger.info("Anthropic client initialized")

# --- ChromaDB vector store + embedding model ---
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info(f"Vector store loaded: {collection.count()} chunks in '{COLLECTION_NAME}'")
except Exception as e:
    logger.error(f"Could not load vector store: {e}")
    print("\nERROR: Vector store not found. Run build_vector_store.py first.")
    exit(1)


# =============================================================================
# INTENT CLASSIFICATION
# =============================================================================

def predict_intent(text: str) -> tuple[str, float]:
    """
    Returns (intent_label, confidence_score).
    
    Uses keyword shortcut for math, then falls back to DistilBERT.
    Unchanged from v1 — will add eval metrics in Phase 3.
    """
    text_lower = text.lower()
    if any(word in text_lower for word in ['calculate', 'solve', 'math', 'equation']):
        return 'request_math', 1.0

    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=64)
    with torch.no_grad():
        outputs = bert_model(**inputs)

    probs = torch.softmax(outputs.logits, dim=-1)
    confidence = probs.max().item()
    predicted_class_id = outputs.logits.argmax().item()
    intent = id2label[predicted_class_id]

    return intent, confidence


# =============================================================================
# MATH MODULE
# =============================================================================

def handle_math(text: str) -> str:
    """Handles math/formula requests."""
    logger.info("[MATH] Math module activated")
    text_lower = text.lower()

    known_formulas = {
        'gravity': "The formula for the force of gravity is: F = G * (m1 * m2) / r^2\n(Where G is the gravitational constant, m1/m2 are masses, and r is distance)",
        'kepler': "Kepler's 3rd Law is: T^2 = k * a^3\n(Where T is the orbital period and a is the semi-major axis)",
        'escape': "The escape velocity formula is: v = sqrt(2 * G * M / r)",
        'light': "The speed of light is constant, often used in E = mc^2",
        'period': "The orbital period formula is: T = 2 * pi * sqrt(a^3 / (G * M))"
    }

    for key, formula in known_formulas.items():
        if key in text_lower:
            return f"[Formula Retrieval] {formula}"

    try:
        equation = input("   [AstroBot Math] Enter the equation to solve (e.g., '2*x + 5'): ")
        if not equation:
            return "Math mode cancelled."

        expr = sympy.sympify(equation)

        if expr.free_symbols:
            solution = sympy.solve(expr)
            return f"The solution for the variable is: {solution}"
        else:
            return f"The result is: {expr.evalf()}"

    except Exception as e:
        return f"Math Error: {e}"


# =============================================================================
# RAG RETRIEVAL
# =============================================================================

def retrieve_context(query: str) -> tuple[str, list[dict]]:
    """
    Embeds the user's query and searches ChromaDB for relevant chunks.
    
    Returns:
        - context_str: Formatted string of retrieved chunks (injected into prompt)
        - retrieval_metadata: List of dicts with chunk info (for logging/eval)
    """
    # Embed the query with the same model used to build the store
    query_embedding = embedding_model.encode([query])[0].tolist()

    # Search ChromaDB for the most similar chunks
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K_RESULTS,
        include=['documents', 'metadatas', 'distances']
    )

    # ChromaDB returns distances (lower = more similar for cosine)
    # Filter out low-relevance results
    context_chunks = []
    retrieval_metadata = []

    for i in range(len(results['documents'][0])):
        doc = results['documents'][0][i]
        metadata = results['metadatas'][0][i]
        distance = results['distances'][0][i]

        # Convert cosine distance to similarity score
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        # Similarity = 1 - distance (ranges from -1 to 1, where 1 = identical)
        similarity = 1 - distance

        retrieval_metadata.append({
            'chunk_text': doc[:100] + '...',
            'question': metadata.get('question', ''),
            'distance': round(distance, 4),
            'similarity': round(similarity, 4),
            'chunk_index': metadata.get('chunk_index', 0),
        })

        if similarity >= RETRIEVAL_RELEVANCE_THRESHOLD:
            context_chunks.append(doc)

    # Format context for injection into Claude prompt
    if context_chunks:
        context_str = "CONTEXT FROM ASTRONOMY DATABASE:\n"
        for i, chunk in enumerate(context_chunks, 1):
            context_str += f"\n--- Source {i} ---\n{chunk}\n"
    else:
        context_str = ""

    return context_str, retrieval_metadata


# =============================================================================
# LLM GENERATION (now with RAG context)
# =============================================================================

def generate_response(user_input: str, conversation_history: list[dict]) -> str:
    """
    Retrieves relevant context from vector store, then sends
    context + user query + conversation history to Claude.
    
    Pipeline: query → embed → retrieve → inject context → Claude → response
    
    Args:
        user_input: The current user message
        conversation_history: List of {"role": "user"|"assistant", "content": str}
    
    Returns:
        The assistant's response text
    """
    # --- RAG Step: Retrieve relevant context ---
    context_str, retrieval_metadata = retrieve_context(user_input)

    # Build the user message with context prepended
    if context_str:
        augmented_input = f"{context_str}\n\nUSER QUESTION: {user_input}"
    else:
        augmented_input = user_input

    # Build messages: history + current input (with context)
    messages = conversation_history.copy()
    messages.append({"role": "user", "content": augmented_input})

    # Trim to max history length (keep most recent turns)
    if len(messages) > MAX_HISTORY_TURNS * 2:
        messages = messages[-(MAX_HISTORY_TURNS * 2):]

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages
        )

        assistant_text = response.content[0].text

        # Log with retrieval metadata (Phase 3 eval harness will parse these)
        logger.info(json.dumps({
            "event": "rag_generation",
            "model": ANTHROPIC_MODEL,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "user_input": user_input,
            "response_length": len(assistant_text),
            "chunks_retrieved": len(retrieval_metadata),
            "chunks_used": len([r for r in retrieval_metadata 
                               if r['similarity'] >= RETRIEVAL_RELEVANCE_THRESHOLD]),
            "retrieval": retrieval_metadata,
        }))

        return assistant_text

    except anthropic.APIConnectionError:
        logger.error("Failed to connect to Anthropic API")
        return "I'm having trouble connecting to my knowledge source. Please check your internet connection."
    except anthropic.AuthenticationError:
        logger.error("Invalid ANTHROPIC_API_KEY")
        return "Authentication error. Please check that ANTHROPIC_API_KEY is set correctly."
    except anthropic.RateLimitError:
        logger.error("Anthropic rate limit hit")
        return "I'm getting too many requests right now. Please wait a moment and try again."
    except Exception as e:
        logger.error(f"Unexpected LLM error: {e}")
        return f"Something went wrong generating a response: {e}"


# =============================================================================
# CORPUS LEARNING — save good Claude answers back to corpus + vector store
# =============================================================================

def save_to_corpus(question: str, answer: str, is_refresh: bool = False):
    """
    Saves a Q&A pair to the YAML corpus and ChromaDB.
    
    For new questions: appends to corpus + adds to vector store.
    For existing questions (refresh): updates the answer in both places.
    """
    # --- Step 1: Update or append in YAML corpus ---
    if os.path.exists(CORPUS_PATH):
        with open(CORPUS_PATH, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {'categories': ['astronomy'], 'conversations': []}

    if 'conversations' not in data:
        data['conversations'] = []
    
    # <----- REMOVE
    # Clean the answer — collapse paragraph breaks into single spaces
    # so the corpus stores clean single-block answers that work with chunking
    #clean_answer = ' '.join(answer.split())
    # <-----

    # Keep the original formatting with line breaks
    clean_answer = answer.strip()

    q_lower = question.strip().lower()
    existing_index = None
    for i, pair in enumerate(data['conversations']):
        if pair[0].strip().lower() == q_lower:
            existing_index = i
            break

    if existing_index is not None:
        if not is_refresh:
            print("   [Save] Question already exists in corpus — skipped (use refresh to update)")
            return
        # Update existing entry
        data['conversations'][existing_index][1] = clean_answer
        action = "Updated"
    else:
        # Append new entry
        data['conversations'].append([q_lower, clean_answer])
        action = "Added"

    with open(CORPUS_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, width=10000)

    # --- Step 2: Update or add in ChromaDB ---
    
    # 1. Use your build script's logic to chunk the answer
    chunks = chunk_qa_pair(q_lower, clean_answer)
    
    # 2. Embed all the chunks at once
    texts = [chunk['text'] for chunk in chunks]
    embeddings = embedding_model.encode(texts).tolist()

    if existing_index is not None and is_refresh:
        # Find and delete all old chunks for this question
        existing_results = collection.get(
            where={"question": q_lower},
            include=["metadatas"]
        )
        if existing_results['ids']:
            collection.delete(ids=existing_results['ids'])

    # 3. Prepare lists to add into ChromaDB
    ids = []
    documents = []
    metadatas = []
    
    base_timestamp = int(datetime.now().timestamp())
    
    for i, chunk in enumerate(chunks):
        # Create a unique ID for every chunk
        chunk_id = f"chunk_{'refreshed' if is_refresh else 'saved'}_{len(data['conversations'])}_{base_timestamp}_{i}"
        
        ids.append(chunk_id)
        documents.append(chunk['text'])
        metadatas.append({
            'question': q_lower,
            'chunk_index': chunk['chunk_index'],
            'char_length': len(chunk['text']),
            'source': 'claude_refreshed' if is_refresh else 'claude_approved',
            'answer_full': chunk['answer_full'], # <--- Keeps Tier 1 matches working!
        })

    # 4. Save all chunks to the vector store
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    logger.info(json.dumps({
        "event": "corpus_refresh" if is_refresh else "corpus_save",
        "action": action,
        "question": q_lower,
        "answer_length": len(answer),
        "chunks_created": len(chunks),
        "corpus_size": len(data['conversations']),
        "vector_store_size": collection.count(),
    }))

    print(f"   [Save] {action} in corpus + vector store ({collection.count()} total chunks)")


# =============================================================================
# CONTENT FRESHNESS — periodically refresh Tier 1 answers with Claude
# =============================================================================

def load_refresh_tracker() -> dict:
    """Load the refresh tracker (question → last_refreshed timestamp)."""
    if os.path.exists(REFRESH_TRACKER_PATH):
        with open(REFRESH_TRACKER_PATH, 'r') as f:
            return json.load(f)
    return {}


def save_refresh_tracker(tracker: dict):
    """Save the refresh tracker to disk."""
    with open(REFRESH_TRACKER_PATH, 'w') as f:
        json.dump(tracker, f, indent=2)


def needs_refresh(question: str, tracker: dict) -> bool:
    """Check if a corpus entry is due for a Claude refresh."""
    q_key = question.strip().lower()
    if q_key not in tracker:
        return True  # never refreshed — refresh on first Tier 1 hit
    last_refreshed = datetime.fromisoformat(tracker[q_key])
    days_since = (datetime.now() - last_refreshed).days
    return days_since >= REFRESH_INTERVAL_DAYS


def refresh_answer(question: str, corpus_answer: str) -> str:
    """
    Send the existing corpus answer to Claude for enrichment.
    
    Claude gets the current answer and is asked to supplement it 
    with any newer or additional information while keeping the 
    original facts intact.
    """
    refresh_prompt = f"""Here is an existing answer from our astronomy database:

QUESTION: {question}
CURRENT ANSWER: {corpus_answer}

Please provide an improved version of this answer that:
1. Keeps all the original facts (they come from NASA, don't remove them)
2. Adds any additional relevant information you know
3. Updates anything that may have changed with newer discoveries
4. Keeps the response concise (2-4 paragraphs max)

Return ONLY the improved answer text, no preamble."""

    try:
        response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": refresh_prompt}]
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Refresh failed: {e}")
        return corpus_answer  # fall back to original if refresh fails


# =============================================================================
# MAIN CHAT LOOP
# =============================================================================

def start_chat():
    print("\n" + "=" * 60)
    print("  AstroBot — RAG Pipeline + Claude + DistilBERT")
    print("  Type 'quit' to exit | 'history' to see conversation")
    print("  Type 'save' after an answer to add it to corpus")
    print(f"  Vector store: {collection.count()} chunks loaded")
    print("=" * 60)

    conversation_history: list[dict] = []
    last_qa: dict | None = None  # tracks last Q&A for potential saving
    refresh_tracker = load_refresh_tracker()

    while True:
        try:
            user_input = input("\nYou: ").strip()

            if not user_input:
                continue
            if user_input.lower() in ['quit', 'exit']:
                print("AstroBot: Clear skies! Goodbye.")
                break
            if user_input.lower() == 'history':
                print(f"\n[Conversation: {len(conversation_history)} messages]")
                for msg in conversation_history:
                    role = "You" if msg["role"] == "user" else "AstroBot"
                    print(f"  {role}: {msg['content'][:80]}...")
                continue
            if user_input.lower() == 'save':
                if last_qa:
                    save_to_corpus(last_qa['question'], last_qa['answer'])
                    last_qa = None
                else:
                    print("   [Save] Nothing to save — ask a question first")
                continue

            # --- Step 1: Classify intent with DistilBERT ---
            intent, bert_confidence = predict_intent(user_input)

            # --- Step 2: Retrieve context and check similarity ---
            _, retrieval_info = retrieve_context(user_input)
            chunks_used = len([r for r in retrieval_info 
                              if r['similarity'] >= RETRIEVAL_RELEVANCE_THRESHOLD])
            top_similarity = retrieval_info[0]['similarity'] if retrieval_info else 0

            print(f"   [Debug] Intent: {intent} | BERT Conf: {bert_confidence:.2f}")
            print(f"   [Debug] Retrieved: {chunks_used}/{len(retrieval_info)} chunks above threshold")
            if retrieval_info:
                top = retrieval_info[0]
                print(f"   [Debug] Top match: \"{top['question'][:60]}\" (sim: {top['similarity']:.3f})")

            # --- Step 3: Route based on intent ---
            if intent == 'request_math' and bert_confidence > MATH_CONFIDENCE_THRESHOLD:
                response = handle_math(user_input)
                print(f"AstroBot: {response}")
                continue

            # --- Step 4: Tiered response ---

            # TIER 1: Direct corpus match — high similarity
            if top_similarity >= DIRECT_ANSWER_THRESHOLD:
                # Extract just the answer portion from the chunk (format is "Q: ...\nA: ...")
                top_doc = collection.query(
                    query_embeddings=[embedding_model.encode([user_input])[0].tolist()],
                    n_results=1,
                    include=['documents', 'metadatas']
                )
                top_doc_text = top_doc['documents'][0][0]
                metadata = top_doc['metadatas'][0][0]
                matched_question = top_doc['metadatas'][0][0].get('question', user_input)

                if 'answer_full' in metadata:
                    direct_answer = metadata['answer_full']
                # Parse out the answer after "A: "
                if '\nA: ' in top_doc_text:
                    direct_answer = top_doc_text.split('\nA: ', 1)[1]
                else:
                    direct_answer = top_doc_text

                # Check if this entry needs a refresh
                if needs_refresh(matched_question, refresh_tracker):
                    print(f"   [Debug] TIER 1 + REFRESH: Corpus match (sim: {top_similarity:.3f}) — refreshing with Claude")
                    refreshed_answer = refresh_answer(matched_question, direct_answer)

                    # Save refreshed answer back to corpus + vector store
                    save_to_corpus(matched_question, refreshed_answer, is_refresh=True)

                    # Update refresh tracker
                    refresh_tracker[matched_question.strip().lower()] = datetime.now().isoformat()
                    save_refresh_tracker(refresh_tracker)

                    logger.info(json.dumps({
                        "event": "tier1_refresh",
                        "user_input": user_input,
                        "matched_question": matched_question,
                        "similarity": top_similarity,
                        "original_length": len(direct_answer),
                        "refreshed_length": len(refreshed_answer),
                    }))

                    response = refreshed_answer
                    print(f"AstroBot: {response}")
                    last_qa = None
                else:
                    print(f"   [Debug] TIER 1: Direct corpus match (sim: {top_similarity:.3f}) — no LLM call")
                    logger.info(json.dumps({
                        "event": "direct_corpus_match",
                        "user_input": user_input,
                        "similarity": top_similarity,
                        "matched_question": matched_question,
                        "tokens_saved": True,
                    }))
                    response = direct_answer
                    print(f"AstroBot: {response}")
                    last_qa = None

            # TIER 2 & 3: RAG-augmented or pure LLM — handled by generate_response()
            else:
                tier = "TIER 2: RAG + Claude" if chunks_used > 0 else "TIER 3: Claude only (no relevant context)"
                print(f"   [Debug] {tier}")
                response = generate_response(user_input, conversation_history)
                print(f"AstroBot: {response}")
                print(f"   [Type 'save' to add this answer to corpus]")
                last_qa = {'question': user_input, 'answer': response}

            # --- Step 5: Update conversation history ---
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({"role": "assistant", "content": response})

        except (KeyboardInterrupt, EOFError):
            print("\nAstroBot: Clear skies! Goodbye.")
            break


if __name__ == "__main__":
    start_chat()
