"""
services/rag.py - Retrieval-Augmented Generation helpers
"""
import json
import re
from collections import Counter

from services.embeddings import search_index
from services.llm import generate

CHAT_SYSTEM = """You are StudyMate AI, a helpful study assistant.
Answer using ONLY the context provided by the student's notes.
If the answer is not in the context, say: I could not find that in your notes.
Use clear student-friendly language.
"""

SUMMARY_SYSTEM = """You are StudyMate AI, an expert academic note summarizer.
Use ONLY the provided study notes.
Write a useful study summary with:
1. Overview
2. Key points
3. Important terms
4. Exam focus
Do not mention missing context unless the notes are empty.
"""

QUIZ_SYSTEM = """You are StudyMate AI, an expert exam question generator.
Use ONLY the provided study notes.
Return ONLY valid JSON. No markdown. No text before or after JSON.
Create clear multiple-choice questions about the real study content.
Do not create questions about file names, page numbers, names in forms, metadata, or document layout.
Do not use placeholders like "...".
JSON format:
[
  {
    "question": "Clear question here?",
    "options": ["A) option", "B) option", "C) option", "D) option"],
    "answer": "A",
    "explanation": "One short reason based on the notes."
  }
]
"""

FLASHCARD_SYSTEM = """You are StudyMate AI, an expert flashcard creator.
Use ONLY the provided study notes.
Return ONLY valid JSON. No markdown. No text before or after JSON.
Create useful flashcards for exam revision.
Do not create cards about file names, page numbers, names in forms, metadata, or document layout.
Do not use placeholders like "...".
JSON format:
[
  {"front": "Question or key term", "back": "Short useful answer"}
]
"""

STOPWORDS = {
    "the", "and", "for", "with", "from", "this", "that", "are", "was", "were", "has", "have", "into",
    "also", "which", "their", "there", "using", "used", "such", "these", "those", "been", "than", "then",
    "your", "you", "can", "will", "shall", "should", "would", "could", "about", "between", "within",
}

BAD_LINE_HINTS = {
    "first name", "middle name", "last name", "full name", "email", "phone", "signature", "date of birth",
    "student id", "registration", "enrol", "enroll", "page ", "copyright", "table of contents",
}


def _clean_for_generation(text: str, max_chars: int = 14000) -> str:
    lines: list[str] = []
    seen = set()
    for raw in text.replace("\x00", " ").splitlines():
        line = " ".join(raw.split()).strip()
        if len(line) < 25:
            continue
        lower = line.lower()
        if any(h in lower for h in BAD_LINE_HINTS):
            continue
        if re.fullmatch(r"[\W\d_]+", line):
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)

    if not lines:
        return text[:max_chars]

    # Keep the beginning, middle, and later sections so generation does not focus only on cover pages.
    joined_sections: list[str] = []
    n = len(lines)
    windows = [(0, min(n, 35)), (max(0, n // 3), min(n, n // 3 + 35)), (max(0, (2 * n) // 3), min(n, (2 * n) // 3 + 35))]
    added = set()
    for start, end in windows:
        for line in lines[start:end]:
            if line not in added:
                added.add(line)
                joined_sections.append(line)

    return "\n".join(joined_sections)[:max_chars]


def _extract_json_array(raw: str) -> list:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        data = json.loads(raw[start:end + 1])
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _letter(value: str) -> str:
    value = str(value or "").strip().upper()
    m = re.search(r"[ABCD]", value)
    return m.group(0) if m else "A"


def _normalise_option(opt: str, idx: int) -> str:
    letter = "ABCD"[idx]
    opt = str(opt or "").strip()
    opt = re.sub(r"^[A-D][\).:-]\s*", "", opt, flags=re.I).strip()
    return f"{letter}) {opt}"


def _valid_text(value: str, min_len: int = 8) -> bool:
    value = str(value or "").strip()
    if len(value) < min_len:
        return False
    if value in {"...", "--", "-", "?"}:
        return False
    if "..." in value[:10]:
        return False
    return True


def _normalise_questions(items: list, limit: int) -> list[dict]:
    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        options = item.get("options", [])
        if not _valid_text(question, 15) or not isinstance(options, list) or len(options) < 4:
            continue
        options = [_normalise_option(o, i) for i, o in enumerate(options[:4])]
        if any(not _valid_text(o, 6) for o in options):
            continue
        output.append({
            "question": question,
            "options": options,
            "answer": _letter(item.get("answer", "A")),
            "explanation": str(item.get("explanation", "")).strip()[:500] or "Based on the uploaded notes.",
        })
        if len(output) >= limit:
            break
    return output


def _normalise_cards(items: list, limit: int) -> list[dict]:
    output = []
    for item in items:
        if not isinstance(item, dict):
            continue
        front = str(item.get("front", "")).strip()
        back = str(item.get("back", "")).strip()
        if not _valid_text(front, 8) or not _valid_text(back, 12):
            continue
        output.append({"front": front[:300], "back": back[:700]})
        if len(output) >= limit:
            break
    return output


def _sentences(text: str) -> list[str]:
    clean = _clean_for_generation(text, 20000)
    parts = re.split(r"(?<=[.!?])\s+|\n+", clean)
    return [p.strip() for p in parts if 55 <= len(p.strip()) <= 350]


def _keywords(text: str, limit: int = 30) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text)
    counts = Counter(w.lower() for w in words if w.lower() not in STOPWORDS)
    return [w for w, _ in counts.most_common(limit)]


def _fallback_quiz(text: str, num_questions: int) -> list[dict]:
    sentences = _sentences(text)
    keywords = _keywords(text, 40)
    if not sentences:
        return []
    output = []
    for i, sent in enumerate(sentences[:num_questions]):
        key = keywords[i % len(keywords)] if keywords else "concept"
        wrongs = [k for k in keywords if k != key][:3]
        while len(wrongs) < 3:
            wrongs.append(f"related topic {len(wrongs) + 1}")
        output.append({
            "question": f"Which statement is supported by the notes about {key}?",
            "options": [
                f"A) {sent[:180]}",
                f"B) {wrongs[0].title()} is the only topic discussed in the notes.",
                f"C) The notes do not discuss any study concept.",
                f"D) The document is only a blank form with no content.",
            ],
            "answer": "A",
            "explanation": "Option A is directly taken from the uploaded notes.",
        })
    return output


def _fallback_cards(text: str, num_cards: int) -> list[dict]:
    sentences = _sentences(text)
    keywords = _keywords(text, num_cards * 2)
    output = []
    for i, sent in enumerate(sentences[:num_cards]):
        term = keywords[i] if i < len(keywords) else f"Key idea {i + 1}"
        output.append({
            "front": f"What should you remember about {term}?",
            "back": sent,
        })
    return output


async def rag_chat(file_id: str, question: str) -> tuple[str, list[dict]]:
    queries = [question]
    if any(word in question.lower() for word in ["summary", "summarize", "summery", "overview", "main point"]):
        queries.append("main concepts important points overview")

    results = []
    seen = set()
    for q in queries:
        for item in search_index(file_id, q, top_k=6):
            chunk = item["chunk"]
            if chunk not in seen:
                seen.add(chunk)
                results.append(item)

    if not results:
        answer = "I could not find relevant text from your uploaded notes. Try re-uploading a clearer PDF or TXT file."
        return answer, []

    context = "\n\n---\n\n".join(r["chunk"] for r in results[:8])
    prompt = f"Context from the student's notes:\n\n{context}\n\nQuestion: {question}\n\nAnswer using the context only."

    answer = await generate(prompt=prompt, system=CHAT_SYSTEM, max_tokens=900, temperature=0.25)
    sources = [{"chunk": r["chunk"][:240], "score": r["score"]} for r in results[:5]]
    return answer, sources


async def summarise_text(text: str) -> str:
    excerpt = _clean_for_generation(text, 16000)
    prompt = f"Summarise these study notes for exam revision. Use the actual content.\n\n{excerpt}"
    return await generate(prompt=prompt, system=SUMMARY_SYSTEM, max_tokens=1400, temperature=0.25)


async def generate_quiz(text: str, num_questions: int = 5) -> list[dict]:
    num_questions = max(1, min(int(num_questions), 15))
    excerpt = _clean_for_generation(text, 16000)
    prompt = (
        f"Create exactly {num_questions} useful multiple-choice quiz questions from these notes. "
        "Every question must test a concept from the notes. Avoid personal information, file metadata, and placeholders.\n\n"
        f"STUDY NOTES:\n{excerpt}"
    )
    try:
        raw = await generate(prompt=prompt, system=QUIZ_SYSTEM, max_tokens=3000, temperature=0.2)
        questions = _normalise_questions(_extract_json_array(raw), num_questions)
    except Exception:
        questions = []

    if len(questions) < num_questions:
        existing = {q["question"] for q in questions}
        for q in _fallback_quiz(text, num_questions):
            if q["question"] not in existing:
                questions.append(q)
            if len(questions) >= num_questions:
                break
    return questions[:num_questions]


async def generate_flashcards(text: str, num_cards: int = 10) -> list[dict]:
    num_cards = max(1, min(int(num_cards), 30))
    excerpt = _clean_for_generation(text, 16000)
    prompt = (
        f"Create exactly {num_cards} useful flashcards from these notes. "
        "Each front should be a question or key term. Each back should be a clear answer from the notes.\n\n"
        f"STUDY NOTES:\n{excerpt}"
    )
    try:
        raw = await generate(prompt=prompt, system=FLASHCARD_SYSTEM, max_tokens=3000, temperature=0.2)
        cards = _normalise_cards(_extract_json_array(raw), num_cards)
    except Exception:
        cards = []

    if len(cards) < num_cards:
        existing = {c["front"] for c in cards}
        for c in _fallback_cards(text, num_cards):
            if c["front"] not in existing:
                cards.append(c)
            if len(cards) >= num_cards:
                break
    return cards[:num_cards]
