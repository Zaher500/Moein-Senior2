from huggingface_hub import InferenceClient
import os
from dotenv import load_dotenv

load_dotenv()

#  Hugging Face Client


HF_API_KEY = os.getenv("HF_TOKEN")

if not HF_API_KEY:
    raise RuntimeError(
        "HF_TOKEN is not set in environment variables"
    )


CHUNK_MODEL = "Qwen/Qwen3-8B"
FINAL_MODEL = "openai/gpt-oss-20b"


chunk_client = InferenceClient(
    model=CHUNK_MODEL,
    provider="nscale",
    token=HF_API_KEY
)


final_client = InferenceClient(
    model=FINAL_MODEL,
    provider="auto",
    token=HF_API_KEY
)

PROMPT_TEMPLATE = """
/no_think

You are an academic source-grounding assistant.

Convert the following lecture segment into concise,
source-faithful academic notes.

Your job is to COMPRESS the provided content,
not to complete it using your own knowledge.

LANGUAGE PRESERVATION IS MANDATORY:

- Preserve the natural language of the source content.
  Do NOT translate the lecture into another language unless
  explicitly requested.

- Determine the main language primarily from the source's
  explanatory prose, complete sentences, definitions,
  descriptions, and educational discussion.

- Do NOT treat technical terms, abbreviations, code,
  model names, proper nouns, product names, translated titles,
  headings, or isolated foreign-language words or labels
  as evidence that the main language has changed.

- When determining the source language, prioritize native
  lecture text and source-visible text over processing annotations.

- The language used inside [VISUAL DESCRIPTION] or
  [VISUAL RELATIONSHIPS] does NOT determine the natural language
  of the lecture.

- If one natural language clearly dominates the explanatory
  content, write the academic notes in that language.

- Preserve technical terms, abbreviations, proper nouns,
  model names, and established terminology in their original
  language when appropriate.

- If the lecture segment genuinely contains substantial
  explanatory content in more than one language and no single
  language clearly dominates, preserve its bilingual or
  multilingual nature rather than translating everything
  into one language.

Rules:

- Use ONLY information explicitly stated or clearly supported
  by this lecture segment.

- Do NOT infer relationships merely because two pieces of
  information appear near each other.

- Do NOT infer that a concept belongs to a particular version,
  model, category, level, stage, or group unless the provided
  text explicitly makes that association.

- Preserve reliable technical terminology, abbreviations, names,
  numbers, labels, and relationships exactly as supported
  by the provided source content.

- Never expand an abbreviation into a different term
  unless the expansion is explicitly supported by the source.

- Do NOT correct, complete, reinterpret, or normalize
  technical content using general knowledge.

- If information is incomplete, ambiguous, or cut off,
  preserve only what is clearly supported.
  Do not guess the missing information.

- Preserve important comparisons, distinctions,
  structured lists, examples, steps, and relationships.

- When the source contains multiple adjacent headings, lists,
  tables, columns, sections, or labeled groups, treat each one
  as a separate source region unless the source explicitly
  connects them.

- Associate an item, value, definition, property, or list entry
  only with the heading, label, column, section, or group that
  clearly contains or explicitly governs it.

- When a new heading, labeled group, column, section, or list begins,
  do NOT carry items, values, definitions, properties, or relationships
  from the previous group into the new one.

- If nearby groups contain similar labels, numbers, terminology,
  or repeated values, do NOT merge them, treat them as equivalent,
  or transfer information between them unless that relationship
  is explicitly supported by the source.

- Do not omit unique educational information merely
  to make the notes shorter.

- Remove only clear repetition or decorative information
  that has no educational meaning.

- Do not mention chunks, OCR, prompts, models,
  summarization, or the processing pipeline.

- When the input comes from flattened text, OCR, tables, diagrams,
  or visual layouts, do NOT infer parent-child, category-item,
  version-property, or heading-content relationships merely from
  the order or proximity of text.

- If the relationship between items is not explicit or reliable,
  preserve the items without assigning them to a specific group
  or relationship.

- If text appears severely corrupted, nonsensical, or unreliable
  due to OCR or extraction errors, do NOT treat it as valid
  academic terminology.
  Omit it rather than guessing, correcting, or inventing its meaning.

- Text under [TEXT INSIDE IMAGE] may come from OCR and may contain
  recognition errors.

- When [VISUAL DESCRIPTION] or [VISUAL RELATIONSHIPS] explicitly
  provide a clearer label, grouping, or relationship than the OCR text,
  prefer the visually supported information.

- Do not preserve isolated corrupted or nonsensical OCR terms as
  academic terminology when they are not confirmed by the visual
  description, visual relationships, or another clear source segment.

- Do not correct corrupted OCR using general knowledge.
  Use a cleaner term only when it is explicitly supported elsewhere
  in the provided source content; otherwise omit the unreliable term.

Lecture segment:
\"\"\"
{TEXT}
\"\"\"
"""

# Summarization Function (CHAT API)


def summarize_text(text: str, max_new_tokens: int = 3200) -> str:
    """
    Summarize a chunk of lecture text using Hugging Face Inference API
    (Conversational / Chat-based model).

    Args:
        text (str): Lecture text chunk
        max_new_tokens (int): Maximum tokens for generated summary

    Returns:
        str: Summary text
    """

    text = text.strip()

    if not text:
        return ""

    prompt = PROMPT_TEMPLATE.replace("{TEXT}", text)

    try:
        response = chunk_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert academic assistant. "
                        "Summarize lecture text accurately and concisely."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=max_new_tokens,
            temperature=0.1,
            top_p=0.9,
        )

        # DEBUG: check if Qwen stopped normally or hit token limit
        print(
            f"[CHUNK] finish_reason="
            f"{response.choices[0].finish_reason}"
        )


        return response.choices[0].message.content.strip()
    

    except Exception as e:
        print("Hugging Face summarization error:", str(e))
        return ""




FINAL_SUMMARY_PROMPT = """
You are an expert academic assistant.

Below are partial summaries generated from consecutive parts
of the SAME academic lecture.

Your task is to create ONE coherent, accurate, study-friendly
final summary of the ENTIRE lecture.

STRICT SOURCE-GROUNDING RULE:
Use ONLY information supported by the provided partial summaries.
Do NOT add facts, examples, recommendations, classifications,
definitions, terminology, or relationships from your general knowledge.

Rules:

1. Treat all partial summaries as parts of ONE lecture.

2. Cover ALL major topics appearing across the beginning,
   middle, and end of the provided content.
   Do not over-focus on the first sections.

3. Before writing, identify the major topics contained across
   all partial summaries and ensure every important topic is
   represented in the final summary.

4. Preserve reliable technical terminology exactly in its original context.
   Do not rename, reinterpret, merge, translate into a new conceptual term,
   or substitute concepts, categories, levels, components, groups, stages,
   or methods unless the provided content explicitly supports doing so.

- Do not create a new framework, model, concept, category, or named
  section merely to organize related information.

- A heading is itself a factual claim.
  Use a conceptual heading only when that concept or grouping is
  explicitly supported by the provided partial summaries.

- If several items belong to an existing source concept, keep them
  under that source concept instead of inventing a broader or
  alternative interpretation.

5. When multiple versions, models, frameworks, methods,
   categories, levels, or alternatives are discussed:
   - Keep each piece of information associated with its correct context.
   - Do not transfer a property from one concept to another.
   - Do not assume equivalence unless explicitly supported.
   - Preserve distinctions exactly as stated.

6. Preserve exact numbers, levels, names, sequences,
   classifications, and relationships when explicitly provided.
   Do not infer missing values or categories.

7. If the provided content distinguishes between similar concepts,
   preserve that distinction.
   Do not merge concepts merely because they have similar names.

8. Do NOT invent examples.
   Include an example only when it is explicitly present
   in the provided partial summaries.

9. Do NOT add recommendations, advice, best practices,
   practical takeaways, conclusions, or interpretations
   unless they are explicitly supported by the provided content.

10. Do NOT expand incomplete or vague information using outside knowledge.
    If a detail is uncertain or unsupported, omit it rather than guessing.

11. Merge genuinely duplicated information,
    but preserve all unique educational information.

12. Preserve important comparisons, distinctions, and relationships
    explicitly present in the provided content.
    Do not flatten or merge information that the source keeps separate.

13. Preserve important structured information when academically meaningful,
    such as ordered lists, grouped items, sequences, hierarchies,
    or step-by-step information.

14. Preserve the natural language of the provided academic content.
    Do NOT translate the content into another language unless
    explicitly requested.

    Determine the main language from explanatory prose,
    definitions, sentences, and educational discussion.

    Do NOT use technical terms, abbreviations, code, model names,
    proper nouns, headings, or isolated foreign-language labels
    as evidence that the main language has changed.

    If one language clearly dominates the academic explanation,
    write the final summary in that language.

    If the provided content is genuinely bilingual and substantial
    academic explanation exists in more than one language, preserve
    the bilingual nature of the content rather than forcing the
    entire summary into one language.

15. Preserve technical terms, abbreviations, model names,
    proper nouns, and established terminology in their original
    language when appropriate.
    Do not translate technical terminology unnecessarily.


16. Prioritize educational content over decorative visual information.
    Do not describe logos, colors, backgrounds, slide design,
    or visual styling unless they carry educational meaning.

17. Do not mention chunks, partial summaries, OCR,
    image processing, prompts, models, or the summarization process.

18. Do not include meta-commentary about the summary itself.
    Do not claim that the summary is complete, accurate,
    or covers all topics.

19. Do not leave incomplete sentences or unfinished sections.

20. Organize the summary using clear headings and bullet points
    when useful for studying.

21. The final summary should be sufficiently detailed to represent
    the lecture and should not become an overly compressed overview.

22. Before finishing, internally verify:
    - Did I cover the major topics from the beginning, middle, and end?
    - Did I add anything not supported by the provided content?
    - Did I accidentally change terminology or context?
    - Did I merge information that should remain separate?
    - Did I invent any example, recommendation, number,
      relationship, or classification?

    If yes, correct it before producing the final answer.

- Do not create a combined example, category, entity, model,
  or concept by merging details that refer to different source contexts.

- When several examples belong to different concepts, sections,
  components, or entities, preserve their original associations.
  Do not present them as parts of one combined example unless
  the provided content explicitly states that they belong together.

- Do not include obviously corrupted, nonsensical, or unreliable
  OCR-like terms as academic facts or terminology.
  If a term cannot be interpreted reliably from the provided content,
  omit it rather than guessing or presenting it as valid.

- If partial summaries contain conflicting names, abbreviations,
  labels, relationships, values, or classifications, do NOT reconcile
  the conflict using general knowledge.

- Prefer information that is clearly and consistently supported
  across the provided partial summaries.

- If the conflict cannot be resolved from the provided content alone,
  omit the uncertain detail rather than choosing one version or
  combining them.

- Do not generalize a property observed in one diagram, section,
  example, or representation to an entire version, model, framework,
  category, or concept unless the provided content explicitly
  supports that broader claim.

- When partial summaries contain conflicting values, labels, names,
  levels, categories, or classifications, never merge the conflicting
  alternatives into a combined value or label.

- Do not create constructions such as "A / B", combined ranges,
  shared classifications, or unified tables in order to reconcile
  conflicting source information.

- Keep conflicting information separate only when each association
  is clearly tied to a distinct source context.
  If the correct association cannot be determined from the provided
  content, omit the disputed detail.

- Do not transfer a value, level, label, or classification from one
  measurement system, representation, model, group, or context to another.

Partial summaries:

\"\"\"
{SUMMARIES}
\"\"\"
"""



def summarize_final(
    combined_summaries: str,
    max_new_tokens: int = 3200
) -> str:

    combined_summaries = combined_summaries.strip()

    if not combined_summaries:
        print("[FINAL] Combined summaries are empty")
        return ""

    print(
        f"[FINAL] Input characters: "
        f"{len(combined_summaries)}"
    )

    prompt = FINAL_SUMMARY_PROMPT.replace(
        "{SUMMARIES}",
        combined_summaries
    )

    try:
        print("[FINAL] Sending request to final model...")

        response = final_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert academic assistant. "
                        "Create one coherent final lecture summary."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=max_new_tokens,
            temperature=0.2,
            top_p=0.9,
              extra_body={
              "reasoning_effort": "low"
             },
        )

        if not response.choices:
            print("[FINAL] Model returned no choices")
            return ""

        content = response.choices[0].message.content

        if not content:
            print("[FINAL] Model returned empty content")
            print(
                "[FINAL] Finish reason:",
                response.choices[0].finish_reason
            )
            print(
                "[FINAL] Usage:",
                response.usage
            )
            return ""

        print(
            f"[FINAL] Summary generated: "
            f"{len(content)} characters"
        )

        return content.strip()

    except Exception as e:
        print(
            "[FINAL] Hugging Face error:",
            repr(e)
        )
        return ""