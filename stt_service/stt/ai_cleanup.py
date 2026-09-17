import os
import re
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

from dotenv import load_dotenv
from huggingface_hub import InferenceClient


# =========================================================
# Configuration
# =========================================================

load_dotenv()

# HF_MODEL = "Qwen/Qwen3-8B"
HF_MODEL = "CohereLabs/aya-expanse-32b"

# V3 rewrites each chunk as a cleaned transcript while preserving
# the lecturer's meaning, dialect, order, and speaking style.
MAX_CHARS_PER_CHUNK = 2500
CONTEXT_CHARS = 600

# Rewriting needs more output room than correction-JSON mode.
MAX_OUTPUT_TOKENS = 3000

# Parallel chunk requests.
MAX_WORKERS = 3

# Retry only when Python rejects a rewritten chunk as unsafe.
MAX_REWRITE_ATTEMPTS = 1

# Safety limits for rewritten chunks.
MIN_LENGTH_RATIO = 0.70
MAX_LENGTH_RATIO = 1.30
MIN_TOKEN_OVERLAP = 0.42
MIN_ENGLISH_TOKEN_RATIO = 0.45
MAX_ENGLISH_TOKEN_RATIO = 1.80

# Python-only lecture-wide clues. No extra model request.
MAX_GLOBAL_CLUES = 100

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise RuntimeError(
        "HF_TOKEN was not found in .env"
    )


print("Initializing Hugging Face InferenceClient...")

hf_client = InferenceClient(
    model=HF_MODEL,
    token=HF_TOKEN,
)

print("Hugging Face InferenceClient initialized")


# =========================================================
# Prompt
# =========================================================

def build_rewrite_prompt(
    main_text: str,
    previous_context: str = "",
    next_context: str = "",
    global_clues: list[str] | None = None,
    strict_retry: bool = False,
) -> str:

    global_clues = global_clues or []

    clues_text = "\n".join(
        f"- {item}"
        for item in global_clues
    )

    retry_instruction = ""

    if strict_retry:
        retry_instruction = """
This is a STRICT RETRY because the previous rewrite failed safety checks.

Be MORE conservative this time:
- stay closer to the original wording
- do not shorten explanations
- do not add new information
- do not remove technical terms
- only reconstruct wording when the intended speech is reasonably clear
"""
    return f"""
You are cleaning a speech-to-text transcript of a university lecture.

Your task is to produce a clear and accurate cleaned transcript while preserving
the lecturer's original content, meaning, speaking style, and level of detail.

The lecture may belong to ANY academic or technical field and may naturally mix
Arabic and English.

IMPORTANT GOAL:

The result should read like a cleaned version of what the lecturer actually said,
not like a summary, textbook, article, or rewritten lecture.

==================================================
CONTENT PRESERVATION
==================================================

Preserve:
- the lecturer's meaning
- the original order of ideas
- examples and explanations
- questions and transitions
- important repetition
- the lecturer's colloquial Arabic style
- the original level of detail
- numbers, durations, quantities, and factual claims

Do NOT heavily summarize or shorten the transcript.

Do NOT remove useful explanations just to make the text shorter.

Do NOT reorganize the lecture into notes, sections, bullet points, or numbered
lists unless the lecturer actually used that structure.

Do NOT add information or explanations from your own knowledge.

==================================================
TRANSCRIPT CLEANUP
==================================================

You SHOULD:
- correct clear speech-to-text errors
- fix malformed or phonetically corrupted words
- correct technical terms when the intended term is reasonably clear
- reconstruct short corrupted phrases when the intended meaning is clear
- remove obvious accidental STT duplication
- add punctuation and sentence boundaries when helpful
- improve readability without changing the lecturer's meaning

You MAY lightly rephrase a badly corrupted phrase when necessary to make the
intended speech understandable.

However, avoid rewriting sentences that are already understandable.

Do not make the lecturer sound unnecessarily formal or academic.

Preserve colloquial Arabic when the lecturer speaks colloquially.

==================================================
ENGLISH TERMINOLOGY
==================================================

The transcript may contain English technical terms mixed naturally with Arabic.

If an English technical term is correctly transcribed, KEEP IT IN ENGLISH.

Do NOT translate English technical terms into Arabic.

Do NOT replace an English term with its Arabic equivalent.

Do NOT automatically add Arabic translations in parentheses.

For example, if the lecturer says an English technical term, preserve that term
in English in the cleaned transcript.

If an English term is clearly corrupted by speech-to-text, you may correct it
to the intended English term when pronunciation and context strongly support
the correction.

If you are uncertain about the intended technical term, keep the original
wording rather than inventing a different concept.

==================================================
ACCURACY
==================================================

Do not invent facts.

Do not change numbers or durations.

Do not expand unclear information using general knowledge.

Do not introduce definitions that the lecturer did not give.

If a phrase is too unclear to reconstruct reliably, preserve it as closely as
possible instead of inventing a polished explanation.

==================================================
CONTEXT
==================================================

PREVIOUS_CONTEXT and NEXT_CONTEXT are provided only to help understand unclear
phrases near MAIN_TEXT.

Do not include them in the output.

<PREVIOUS_CONTEXT>
{previous_context}
</PREVIOUS_CONTEXT>

<NEXT_CONTEXT>
{next_context}
</NEXT_CONTEXT>

GLOBAL_TECHNICAL_CLUES contains terms found elsewhere in the same lecture.
They are hints only and may themselves contain transcription errors.

<GLOBAL_TECHNICAL_CLUES>
{clues_text}
</GLOBAL_TECHNICAL_CLUES>

==================================================
MAIN TEXT
==================================================

<MAIN_TEXT>
{main_text}
</MAIN_TEXT>

==================================================
OUTPUT
==================================================

Return ONLY the cleaned version of MAIN_TEXT.

Do not return analysis, comments, notes, Markdown, headings, or prompt tags.

The final output should preserve most of the original lecture content and detail,
while correcting transcription errors and making the speech easier to read.

Keep English technical terminology in English.
""".strip()

# =========================================================
# Text helpers
# =========================================================

def extract_numbers(
    text: str,
) -> list[str]:

    return re.findall(
        r"\d+(?:[.,]\d+)?",
        text or "",
    )


def word_tokens(
    text: str,
) -> list[str]:

    return re.findall(
        r"[A-Za-z0-9]+|[\u0600-\u06FF]+",
        text or "",
    )


def english_tokens(
    text: str,
) -> list[str]:

    return re.findall(
        r"[A-Za-z][A-Za-z0-9+.#/_-]*",
        text or "",
    )


def normalized_for_similarity(
    text: str,
) -> str:

    return " ".join(
        token.casefold()
        for token in word_tokens(text)
    )


def sequence_similarity(
    first: str,
    second: str,
) -> float:

    first_norm = normalized_for_similarity(
        first
    )

    second_norm = normalized_for_similarity(
        second
    )

    if not first_norm or not second_norm:
        return 0.0

    return SequenceMatcher(
        None,
        first_norm,
        second_norm,
        autojunk=False,
    ).ratio()


def token_overlap_ratio(
    original: str,
    cleaned: str,
) -> float:
    """
    Fraction of meaningful ORIGINAL token types still represented
    exactly in the cleaned chunk.

    This is only a coarse anti-hallucination safety check.
    """

    original_tokens = {
        token.casefold()
        for token in word_tokens(original)
        if len(token) >= 2
    }

    cleaned_tokens = {
        token.casefold()
        for token in word_tokens(cleaned)
        if len(token) >= 2
    }

    if not original_tokens:
        return 1.0

    return (
        len(
            original_tokens
            & cleaned_tokens
        )
        / len(original_tokens)
    )


def english_token_ratio(
    original: str,
    cleaned: str,
) -> float:

    original_count = len(
        english_tokens(original)
    )

    cleaned_count = len(
        english_tokens(cleaned)
    )

    if original_count == 0:
        return 1.0

    return (
        cleaned_count
        / original_count
    )


# =========================================================
# Python-only global technical clues
# =========================================================

def extract_global_technical_clues(
    raw_text: str,
) -> list[str]:

    if not raw_text:
        return []

    pattern = re.compile(
        r"(?<![A-Za-z0-9])"
        r"[A-Za-z][A-Za-z0-9+.#/_-]*"
        r"(?:\s+[A-Za-z][A-Za-z0-9+.#/_-]*){0,3}"
        r"(?![A-Za-z0-9])"
    )

    results = []
    seen = set()

    for match in pattern.finditer(
        raw_text
    ):

        phrase = (
            match.group(0)
            .strip()
        )

        if not phrase:
            continue

        key = phrase.casefold()

        if key in seen:
            continue

        seen.add(key)
        results.append(
            phrase
        )

        if (
            len(results)
            >= MAX_GLOBAL_CLUES
        ):
            break

    return results


# =========================================================
# Chunking
# =========================================================

def split_text_into_chunks(
    text: str,
    max_chars: int = MAX_CHARS_PER_CHUNK,
) -> list[dict]:

    text = text or ""

    if not text.strip():
        return []

    chunks = []
    text_length = len(text)
    start = 0

    # Do not jump too far backward just because an old question mark exists.
    # This keeps a ~4700-char lecture near two chunks instead of three.
    boundary_search_back = 220

    while start < text_length:

        while (
            start < text_length
            and text[start].isspace()
        ):
            start += 1

        if start >= text_length:
            break

        target_end = min(
            start + max_chars,
            text_length,
        )

        end = target_end

        if target_end < text_length:

            search_start = max(
                start,
                target_end
                - boundary_search_back,
            )

            best_break = -1

            for separator in (
                ".",
                "؟",
                "!",
                "\n",
            ):

                position = text.rfind(
                    separator,
                    search_start,
                    target_end,
                )

                if position > best_break:
                    best_break = position

            if best_break != -1:
                end = best_break + 1

            else:
                last_space = text.rfind(
                    " ",
                    search_start,
                    target_end,
                )

                if last_space > start:
                    end = last_space

        if end <= start:
            end = min(
                start + max_chars,
                text_length,
            )

        chunk_text = (
            text[start:end]
            .strip()
        )

        if chunk_text:
            chunks.append(
                {
                    "start": start,
                    "end": end,
                    "text": chunk_text,
                }
            )

        start = end

    return chunks


# =========================================================
# Model output cleanup
# =========================================================

def sanitize_rewrite_output(
    response_text: str,
) -> str:

    if not response_text:
        return ""

    cleaned = (
        response_text
        .strip()
    )

    cleaned = re.sub(
        r"^```(?:text|markdown)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    # Handle accidental wrapper tags if the model adds them.
    match = re.search(
        r"<CLEANED_TEXT>\s*(.*?)\s*</CLEANED_TEXT>",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:
        cleaned = (
            match.group(1)
            .strip()
        )

    # Remove a label if the model ignored the instruction once.
    cleaned = re.sub(
        r"^(?:cleaned text|cleaned transcript|النص المنظف)\s*:\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return cleaned.strip()


# =========================================================
# Safety validation
# =========================================================

def validate_rewritten_chunk(
    original: str,
    cleaned: str,
) -> tuple[bool, dict]:

    metrics = {
        "reason": "ok",
        "length_ratio": 0.0,
        "token_overlap": 0.0,
        "english_ratio": 0.0,
        "similarity": 0.0,
    }

    original = (
        original
        or ""
    ).strip()

    cleaned = (
        cleaned
        or ""
    ).strip()

    if not cleaned:
        metrics["reason"] = (
            "empty output"
        )
        return False, metrics

    length_ratio = (
        len(cleaned)
        / max(
            len(original),
            1,
        )
    )

    metrics[
        "length_ratio"
    ] = length_ratio

    if not (
        MIN_LENGTH_RATIO
        <= length_ratio
        <= MAX_LENGTH_RATIO
    ):
        metrics["reason"] = (
            "unsafe length ratio"
        )
        return False, metrics

    original_numbers = (
        extract_numbers(
            original
        )
    )

    cleaned_numbers = (
        extract_numbers(
            cleaned
        )
    )

    if (
        original_numbers
        != cleaned_numbers
    ):
        metrics["reason"] = (
            "numbers changed"
        )
        metrics[
            "original_numbers"
        ] = original_numbers
        metrics[
            "cleaned_numbers"
        ] = cleaned_numbers
        return False, metrics

    overlap = token_overlap_ratio(
        original,
        cleaned,
    )

    metrics[
        "token_overlap"
    ] = overlap

    if overlap < MIN_TOKEN_OVERLAP:
        metrics["reason"] = (
            "too little lexical overlap"
        )
        return False, metrics

    eng_ratio = english_token_ratio(
        original,
        cleaned,
    )

    metrics[
        "english_ratio"
    ] = eng_ratio

    if not (
        MIN_ENGLISH_TOKEN_RATIO
        <= eng_ratio
        <= MAX_ENGLISH_TOKEN_RATIO
    ):
        metrics["reason"] = (
            "technical-language balance changed too much"
        )
        return False, metrics

    similarity = sequence_similarity(
        original,
        cleaned,
    )

    metrics[
        "similarity"
    ] = similarity

    return True, metrics


# =========================================================
# Aya rewrite call
# =========================================================

def rewrite_chunk_with_aya(
    main_text: str,
    previous_context: str = "",
    next_context: str = "",
    global_clues: list[str] | None = None,
) -> tuple[str, dict]:

    """
    Accept-all mode:

    - every NON-EMPTY model rewrite is accepted directly
    - validation metrics are calculated only for logging/diagnostics
    - Python does NOT reject based on length, overlap, English ratio,
      similarity, or changed numbers
    - fallback to the original chunk happens only if the model request
      fails or returns an empty output
    """

    global_clues = (
        global_clues
        or []
    )

    started = (
        time.perf_counter()
    )

    try:
        completion = (
            hf_client
            .chat
            .completions
            .create(
                messages=[
                    {
                        "role": "system",
                    "content": (
                    "Clean speech-to-text errors in a university lecture transcript. "
                    "Preserve the lecturer's meaning, detail, order, examples, and speaking style. "
                    "Do not heavily summarize or add outside information. "
                    "Keep English technical terms in English and do not translate them into Arabic."
),
                    },
                    {
                        "role": "user",
                        "content": build_rewrite_prompt(
                            main_text=main_text,
                            previous_context=previous_context,
                            next_context=next_context,
                            global_clues=global_clues,
                            strict_retry=False,
                        ),
                    },
                ],
                temperature=0.0,
                max_tokens=MAX_OUTPUT_TOKENS,
            )
        )

        response_text = (
            completion
            .choices[0]
            .message.content
            or ""
        )

        cleaned = (
            sanitize_rewrite_output(
                response_text
            )
        )

        elapsed = (
            time.perf_counter()
            - started
        )

        # Empty output is not a usable model proposal.
        if not cleaned:
            print(
                f"Aya rewrite finished in {elapsed:.2f}s "
                "| empty output -> original chunk fallback"
            )

            return (
                main_text,
                {
                    "reason": "empty model output",
                    "accepted": False,
                },
            )

        # Keep the old validator only as a DIAGNOSTIC metric source.
        # Its boolean result is intentionally ignored.
        _, metrics = (
            validate_rewritten_chunk(
                original=main_text,
                cleaned=cleaned,
            )
        )

        metrics[
            "reason"
        ] = "accepted_model_output"

        metrics[
            "accepted"
        ] = True

        print(
            f"Aya rewrite finished in {elapsed:.2f}s "
            f"| ACCEPTED=True | "
            f"length={metrics.get('length_ratio', 0.0):.2f} | "
            f"overlap={metrics.get('token_overlap', 0.0):.2f} | "
            f"similarity={metrics.get('similarity', 0.0):.2f}"
        )

        return (
            cleaned,
            metrics,
        )

    except Exception as e:

        elapsed = (
            time.perf_counter()
            - started
        )

        print(
            f"Aya rewrite request failed after "
            f"{elapsed:.2f}s: {e}"
        )

        print(
            "Falling back to original chunk because "
            "the model request itself failed."
        )

        return (
            main_text,
            {
                "reason": (
                    f"request failed: {e}"
                ),
                "accepted": False,
            },
        )


# =========================================================
# Process one chunk
# =========================================================

def process_chunk(
    index: int,
    chunks: list[dict],
    global_clues: list[str],
) -> tuple[int, str, dict]:

    chunk = chunks[index]

    previous_context = ""
    next_context = ""

    if index > 0:
        previous_context = (
            chunks[index - 1]["text"][
                -CONTEXT_CHARS:
            ]
        )

    if (
        index
        < len(chunks) - 1
    ):
        next_context = (
            chunks[index + 1]["text"][
                :CONTEXT_CHARS
            ]
        )

    print(
        f"Starting rewrite chunk "
        f"{index + 1}/{len(chunks)}..."
    )

    cleaned, metrics = (
        rewrite_chunk_with_aya(
            main_text=chunk["text"],
            previous_context=previous_context,
            next_context=next_context,
            global_clues=global_clues,
        )
    )

    return (
        index,
        cleaned,
        metrics,
    )


# =========================================================
# Merge
# =========================================================

def merge_cleaned_chunks(
    cleaned_chunks: list[str],
) -> str:

    parts = [
        part.strip()
        for part in cleaned_chunks
        if part
        and part.strip()
    ]

    if not parts:
        return ""

    # Single spaces are safer than artificial paragraphs because a chunk
    # boundary may occur in the middle of a spoken sentence.
    return " ".join(
        parts
    ).strip()


# =========================================================
# Main cleanup pipeline
# =========================================================

def clean_long_transcript_with_qwen_client(
    raw_text: str,
) -> str:

    """
    Compatibility name preserved so existing project imports do not change.

    V3 accept-all behavior:
    - rewrite each chunk as a cleaned transcript
    - preserve lecturer voice and meaning through the prompt
    - accept every non-empty model rewrite
    - Python metrics are diagnostic only
    - fall back only if the request fails or output is empty
    """

    raw_text = (
        raw_text
        or ""
    ).strip()

    if not raw_text:
        return ""

    pipeline_started = (
        time.perf_counter()
    )

    global_clues = (
        extract_global_technical_clues(
            raw_text
        )
    )

    chunks = (
        split_text_into_chunks(
            raw_text,
            MAX_CHARS_PER_CHUNK,
        )
    )

    if not chunks:
        return raw_text

    print()
    print(
        "========================================"
    )
    print(
        "Starting Transcript Cleanup V3 - ACCEPT ALL"
    )
    print(
        f"Model: {HF_MODEL}"
    )
    print(
        f"Chunks: {len(chunks)}"
    )
    print(
        f"Chunk size: ~{MAX_CHARS_PER_CHUNK} chars"
    )
    print(
        f"Parallel workers: {MAX_WORKERS}"
    )
    print(
        f"Global technical clues: {len(global_clues)}"
    )
    print(
        "Mode: context-preserving rewrite / accept every non-empty model output"
    )
    print(
        "========================================"
    )
    print()

    results = {}

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(
                process_chunk,
                index,
                chunks,
                global_clues,
            ): index
            for index in range(
                len(chunks)
            )
        }

        for future in as_completed(
            futures
        ):

            index = futures[
                future
            ]

            try:
                (
                    chunk_index,
                    cleaned,
                    metrics,
                ) = future.result()

                results[
                    chunk_index
                ] = {
                    "text": cleaned,
                    "metrics": metrics,
                }

            except Exception as e:
                print(
                    f"Chunk {index + 1} failed: {e}"
                )

                results[
                    index
                ] = {
                    "text": chunks[
                        index
                    ]["text"],
                    "metrics": {
                        "reason": (
                            f"chunk exception: {e}"
                        )
                    },
                }

    cleaned_chunks = []

    print()
    print(
        "========== CHUNK RESULTS =========="
    )

    for index in range(
        len(chunks)
    ):

        item = results.get(
            index
        )

        if item is None:
            cleaned = (
                chunks[index][
                    "text"
                ]
            )
            metrics = {
                "reason": (
                    "missing result"
                )
            }
        else:
            cleaned = item[
                "text"
            ]
            metrics = item[
                "metrics"
            ]

        cleaned_chunks.append(
            cleaned
        )

        print(
            f"Chunk {index + 1}: "
            f"reason={metrics.get('reason', 'ok')} | "
            f"length={metrics.get('length_ratio', 1.0):.2f} | "
            f"overlap={metrics.get('token_overlap', 1.0):.2f} | "
            f"similarity={metrics.get('similarity', 1.0):.2f}"
        )

    print(
        "==================================="
    )

    cleaned_text = (
        merge_cleaned_chunks(
            cleaned_chunks
        )
    )

    # Accept-all mode:
    # Do NOT revert the final transcript if numbers changed.
    # Number differences may still appear in diagnostic logs, but the
    # model output is preserved as requested.

    elapsed = (
        time.perf_counter()
        - pipeline_started
    )

    print()
    print(
        f"Transcript Cleanup V3 ACCEPT-ALL completed in "
        f"{elapsed:.2f} seconds."
    )
    print(
        f"Raw chars: {len(raw_text)}"
    )
    print(
        f"Final chars: {len(cleaned_text)}"
    )
    print(
        f"Final length ratio: "
        f"{len(cleaned_text) / max(len(raw_text), 1):.2f}"
    )
    print()

    return cleaned_text


# =========================================================
# Optional: clean one standalone transcript/chunk
# =========================================================

def clean_transcript_with_qwen_client(
    main_text: str,
    previous_context: str = "",
    next_context: str = "",
) -> str:

    main_text = (
        main_text
        or ""
    ).strip()

    if not main_text:
        return ""

    global_clues = (
        extract_global_technical_clues(
            main_text
        )
    )

    cleaned, _ = (
        rewrite_chunk_with_aya(
            main_text=main_text,
            previous_context=previous_context,
            next_context=next_context,
            global_clues=global_clues,
        )
    )

    return cleaned







