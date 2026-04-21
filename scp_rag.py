"""
SCP RAG - Thematic SCP search + brainstorming tool
Requirements: pip install chromadb sentence-transformers datasets google-generativeai
Get free Gemini API key: https://aistudio.google.com/app/apikey
"""

import os
import chromadb
from sentence_transformers import SentenceTransformer
from datasets import load_dataset
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")  # aistudio.google.com
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")  # optional
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")       # console.groq.com — free & fast
CHROMA_PATH = "./scp_chroma_db"              # local persistent DB
COLLECTION_NAME = "scp_entries"
EMBED_MODEL = "all-MiniLM-L6-v2"            # small, fast, runs on CPU
TOP_K = 5                                    # how many SCPs to retrieve per query
# ──────────────────────────────────────────────────────────────────────────────


def load_or_create_db():
    """Load existing ChromaDB or build it fresh from HuggingFace dataset."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Check if already ingested
    existing = client.list_collections()
    if any(c.name == COLLECTION_NAME for c in existing):
        print("✓ Found existing SCP database. Loading...")
        collection = client.get_collection(COLLECTION_NAME)
        print(f"✓ {collection.count()} SCP entries loaded.")
        return collection

    # First time: ingest from HuggingFace
    print("First run — downloading SCP dataset from HuggingFace...")
    print("This will take a few minutes but only happens once.\n")

    dataset = load_dataset("quguanni/scp-foundation-structured", split="train")
    print(f"✓ Downloaded {len(dataset)} entries.")

    print("Loading embedding model...")
    embedder = SentenceTransformer(EMBED_MODEL)

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    # Ingest in batches
    BATCH_SIZE = 100
    total = len(dataset)

    print(f"Embedding and storing {total} SCPs...")

    ids, docs, metas = [], [], []
    seen_ids = set()

    for i, entry in enumerate(dataset):
        # Use exact field names from the quguanni/scp-foundation-structured schema
        item_number = str(entry.get("item_number") or "")
        scp_id = f"SCP-{item_number}" if item_number else str(entry.get("id") or f"entry_{i}")
        title = entry.get("title") or scp_id
        object_class = entry.get("object_class") or "Unknown"

        # Build rich combined text from structured fields
        description = entry.get("description") or ""
        containment = entry.get("containment_procedures") or ""
        addenda      = entry.get("addenda_text") or ""
        raw_text     = entry.get("text") or ""

        # Prefer structured fields; fall back to raw text blob
        if description or containment:
            full_text = f"[Containment Procedures]\n{containment}\n\n[Description]\n{description}"
            if addenda:
                full_text += f"\n\n[Addenda]\n{addenda}"
        else:
            full_text = raw_text

        if not full_text or len(full_text.strip()) < 50:
            continue  # skip empty/stub entries

        # Deduplicate by SCP ID (dataset has multiple content_type rows per SCP)
        if scp_id in seen_ids:
            continue
        seen_ids.add(scp_id)

        # Truncate very long entries for embedding
        text_for_embed = full_text[:2000]

        ids.append(scp_id)
        docs.append(text_for_embed)
        metas.append({
            "scp_id": scp_id,
            "title": title,
            "object_class": object_class,
            "full_text": full_text[:4000]  # store more for context window
        })

        # Batch insert
        if len(ids) == BATCH_SIZE:
            embeddings = embedder.encode(docs).tolist()
            collection.add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)
            print(f"  Ingested {i+1}/{total}...", end="\r")
            ids, docs, metas = [], [], []

    # Final batch
    if ids:
        embeddings = embedder.encode(docs).tolist()
        collection.add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metas)

    print(f"\n✓ Done. {collection.count()} SCPs stored in local DB.")
    return collection



def retrieve_scps(query: str, collection, embedder, top_k=TOP_K, object_class_filter=None):
    """Semantic search over SCP corpus."""
    query_embedding = embedder.encode([query]).tolist()

    where_filter = None
    if object_class_filter:
        where_filter = {"object_class": {"$eq": object_class_filter}}

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where=where_filter,
        include=["metadatas", "distances"]
    )

    scps = []
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        scps.append({
            "scp_id": meta["scp_id"],
            "title": meta["title"],
            "object_class": meta["object_class"],
            "text": meta["full_text"],
            "similarity": round(1 - dist, 3)
        })

    return scps


def brainstorm_with_ai(query: str, scps: list, mode: str = "brainstorm"):
    """Send retrieved SCP references to AI for horror brainstorming."""
    # SCPs are used as dark creative reference material, not the focus
    scp_context = ""
    for s in scps:
        scp_context += f"\n\n--- Reference: {s['scp_id']} (Containment Class: {s['object_class']}) ---\n{s['text'][:1500]}"

    if mode == "brainstorm":
        prompt = f"""You are an expert horror creative consultant. Your job is to help writers, filmmakers, and storytellers develop genuinely terrifying and original horror concepts.

The user wants to explore this theme/concept: "{query}"

For inspiration, here are some related anomalous entities and concepts pulled from a horror fiction database:
{scp_context}

Using these as creative fuel (not as the literal subject), provide:
1. **Core Horror Concept**: A fresh, original horror idea centered on "{query}" — what makes it deeply unsettling?
2. **Story Angles**: 2-3 distinct narrative approaches (psychological, cosmic, body horror, folk horror, etc.)
3. **The Hook**: What is the one moment, image, or reveal that would make an audience's skin crawl?
4. **Subversions**: An unexpected twist on the theme that avoids horror clichés.

Be dark, creative, and genuinely useful. Don't just rehash the reference material — use it to spark something new."""

    elif mode == "short_film":
        prompt = f"""You are a horror filmmaker helping develop a low-budget short horror film concept.

Theme/concept to explore: "{query}"

Creative references from a horror fiction archive:
{scp_context}

Develop a short film (5-15 minutes) that:
- Has a minimal cast (2-3 people max)
- Can be shot in accessible, real-world locations (apartment, campus, woods, parking garage, etc.)
- Builds dread through atmosphere, sound, and implication — not expensive effects
- Has a clear, punchy ending that lands hard

Provide: **Title**, **Logline**, **Setup**, **Key Scenes**, and **The Scare** — what specific moment or image delivers the horror payoff."""

    elif mode == "full_film":
        prompt = f"""You are an experienced horror screenwriter pitching a full-length feature film to a studio.

Theme/concept: "{query}"

Creative references from a horror fiction archive:
{scp_context}

Develop a 90-120 minute feature horror film with:
- A compelling, flawed protagonist the audience roots for
- A clear three-act structure with escalating dread
- A central horror mechanic that feels fresh and memorable
- A thematic underpinning that gives the horror meaning beyond just scares

Provide: **Title**, **Logline**, **Act 1 / Act 2 / Act 3 breakdown**, **The Monster/Threat**, and **What it's really about** (subtext/theme)."""

    elif mode == "find":
        prompt = f"""You are a horror creative consultant with deep knowledge of horror fiction, folklore, and genre tropes.

The user is researching the horror theme: "{query}"

Here are related concepts from a horror fiction archive that may be relevant:
{scp_context}

For each reference:
- Briefly summarize the core horror concept in plain language
- Explain how it connects to "{query}"
- Rate its relevance on a scale of 1-10

Then suggest 2-3 real-world horror inspirations (films, books, folklore) that also explore this theme well."""

    if DEEPSEEK_API_KEY:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except ImportError:
            return "Install the openai package: pip install openai"
        except Exception as e:
            return f"DeepSeek API Error: {str(e)}"

    elif GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except ImportError:
            return "Install the groq package: pip install groq"
        except Exception as e:
            return f"Groq API Error: {str(e)}"

    else:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Gemini API Error: {str(e)}"


def main():
    print("=" * 60)
    print("  SCP RAG — Thematic Horror Brainstorming Tool")
    print("=" * 60)

    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("\n⚠️  Set your Gemini API key in the script first.")
        print("Get one free at: https://aistudio.google.com/app/apikey")
        return

    # Load DB (builds on first run)
    collection = load_or_create_db()

    # Load embedder
    print("Loading embedding model...")
    embedder = SentenceTransformer(EMBED_MODEL)
    print("✓ Ready.\n")

    # Modes
    print("Modes:")
    print("  [1] find      — Find SCPs by theme")
    print("  [2] brainstorm — Get horror ideas based on a concept")
    print("  [3] short_film — Get short film ideas from a theme")
    print("  [q] quit\n")

    while True:
        mode_input = input("Mode (1/2/3/q): ").strip().lower()

        if mode_input == "q":
            break

        mode_map = {"1": "find", "2": "brainstorm", "3": "short_film"}
        mode = mode_map.get(mode_input)
        if not mode:
            print("Invalid mode.")
            continue

        query = input("Enter theme/concept: ").strip()
        if not query:
            continue

        # Optional filter
        class_filter = input("Filter by Object Class? (Keter/Euclid/Safe/skip): ").strip()
        class_filter = class_filter if class_filter.lower() not in ["skip", "", "n"] else None

        print("\nSearching SCP corpus...")
        scps = retrieve_scps(query, collection, embedder, object_class_filter=class_filter)

        print(f"Found {len(scps)} relevant SCPs:")
        for s in scps:
            print(f"  • {s['scp_id']} (Class: {s['object_class']}) — similarity: {s['similarity']}")

        print("\nGenerating response with Gemini...\n")
        response = brainstorm_with_gemini(query, scps, mode=mode)

        print("─" * 60)
        print(response)
        print("─" * 60 + "\n")


if __name__ == "__main__":
    main()
