import re
from study_plan.db.mongo import get_extracted_text ,get_saved_lecture_analysis, save_lecture_analysis

import os
from typing import Literal
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

load_dotenv()
ANALYZER_VERSION = "v1"
def analyze_lecture(lecture_id: str, student_id: str):
    """
    Prepare lecture content for AI analysis.
    """

    # 1. Retrieve extracted text from MongoDB
    extracted_text = get_extracted_text(
        lecture_id=lecture_id,
        student_id=student_id
    )

    if not extracted_text or not extracted_text.strip():
        raise ValueError(
            "Extracted text not found for this lecture."
        )

    # 2. Detect lecture pages
    pages = re.findall(
        r"^===== PAGE (\d+) =====",
        extracted_text,
        flags=re.MULTILINE
    )

    # 3. Prepare lecture information
    lecture_data = {
        "lecture_id": str(lecture_id),
        "page_count": len(set(pages)),
        "text_length": len(extracted_text),
        "content": extracted_text
    }

    return lecture_data




class LectureTopic(BaseModel):
    name: str
    page_numbers: list[int]
    difficulty: Literal["easy", "medium", "hard"]
    importance: Literal["low", "medium", "high"]
    estimated_study_minutes: int = Field(ge=5, le=180)




class LectureAnalysis(BaseModel):
    lecture_title: str
    topics: list[LectureTopic]
    key_concepts: list[str]
    difficulty: Literal["easy", "medium", "hard"]
    important_diagrams: list[str]
    study_recommendations: list[str]



def analyze_lecture_with_gemini(
    lecture_id: str,
    student_id: str
):
    # 1. Get lecture content from MongoDB
    lecture_data = analyze_lecture(
        lecture_id=lecture_id,
        student_id=student_id
    )

    extracted_text = lecture_data["content"]

    # Check if an up-to-date analysis already exists
    model_name = os.getenv("GEMINI_MODEL")

    if not model_name:
        raise RuntimeError("GEMINI_MODEL is missing")

    saved_analysis = get_saved_lecture_analysis(
        lecture_id=lecture_id,
        student_id=student_id,
        extracted_text=extracted_text,
        model_name=model_name,
        analyzer_version=ANALYZER_VERSION
    )

    if saved_analysis is not None:
        print("Using cached lecture analysis")

        return {
            **saved_analysis,
            "analysis_source": "cache"
        }


    # 2. Prepare Gemini prompt
    prompt = f"""
You are an educational lecture analyzer
for the Moein AI Student Assistant.

Analyze the provided original lecture content
for personalized study planning.

Instructions:
- Extract the actual educational topics.
- Ignore repeated OCR text.
- Ignore university logos and decorative elements.
- Ignore irrelevant visual descriptions.
- Preserve important diagrams and relationships.
- Identify important concepts students must understand.
- Do not invent information.
- Do not include topics that are only mentioned
  in a course outline but not actually taught.
- Use the PAGE markers to identify topic page numbers.
- Estimate difficulty based on the lecture content.
- Estimate study time in minutes for an average student.
- Recommend suitable study activities.
- Preserve the lecture's technical terminology.
- Classify each topic's importance as low, medium, or high.
- Assign an estimated study time in minutes to each topic.
- Include time for understanding and a brief review.
- Give course introductions and overviews less study time.
- Give important and difficult concepts more study time.
- Do not inflate study time because of repeated OCR content.
- Do not treat references or next-lecture announcements
  as topics taught in this lecture.
- Study time estimates are approximate.

LECTURE CONTENT:
{extracted_text}
"""

    # 3. Initialize Gemini
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    client = genai.Client(api_key=api_key)

    try:
        # 4. Analyze lecture
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LectureAnalysis,
                temperature=0.2
            )
        )

        if not response.text:
            raise RuntimeError(
                "Gemini returned an empty response"
            )

        # 5. Validate JSON output
        analysis = LectureAnalysis.model_validate_json(
            response.text
        )
        # 6. Calculate total estimated study time
        if not analysis.topics:
            raise ValueError("No study topics were extracted.")

        total_study_minutes = sum(
            topic.estimated_study_minutes
            for topic in analysis.topics
        )
        # 7. Prepare analysis result
        analysis_result = {
            "lecture_id": str(lecture_id),
            "page_count": lecture_data["page_count"],
            **analysis.model_dump(),
            "estimated_study_minutes": total_study_minutes
        }

        # 8. Save analysis in MongoDB
        save_lecture_analysis(
            lecture_id=lecture_id,
            student_id=student_id,
            extracted_text=extracted_text,
            model_name=model_name,
            analysis=analysis_result,
            analyzer_version=ANALYZER_VERSION
        )

        print("New lecture analysis saved in MongoDB")

        return {
            **analysis_result,
            "analysis_source": "gemini"
        }

        f

    finally:
        client.close()
