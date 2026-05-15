"""
AstroBot — run_evals.py
==============================
Evaluation harness.

Measures three dimensions of system quality:
    1. RETRIEVAL QUALITY — Hit Rate, MRR
    2. GENERATION FAITHFULNESS — RAG vs No-RAG with LLM-as-judge
    3. INTENT CLASSIFICATION — Precision, Recall, F1

Usage:
    python src/run_evals.py # runs all
    python src/run_evals.py --eval retrieval
    python src/run_evals.py --eval faithfulness
    python src/run_evals.py --eval intent
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime
from collections import defaultdict

CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_SCRIPT_DIR)
sys.path.insert(0, CURRENT_SCRIPT_DIR)

EVAL_DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'eval_questions.json')
CHROMA_DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'chroma_db')
MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'astro_bert_model')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'logs', 'evals')
RESULTS_PATH = None  # set dynamically at runtime with timestamp

EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
COLLECTION_NAME = 'astronomy_qa'
TOP_K_RESULTS = 3
ANTHROPIC_MODEL = "claude-sonnet-4-6"

# Cosine similarity threshold for the semantic-match fallback in retrieval eval.
# 0.75 keeps paraphrases (e.g. "how hot is mercury?" vs "what is the temperature on
# mercury?") as hits while still rejecting topically-related-but-wrong matches.
SEMANTIC_MATCH_THRESHOLD = 0.75

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
"""

SYSTEM_PROMPT_NO_RAG = """You are AstroBot, an expert astronomy and space science assistant.

Guidelines:
- Give accurate, scientifically grounded answers
- When uncertain, say so honestly rather than guessing
- Keep responses concise but informative (2-4 paragraphs max)
- Use specific numbers, dates, and mission names when relevant
- If a question is outside astronomy/space, politely redirect
"""


def load_dependencies():
    import torch
    import anthropic
    import chromadb
    from sentence_transformers import SentenceTransformer
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    components = {}
    print("[INIT] Loading embedding model.")
    components['embedding_model'] = SentenceTransformer(EMBEDDING_MODEL)
    print("[INIT] Loading ChromaDB.")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    components['collection'] = chroma_client.get_collection(name=COLLECTION_NAME)
    print(f"   {components['collection'].count()} chunks loaded")
    components['llm_client'] = anthropic.Anthropic()
    print("[INIT] Loading DistilBERT.")
    components['tokenizer'] = AutoTokenizer.from_pretrained(MODEL_PATH)
    components['bert_model'] = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
    components['id2label'] = components['bert_model'].config.id2label
    with open(EVAL_DATA_PATH, 'r') as f:
        components['eval_data'] = json.load(f)
    print("[INIT] All components loaded.\n")
    return components


def eval_retrieval(components: dict) -> dict:
    from sentence_transformers import util as st_util

    print("=" * 60)
    print("  EVAL 1: RETRIEVAL QUALITY")
    print("=" * 60)

    eval_questions = components['eval_data']['retrieval_eval']
    embedding_model = components['embedding_model']
    collection = components['collection']

    hits = 0
    semantic_only_hits = 0
    reciprocal_ranks = []
    results_detail = []

    for item in eval_questions:
        query = item['query']
        expected = item['expected_source'].strip().lower()

        query_embedding = embedding_model.encode([query])[0].tolist()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=TOP_K_RESULTS,
            include=['documents', 'metadatas', 'distances']
        )

        retrieved_qs = [
            results['metadatas'][0][i].get('question', '').strip().lower()
            for i in range(len(results['metadatas'][0]))
        ]
        retrieved_distances = [results['distances'][0][i] for i in range(len(retrieved_qs))]

        # Pass 1: cheap substring check
        found_rank = None
        match_type = None
        match_sim = None
        for i, rq in enumerate(retrieved_qs):
            if expected in rq or rq in expected:
                found_rank = i + 1
                match_type = 'substring'
                break

        # Pass 2: semantic fallback. The substring matcher misses paraphrases
        # (e.g. expected "what is the temperature on mercury?" vs retrieved
        # "how hot is mercury?"). Embed expected + each retrieved question and
        # accept the first one above SEMANTIC_MATCH_THRESHOLD.
        sims = [None] * len(retrieved_qs)
        if found_rank is None and retrieved_qs:
            expected_emb = embedding_model.encode([expected], convert_to_tensor=True)
            retrieved_embs = embedding_model.encode(retrieved_qs, convert_to_tensor=True)
            sim_row = st_util.cos_sim(expected_emb, retrieved_embs)[0]
            sims = [float(s) for s in sim_row]
            for i, sim in enumerate(sims):
                if sim >= SEMANTIC_MATCH_THRESHOLD:
                    found_rank = i + 1
                    match_type = 'semantic'
                    match_sim = round(sim, 4)
                    semantic_only_hits += 1
                    break

        retrieved_questions = [
            {
                'question': retrieved_qs[i],
                'distance': round(retrieved_distances[i], 4),
                'similarity_to_expected': round(sims[i], 4) if sims[i] is not None else None,
                'rank': i + 1,
            }
            for i in range(len(retrieved_qs))
        ]

        hit = found_rank is not None
        if hit:
            hits += 1
            reciprocal_ranks.append(1.0 / found_rank)
        else:
            reciprocal_ranks.append(0.0)

        if hit and match_type == 'semantic':
            status = f"HIT (rank {found_rank}, semantic sim={match_sim})"
        elif hit:
            status = f"HIT (rank {found_rank})"
        else:
            status = "MISS"
        print(f"  [{status}] \"{query[:50]}\"")
        if not hit:
            top_sim = sims[0] if sims and sims[0] is not None else 0.0
            print(f"          Expected: \"{expected[:50]}\"")
            print(f"          Got:      \"{retrieved_questions[0]['question'][:50]}\" (sim={top_sim:.3f})")

        results_detail.append({
            'query': query, 'expected_source': expected,
            'hit': hit, 'found_rank': found_rank,
            'match_type': match_type, 'match_similarity': match_sim,
            'retrieved': retrieved_questions,
        })

    hit_rate = hits / len(eval_questions)
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
    substring_hits = hits - semantic_only_hits

    print(f"\n  --- Retrieval Results ---")
    print(f"  Hit Rate @ {TOP_K_RESULTS}: {hit_rate:.1%} ({hits}/{len(eval_questions)})")
    print(f"     substring: {substring_hits}   semantic (sim >= {SEMANTIC_MATCH_THRESHOLD}): {semantic_only_hits}")
    print(f"  MRR:                        {mrr:.3f}")
    print()

    return {
        'hit_rate': round(hit_rate, 4), 'mrr': round(mrr, 4),
        'total_queries': len(eval_questions), 'hits': hits,
        'substring_hits': substring_hits, 'semantic_hits': semantic_only_hits,
        'semantic_threshold': SEMANTIC_MATCH_THRESHOLD,
        'details': results_detail,
    }


JUDGE_PROMPT = """You are an evaluation judge. Score the following AI-generated answer on two dimensions.

CONTEXT (from astronomy database):
{context}

QUESTION: {question}

ANSWER: {answer}

Score each dimension from 1-5:

FAITHFULNESS: Is the answer grounded in the provided context? 
  1 = contradicts context, 2 = mostly ignores context, 3 = partially uses context, 
  4 = mostly grounded in context, 5 = fully grounded in context

RELEVANCE: Does the answer actually address the question?
  1 = completely off-topic, 2 = barely relevant, 3 = somewhat relevant, 
  4 = mostly relevant, 5 = directly and fully answers the question

Respond in ONLY this exact JSON format, nothing else:
{{"faithfulness": <score>, "relevance": <score>, "reasoning": "<one sentence>"}}"""

JUDGE_PROMPT_NO_RAG = """You are an evaluation judge. Score the following AI-generated answer on two dimensions.

QUESTION: {question}

ANSWER: {answer}

Score each dimension from 1-5:

ACCURACY: Is the answer scientifically accurate?
  1 = completely wrong, 2 = mostly wrong, 3 = partially correct, 
  4 = mostly correct, 5 = fully accurate

RELEVANCE: Does the answer actually address the question?
  1 = completely off-topic, 2 = barely relevant, 3 = somewhat relevant, 
  4 = mostly relevant, 5 = directly and fully answers the question

Respond in ONLY this exact JSON format, nothing else:
{{"accuracy": <score>, "relevance": <score>, "reasoning": "<one sentence>"}}"""


def generate_with_rag(query, components):
    embedding_model = components['embedding_model']
    collection = components['collection']
    client = components['llm_client']

    query_embedding = embedding_model.encode([query])[0].tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=TOP_K_RESULTS, include=['documents'])

    context_str = "CONTEXT FROM ASTRONOMY DATABASE:\n"
    for i, doc in enumerate(results['documents'][0], 1):
        context_str += f"\n--- Source {i} ---\n{doc}\n"

    augmented_input = f"{context_str}\n\nUSER QUESTION: {query}"
    response = client.messages.create(
        model=ANTHROPIC_MODEL, max_tokens=512, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": augmented_input}]
    )
    return response.content[0].text, context_str


def generate_without_rag(query, components):
    client = components['llm_client']
    response = client.messages.create(
        model=ANTHROPIC_MODEL, max_tokens=512, system=SYSTEM_PROMPT_NO_RAG,
        messages=[{"role": "user", "content": query}]
    )
    return response.content[0].text


def judge_response(prompt, components):
    client = components['llm_client']
    response = client.messages.create(
        model=ANTHROPIC_MODEL, max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text.strip().replace('```json', '').replace('```', '').strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "Failed to parse judge response", "raw": text}


def eval_faithfulness(components: dict) -> dict:
    print("=" * 60)
    print("  EVAL 2: GENERATION FAITHFULNESS (RAG vs No-RAG)")
    print("=" * 60)
    print("  This eval calls the API multiple times per question.")
    print("  It may take a few minutes.\n")

    eval_questions = components['eval_data']['faithfulness_eval']
    results_detail = []
    rag_faith, rag_rel, no_rag_acc, no_rag_rel = [], [], [], []

    for i, item in enumerate(eval_questions):
        query = item['query']
        print(f"  [{i+1}/{len(eval_questions)}] \"{query}\"")

        rag_answer, context_used = generate_with_rag(query, components)
        time.sleep(0.5)
        no_rag_answer = generate_without_rag(query, components)
        time.sleep(0.5)

        rag_scores = judge_response(
            JUDGE_PROMPT.format(context=context_used, question=query, answer=rag_answer), components)
        time.sleep(0.5)
        no_rag_scores = judge_response(
            JUDGE_PROMPT_NO_RAG.format(question=query, answer=no_rag_answer), components)
        time.sleep(0.5)

        if 'faithfulness' in rag_scores:
            rag_faith.append(rag_scores['faithfulness'])
            rag_rel.append(rag_scores['relevance'])
        if 'accuracy' in no_rag_scores:
            no_rag_acc.append(no_rag_scores['accuracy'])
            no_rag_rel.append(no_rag_scores['relevance'])

        print(f"     RAG:    faith={rag_scores.get('faithfulness', '?')}/5  rel={rag_scores.get('relevance', '?')}/5")
        print(f"     No-RAG: acc={no_rag_scores.get('accuracy', '?')}/5    rel={no_rag_scores.get('relevance', '?')}/5")

        results_detail.append({
            'query': query, 'rag_answer': rag_answer[:200] + '...', 'no_rag_answer': no_rag_answer[:200] + '...',
            'rag_scores': rag_scores, 'no_rag_scores': no_rag_scores,
        })

    avg = lambda lst: sum(lst) / len(lst) if lst else 0
    print(f"\n  --- Faithfulness Results ---")
    print(f"  {'Metric':<25} {'RAG':>8} {'No-RAG':>8}")
    print(f"  {'-'*42}")
    print(f"  {'Faithfulness/Accuracy':<25} {avg(rag_faith):>7.2f} {avg(no_rag_acc):>7.2f}")
    print(f"  {'Relevance':<25} {avg(rag_rel):>7.2f} {avg(no_rag_rel):>7.2f}")
    print()

    return {
        'rag': {'avg_faithfulness': round(avg(rag_faith), 3), 'avg_relevance': round(avg(rag_rel), 3)},
        'no_rag': {'avg_accuracy': round(avg(no_rag_acc), 3), 'avg_relevance': round(avg(no_rag_rel), 3)},
        'total_questions': len(eval_questions), 'details': results_detail,
    }


def eval_intent(components: dict) -> dict:
    import torch

    print("=" * 60)
    print("  EVAL 3: INTENT CLASSIFICATION")
    print("=" * 60)

    eval_questions = components['eval_data']['intent_eval']
    tokenizer = components['tokenizer']
    bert_model = components['bert_model']
    id2label = components['id2label']

    predictions, actuals, results_detail = [], [], []

    for item in eval_questions:
        query = item['query']
        expected = item['expected_intent']
        text_lower = query.lower()

        if any(word in text_lower for word in ['calculate', 'solve', 'math', 'equation']):
            predicted, confidence = 'request_math', 1.0
        else:
            inputs = tokenizer(query, return_tensors="pt", truncation=True, padding=True, max_length=64)
            with torch.no_grad():
                outputs = bert_model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
            confidence = probs.max().item()
            predicted = id2label[outputs.logits.argmax().item()]

        correct = predicted == expected
        status = "OK" if correct else "MISS"
        print(f"  [{status}] \"{query[:40]}\"  expected={expected}  got={predicted}  conf={confidence:.2f}")

        predictions.append(predicted)
        actuals.append(expected)
        results_detail.append({
            'query': query, 'expected': expected, 'predicted': predicted,
            'confidence': round(confidence, 4), 'correct': correct
        })

    all_labels = sorted(set(actuals + predictions))
    per_class = {}
    for label in all_labels:
        tp = sum(1 for a, p in zip(actuals, predictions) if a == label and p == label)
        fp = sum(1 for a, p in zip(actuals, predictions) if a != label and p == label)
        fn = sum(1 for a, p in zip(actuals, predictions) if a == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        per_class[label] = {'precision': round(precision, 3), 'recall': round(recall, 3),
                            'f1': round(f1, 3), 'support': sum(1 for a in actuals if a == label)}

    accuracy = sum(1 for a, p in zip(actuals, predictions) if a == p) / len(actuals)
    macro_f1 = sum(c['f1'] for c in per_class.values()) / len(per_class)

    print(f"\n  --- Intent Classification Results ---")
    print(f"  {'Intent':<25} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Support':>8}")
    print(f"  {'-'*52}")
    for label, metrics in sorted(per_class.items()):
        print(f"  {label:<25} {metrics['precision']:>6.3f} {metrics['recall']:>6.3f} {metrics['f1']:>6.3f} {metrics['support']:>8}")
    print(f"  {'-'*52}")
    print(f"  {'Overall Accuracy':<25} {accuracy:>6.1%}")
    print(f"  {'Macro F1':<25} {macro_f1:>6.3f}")
    print()

    return {
        'accuracy': round(accuracy, 4), 'macro_f1': round(macro_f1, 4),
        'per_class': per_class, 'total_samples': len(eval_questions), 'details': results_detail
    }


def main():
    parser = argparse.ArgumentParser(description='AstroBot Evaluation Harness')
    parser.add_argument('--eval', choices=['retrieval', 'faithfulness', 'intent', 'all'],
                        default='all', help='Which eval to run (default: all)')
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  AstroBot — Evaluation Harness")
    print("=" * 60 + "\n")

    components = load_dependencies()
    results = {'timestamp': datetime.now().isoformat(), 'model': ANTHROPIC_MODEL, 'top_k': TOP_K_RESULTS}

    if args.eval in ['retrieval', 'all']:
        results['retrieval'] = eval_retrieval(components)
    if args.eval in ['intent', 'all']:
        results['intent'] = eval_intent(components)
    if args.eval in ['faithfulness', 'all']:
        results['faithfulness'] = eval_faithfulness(components)

    # Generate timestamped results file
    timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    RESULTS_PATH = os.path.join(RESULTS_DIR, f"eval_{args.eval}_{timestamp_str}.json")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(RESULTS_PATH, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"[SAVED] Full results written to {RESULTS_PATH}")

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    if 'retrieval' in results:
        r = results['retrieval']
        print(f"  Retrieval:     Hit Rate={r['hit_rate']:.1%}  MRR={r['mrr']:.3f}")
    if 'intent' in results:
        i = results['intent']
        print(f"  Intent:        Accuracy={i['accuracy']:.1%}  Macro-F1={i['macro_f1']:.3f}")
    if 'faithfulness' in results:
        f_res = results['faithfulness']
        print(f"  RAG Gen:       Faithfulness={f_res['rag']['avg_faithfulness']:.2f}/5  Relevance={f_res['rag']['avg_relevance']:.2f}/5")
        print(f"  No-RAG Gen:    Accuracy={f_res['no_rag']['avg_accuracy']:.2f}/5      Relevance={f_res['no_rag']['avg_relevance']:.2f}/5")
    print()


if __name__ == "__main__":
    main()
