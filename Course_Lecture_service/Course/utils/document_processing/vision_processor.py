# import base64
# import mimetypes
# import os
# from pathlib import Path
# import json
# from huggingface_hub import InferenceClient
# from dotenv import load_dotenv
# load_dotenv()


# # Load .env if it exists.
# # If HF_TOKEN is already set in PowerShell,
# # os.getenv() will read it normally.

# class VisionProcessor:
#     """
#     Visual understanding using Qwen3-VL
#     through Hugging Face Inference Providers.

#     Responsibilities:
#     - understand diagrams
#     - understand flowcharts
#     - understand charts
#     - understand infographics
#     - explain visual relationships

#     OCR text is passed only as supporting evidence.
#     """

#     MODEL_NAME = "Qwen/Qwen3-VL-8B-Instruct"

#     def __init__(self):

#         api_key = os.getenv("HF_TOKEN")

#         if not api_key:
#             raise ValueError(
#                 "HF_TOKEN environment variable was not found."
#             )

#         self.client = InferenceClient(
#             provider="featherless-ai",
#             api_key=api_key,
#             timeout=120,
#         )

#     def process_image(
#         self,
#         image_path: str,
#         visible_text: list[str] | None = None,
#     ) -> dict:
#         """
#         Analyze one educational image.

#         Args:
#             image_path:
#                 Path to extracted image.

#             visible_text:
#                 OCR text previously extracted
#                 by PaddleOCR.

#         Returns:
#             {
#                 "description": "...",
#                 "relationships": []
#             }
#         """

#         path = Path(image_path)

#         # =====================================================
#         # Validate image
#         # =====================================================

#         if not path.exists():
#             raise FileNotFoundError(
#                 f"Image not found: {image_path}"
#             )

#         if not path.is_file():
#             raise ValueError(
#                 f"Path is not a file: {image_path}"
#             )

#         # =====================================================
#         # Convert image to Base64 data URL
#         # =====================================================

#         image_url = self._image_to_data_url(
#             path
#         )

#         # =====================================================
#         # Prepare OCR context
#         # =====================================================

#         ocr_text = ""

#         if visible_text:
#             ocr_text = "\n".join(
#                 visible_text
#             )

#         prompt = self._build_prompt(
#             ocr_text
#         )

#         # =====================================================
#         # Send image + OCR text to Qwen3-VL
#         # =====================================================

#         try:

#             response = (
#                 self.client.chat.completions.create(
#                     model=self.MODEL_NAME,
#                     messages=[
#                         {
#                             "role": "user",
#                             "content": [
#                                 {
#                                     "type": "image_url",
#                                     "image_url": {
#                                         "url": image_url
#                                     },
#                                 },
#                                 {
#                                     "type": "text",
#                                     "text": prompt,
#                                 },
#                             ],
#                         }
#                     ],
#                     max_tokens=1200,
#                     temperature=0.1,
#                 )
#             )

#         except Exception as e:

#             raise RuntimeError(
#                 f"Vision processing failed for "
#                 f"'{image_path}': {str(e)}"
#             ) from e

#         # =====================================================
#         # Read model response
#         # =====================================================

#         raw_response = (
#     response
#     .choices[0]
#     .message
#     .content
# )

#         if not raw_response:
#             return {
#                 "description": "",
#                 "relationships": [],
#             }

#         cleaned_response = raw_response.strip()

#         if cleaned_response.startswith("```json"):
#             cleaned_response = cleaned_response[7:]

#         if cleaned_response.startswith("```"):
#             cleaned_response = cleaned_response[3:]

#         if cleaned_response.endswith("```"):
#             cleaned_response = cleaned_response[:-3]

#         cleaned_response = cleaned_response.strip()

#         try:
#             parsed = json.loads(cleaned_response)

#         except json.JSONDecodeError as e:
#             raise RuntimeError(
#                 f"Qwen returned invalid JSON: {cleaned_response}"
#             ) from e

#         return {
#             "description": str(
#                 parsed.get("description", "")
#             ).strip(),

#             "relationships": [
#                 str(item).strip()
#                 for item in parsed.get(
#                     "relationships",
#                     []
#                 )
#                 if str(item).strip()
#             ],
#         }

#     def _image_to_data_url(
#         self,
#         path: Path,
#     ) -> str:
#         """
#         Convert a local image into a Base64
#         data URL accepted by the HF multimodal API.
#         """

#         mime_type, _ = mimetypes.guess_type(
#             str(path)
#         )

#         if not mime_type:
#             mime_type = "image/png"

#         with open(
#             path,
#             "rb",
#         ) as image_file:

#             encoded = base64.b64encode(
#                 image_file.read()
#             ).decode("utf-8")

#         return (
#             f"data:{mime_type};"
#             f"base64,{encoded}"
#         )

#     def _build_prompt(
#     self,
#     ocr_text: str,
# ) -> str:

#      return f"""
# You are analyzing a visual element extracted from an educational lecture.

# The image may contain one or more:
# - diagrams
# - flowcharts
# - charts or graphs
# - tables
# - timelines
# - hierarchies
# - comparisons
# - process models
# - scientific figures
# - technical illustrations
# - screenshots
# - formulas
# - infographics
# - labeled images
# - structured text regions

# OCR has already been performed.

# --- OCR TEXT ---
# {ocr_text}
# --- END OCR TEXT ---

# IMPORTANT RULES:

# 1. The IMAGE is the primary source of truth.
#    OCR is supporting evidence only and may contain recognition errors.

# 2. First identify the visual regions of the image.
#    Examples:
#    - left / right panels
#    - top / bottom sections
#    - columns
#    - groups
#    - branches
#    - versions
#    - categories
#    - separate diagrams

# 3. Analyze each visually distinct region independently BEFORE comparing
#    or connecting information across regions.

# 4. NEVER merge labels, values, stages, names, descriptions, or concepts
#    that belong to different visual regions.

# 5. When the image compares multiple versions, methods, categories,
#    alternatives, or sides:
#    - keep each side separate
#    - identify the contents of each side independently
#    - then explain similarities and differences

# 6. Preserve associations between labels and the visual objects,
#    rows, columns, boxes, branches, or regions they belong to.

# 7. Identify visually supported relationships such as:
#    - hierarchy
#    - sequence
#    - progression
#    - dependency
#    - cause and effect
#    - parent-child
#    - grouping
#    - comparison
#    - input/output

#     Relationships should be explicit and self-contained.

#    Prefer:
#    "Component A belongs to Section B."

#    Instead of:
#    "Component A is related to Section B."

# 8. If arrows, connectors, paths, or lines exist:
#    explain what they connect and their direction.

# 9. If the image is a flowchart or process:
#    explain the order of steps and transitions.

# 10. If the image is a hierarchy:
#     explain the levels and which elements belong to each level.

# 11. If the image is a chart or graph:
#     identify axes, legends, categories, trends, and comparisons
#     only when they are visually supported.

# 12. If the image is a table:
#     preserve only clearly visible table structure and associations.

#     Identify clearly readable:
#     - table title
#     - row labels
#     - column headers
#     - section or group labels
#     - individual cell values only when their exact position is clear

#     For dense tables, matrices, or partially readable tables:
#     - do NOT extrapolate patterns across rows or columns
#     - do NOT complete missing numeric sequences
#     - do NOT assume that every cell is populated
#     - do NOT infer the semantic meaning of numeric values unless
#       the table explicitly states what those values represent
#     - do NOT infer the semantic role of a standalone label
#       unless that role is explicitly stated or visually unambiguous
#     - do NOT infer meaning from colors unless a visible legend
#       explicitly defines that meaning
#     - prefer describing the table structure and readable labels
#       instead of producing uncertain per-cell relationships

#     Report a row-to-column value relationship only when every reported
#     value and its exact cell position are clearly readable in the image.

#     If cell-level information is uncertain, omit those relationships
#     rather than guessing or completing them.

# 13. Do NOT assume that two items are equivalent just because they appear
#     at the same vertical or horizontal position.

# 14. Do NOT assume that two panels contain the same labels or stages.
#     Verify each panel independently from the image.

# 15. Use spatial position only when it clearly contributes to meaning.

# 16. Do not invent missing facts, labels, relationships, values,
#     similarities, or differences.

# 17. If something is unclear or ambiguous, omit it rather than guessing.

# 18. OCR text may contain recognition errors.
#     Use the IMAGE as the source of truth for both structure
#     and visually readable labels.

#     If an OCR label is clearly corrupted but the correct label
#     is clearly readable in the image, use the label visible
#     in the image.

#     If the label cannot be read reliably from the image,
#     do not guess or correct it.

# 19. Do not claim that two regions contain the same labels, values,
#     stages, or categories unless this is clearly visible in the image.

# 20. When exact labels differ between regions, preserve that distinction.
#     Do not generalize one region's labels to another region.

# - For grouped layouts such as quadrants, columns, sections, clusters,
#   tables, or labeled regions, explicitly state which visible items
#   belong to each group when the visual association is clear.

# - For each clearly labeled group, section, quadrant, column, or region,
#   explicitly identify all clearly readable items that belong to it
#   before describing relationships between different groups.

# - Do not leave group membership implicit only in the description.
#   Express important memberships explicitly in "relationships".

# - When a label or phrase is visually split across multiple lines,
#   reconstruct it as one item only when those lines clearly belong
#   together in the same visual region.

# - When arrows or connectors are merely decorative and do not encode
#   a clear semantic relationship, prioritize explicit group membership
#   and educational structure.

# - For dense tables or matrices, do not extrapolate a repeated pattern
#   across rows or columns.

# - Report a row-to-column value relationship only when the specific
#   cell association is clearly visible in the image.

# - If individual cell values cannot be read reliably, describe the
#   table structure and readable labels without inventing or completing
#   the missing cell relationships.

# Your goal is to capture the educational meaning and visual structure
# accurately and conservatively.

# Return ONLY valid JSON in exactly this format:

# {{
#     "description": "A concise but complete explanation of the visual content, keeping distinct regions separate when needed.",
#     "relationships": [
#         "A specific visually supported relationship",
#         "Another specific visually supported relationship"
#     ]
# }}

# If there are no meaningful visual relationships,
# return an empty relationships list.

# Do not return Markdown.
# Do not return code fences.
# Do not return any text outside the JSON.
# """.strip()












import base64
import mimetypes
import os
import json
import time
from pathlib import Path

from huggingface_hub import InferenceClient
from dotenv import load_dotenv


load_dotenv()


class InvalidVisionJSONError(Exception):
    """
    Raised when the Vision model returns text
    that cannot be parsed as the expected JSON.
    """

    pass


class VisionProcessor:
    """
    Visual understanding using Qwen3-VL
    through Hugging Face Inference Providers.

    Responsibilities:
    - understand diagrams
    - understand flowcharts
    - understand charts
    - understand infographics
    - explain visual relationships

    OCR text is passed only as supporting evidence.
    """

    MODEL_NAME = "Qwen/Qwen3-VL-8B-Instruct"

    MAX_ATTEMPTS = 2

    def __init__(self):

        api_key = os.getenv("HF_TOKEN")

        if not api_key:
            raise ValueError(
                "HF_TOKEN environment variable was not found."
            )

        self.client = InferenceClient(
            provider="featherless-ai",
            api_key=api_key,
            timeout=120,
        )

    def process_image(
        self,
        image_path: str,
        visible_text: list[str] | None = None,
    ) -> dict:
        """
        Analyze one educational image.

        The Vision request is attempted once normally.

        If the first request fails because of:
        - invalid JSON
        - incomplete response
        - temporary connection/provider error

        one retry is performed with temperature=0.0
        and a stricter JSON instruction.

        Permanent errors such as authentication,
        payment, permission, or bad-request errors
        are not retried.

        Args:
            image_path:
                Path to extracted image.

            visible_text:
                OCR text previously extracted
                by PaddleOCR.

        Returns:
            {
                "description": "...",
                "relationships": []
            }
        """

        path = Path(image_path)

        # =====================================================
        # Validate image
        # =====================================================

        if not path.exists():
            raise FileNotFoundError(
                f"Image not found: {image_path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Path is not a file: {image_path}"
            )

        # =====================================================
        # Convert image to Base64 data URL
        # =====================================================

        image_url = self._image_to_data_url(
            path
        )

        # =====================================================
        # Prepare OCR context
        # =====================================================

        ocr_text = ""

        if visible_text:
            ocr_text = "\n".join(
                visible_text
            )

        base_prompt = self._build_prompt(
            ocr_text
        )

        # =====================================================
        # Vision call with ONE retry
        # =====================================================

        last_error = None

        for attempt in range(
            1,
            self.MAX_ATTEMPTS + 1,
        ):

            is_retry = attempt > 1

            temperature = (
                0.0
                if is_retry
                else 0.1
            )

            prompt = base_prompt

            if is_retry:
                prompt = (
                    base_prompt
                    + "\n\n"
                    + self._build_retry_instruction()
                )

            try:

                response = self._send_request(
                    image_url=image_url,
                    prompt=prompt,
                    temperature=temperature,
                )

                raw_response = (
                    response
                    .choices[0]
                    .message
                    .content
                )

                if not raw_response:
                    return {
                        "description": "",
                        "relationships": [],
                    }

                parsed = self._parse_response(
                    raw_response
                )

                return self._normalize_result(
                    parsed
                )

            except Exception as e:

                last_error = e

                # ---------------------------------------------
                # Do NOT retry permanent errors
                # ---------------------------------------------

                if self._is_non_retryable_error(e):

                    raise RuntimeError(
                        f"Vision processing failed for "
                        f"'{image_path}': {str(e)}"
                    ) from e

                # ---------------------------------------------
                # Retry only once
                # ---------------------------------------------

                if attempt < self.MAX_ATTEMPTS:

                    print(
                        f"[VISION RETRY] "
                        f"image={image_path} "
                        f"attempt={attempt + 1}/"
                        f"{self.MAX_ATTEMPTS} "
                        f"reason={self._short_error(e)}"
                    )

                    # Small delay for temporary
                    # provider/network problems.
                    time.sleep(1)

                    continue

                # ---------------------------------------------
                # Second attempt also failed
                # ---------------------------------------------

                raise RuntimeError(
                    f"Vision processing failed after "
                    f"{self.MAX_ATTEMPTS} attempts for "
                    f"'{image_path}': {str(e)}"
                ) from e

        # Safety fallback.
        # Normally unreachable.
        raise RuntimeError(
            f"Vision processing failed for "
            f"'{image_path}': {str(last_error)}"
        )

    def _send_request(
        self,
        image_url: str,
        prompt: str,
        temperature: float,
    ):
        """
        Send one multimodal request to Qwen3-VL.
        """

        return (
            self.client.chat.completions.create(
                model=self.MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
                max_tokens=1200,
                temperature=temperature,
            )
        )

    def _parse_response(
        self,
        raw_response: str,
    ) -> dict:
        """
        Clean and parse the model response
        as strict JSON.
        """

        cleaned_response = (
            raw_response.strip()
        )

        if cleaned_response.startswith(
            "```json"
        ):
            cleaned_response = (
                cleaned_response[7:]
            )

        if cleaned_response.startswith(
            "```"
        ):
            cleaned_response = (
                cleaned_response[3:]
            )

        if cleaned_response.endswith(
            "```"
        ):
            cleaned_response = (
                cleaned_response[:-3]
            )

        cleaned_response = (
            cleaned_response.strip()
        )

        try:

            parsed = json.loads(
                cleaned_response
            )

        except json.JSONDecodeError as e:

            raise InvalidVisionJSONError(
                "Qwen returned invalid JSON: "
                f"{cleaned_response}"
            ) from e

        if not isinstance(parsed, dict):

            raise InvalidVisionJSONError(
                "Qwen returned valid JSON, "
                "but the top-level value "
                "is not an object."
            )

        return parsed

    def _normalize_result(
        self,
        parsed: dict,
    ) -> dict:
        """
        Normalize the parsed JSON into the
        structure expected by the pipeline.
        """

        description = str(
            parsed.get(
                "description",
                "",
            )
        ).strip()

        raw_relationships = (
            parsed.get(
                "relationships",
                [],
            )
        )

        if not isinstance(
            raw_relationships,
            list,
        ):
            raw_relationships = []

        relationships = [
            str(item).strip()
            for item in raw_relationships
            if str(item).strip()
        ]

        return {
            "description": description,
            "relationships": relationships,
        }

    def _is_non_retryable_error(
        self,
        error: Exception,
    ) -> bool:
        """
        Return True for errors where retrying
        the same request is unlikely to help.

        Examples:
        - 400 Bad Request
        - 401 Unauthorized
        - 402 Payment Required
        - 403 Forbidden
        - 404 Not Found
        """

        status_code = None

        # Some Hugging Face / HTTP exceptions
        # expose status_code directly.
        if hasattr(
            error,
            "status_code",
        ):
            status_code = getattr(
                error,
                "status_code",
                None,
            )

        # HfHubHTTPError usually stores the
        # HTTP response here.
        response = getattr(
            error,
            "response",
            None,
        )

        if (
            status_code is None
            and response is not None
        ):
            status_code = getattr(
                response,
                "status_code",
                None,
            )

        if status_code in {
            400,
            401,
            402,
            403,
            404,
        }:
            return True

        error_text = str(
            error
        ).lower()

        permanent_markers = [
            "400 bad request",
            "401 unauthorized",
            "402 payment required",
            "403 forbidden",
            "404 not found",
            "depleted your monthly included credits",
            "insufficient credits",
            "unauthorized",
            "invalid token",
            "authentication failed",
        ]

        return any(
            marker in error_text
            for marker in permanent_markers
        )

    def _short_error(
        self,
        error: Exception,
    ) -> str:
        """
        Create a short log-friendly error message.
        Avoid printing huge malformed model outputs.
        """

        text = str(
            error
        ).replace(
            "\n",
            " ",
        ).strip()

        max_length = 220

        if len(text) > max_length:
            return (
                text[:max_length]
                + "..."
            )

        return text

    def _build_retry_instruction(
        self,
    ) -> str:
        """
        Extra instruction used only on
        the second Vision attempt.
        """

        return """
RETRY REQUIREMENT:

The previous attempt failed because the response was invalid,
incomplete, or could not be processed.

Return ONLY one complete valid JSON object matching the required schema.

Do not return Markdown.
Do not return code fences.
Do not include comments.
Do not include explanations outside the JSON object.
Do not output partial JSON.

The response must begin with {
and end with }.
""".strip()

    def _image_to_data_url(
        self,
        path: Path,
    ) -> str:
        """
        Convert a local image into a Base64
        data URL accepted by the HF multimodal API.
        """

        mime_type, _ = mimetypes.guess_type(
            str(path)
        )

        if not mime_type:
            mime_type = "image/png"

        with open(
            path,
            "rb",
        ) as image_file:

            encoded = base64.b64encode(
                image_file.read()
            ).decode("utf-8")

        return (
            f"data:{mime_type};"
            f"base64,{encoded}"
        )

    def _build_prompt(
        self,
        ocr_text: str,
    ) -> str:

        return f"""
You are analyzing a visual element extracted from an educational lecture.

The image may contain one or more:
- diagrams
- flowcharts
- charts or graphs
- tables
- timelines
- hierarchies
- comparisons
- process models
- scientific figures
- technical illustrations
- screenshots
- formulas
- infographics
- labeled images
- structured text regions

OCR has already been performed.

--- OCR TEXT ---
{ocr_text}
--- END OCR TEXT ---

IMPORTANT RULES:

1. The IMAGE is the primary source of truth.
   OCR is supporting evidence only and may contain recognition errors.

2. First identify the visual regions of the image.
   Examples:
   - left / right panels
   - top / bottom sections
   - columns
   - groups
   - branches
   - versions
   - categories
   - separate diagrams

3. Analyze each visually distinct region independently BEFORE comparing
   or connecting information across regions.

4. NEVER merge labels, values, stages, names, descriptions, or concepts
   that belong to different visual regions.

5. When the image compares multiple versions, methods, categories,
   alternatives, or sides:
   - keep each side separate
   - identify the contents of each side independently
   - then explain similarities and differences

6. Preserve associations between labels and the visual objects,
   rows, columns, boxes, branches, or regions they belong to.

7. Identify visually supported relationships such as:
   - hierarchy
   - sequence
   - progression
   - dependency
   - cause and effect
   - parent-child
   - grouping
   - comparison
   - input/output

   Relationships should be explicit and self-contained.

   Prefer:
   "Component A belongs to Section B."

   Instead of:
   "Component A is related to Section B."

8. If arrows, connectors, paths, or lines exist:
   explain what they connect and their direction.

9. If the image is a flowchart or process:
   explain the order of steps and transitions.

10. If the image is a hierarchy:
    explain the levels and which elements belong to each level.

11. If the image is a chart or graph:
    identify axes, legends, categories, trends, and comparisons
    only when they are visually supported.

12. If the image is a table:
    preserve only clearly visible table structure and associations.

    Identify clearly readable:
    - table title
    - row labels
    - column headers
    - section or group labels
    - individual cell values only when their exact position is clear

    For dense tables, matrices, or partially readable tables:
    - do NOT extrapolate patterns across rows or columns
    - do NOT complete missing numeric sequences
    - do NOT assume that every cell is populated
    - do NOT infer the semantic meaning of numeric values unless
      the table explicitly states what those values represent
    - do NOT infer the semantic role of a standalone label
      unless that role is explicitly stated or visually unambiguous
    - do NOT infer meaning from colors unless a visible legend
      explicitly defines that meaning
    - prefer describing the table structure and readable labels
      instead of producing uncertain per-cell relationships

    Report a row-to-column value relationship only when every reported
    value and its exact cell position are clearly readable in the image.

    If cell-level information is uncertain, omit those relationships
    rather than guessing or completing them.

13. Do NOT assume that two items are equivalent just because they appear
    at the same vertical or horizontal position.

14. Do NOT assume that two panels contain the same labels or stages.
    Verify each panel independently from the image.

15. Use spatial position only when it clearly contributes to meaning.

16. Do not invent missing facts, labels, relationships, values,
    similarities, or differences.

17. If something is unclear or ambiguous, omit it rather than guessing.

18. OCR text may contain recognition errors.
    Use the IMAGE as the source of truth for both structure
    and visually readable labels.

    If an OCR label is clearly corrupted but the correct label
    is clearly readable in the image, use the label visible
    in the image.

    If the label cannot be read reliably from the image,
    do not guess or correct it.

19. Do not claim that two regions contain the same labels, values,
    stages, or categories unless this is clearly visible in the image.

20. When exact labels differ between regions, preserve that distinction.
    Do not generalize one region's labels to another region.

- For grouped layouts such as quadrants, columns, sections, clusters,
  tables, or labeled regions, explicitly state which visible items
  belong to each group when the visual association is clear.

- For each clearly labeled group, section, quadrant, column, or region,
  explicitly identify all clearly readable items that belong to it
  before describing relationships between different groups.

- Do not leave group membership implicit only in the description.
  Express important memberships explicitly in "relationships".

- When a label or phrase is visually split across multiple lines,
  reconstruct it as one item only when those lines clearly belong
  together in the same visual region.

- When arrows or connectors are merely decorative and do not encode
  a clear semantic relationship, prioritize explicit group membership
  and educational structure.

- For dense tables or matrices, do not extrapolate a repeated pattern
  across rows or columns.

- Report a row-to-column value relationship only when the specific
  cell association is clearly visible in the image.

- If individual cell values cannot be read reliably, describe the
  table structure and readable labels without inventing or completing
  the missing cell relationships.

Your goal is to capture the educational meaning and visual structure
accurately and conservatively.

Return ONLY valid JSON in exactly this format:

{{
    "description": "A concise but complete explanation of the visual content, keeping distinct regions separate when needed.",
    "relationships": [
        "A specific visually supported relationship",
        "Another specific visually supported relationship"
    ]
}}

If there are no meaningful visual relationships,
return an empty relationships list.

Do not return Markdown.
Do not return code fences.
Do not return any text outside the JSON.
""".strip()