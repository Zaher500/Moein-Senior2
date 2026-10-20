from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from .export_utils import generate_pdf, generate_word

from .rabbitmq import send_to_queue
from .serializers import LectureTextSerializer
from .db.mongo import get_summary_by_lecture_id, is_summary_ready , save_extracted_text
from .auth_helpers import get_user_from_headers


class LectureTextAPIView(APIView):
    def post(self, request):
        print("Summarization request received")

        user_data = get_user_from_headers(request)
        user_id = user_data.get("user_id")
        student_id = user_data.get("student_id")

        if not user_id:
            return Response(
                {"error": "Missing user ID"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = LectureTextSerializer(data=request.data)

        if not serializer.is_valid():
            print("Validation errors:", serializer.errors)
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        lecture_id = serializer.validated_data["lecture_id"]
        text = serializer.validated_data["text"]

        text = text.replace("\x00", "").strip()

        if not student_id:
            return Response(
                {"error": "Missing student ID"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not text:
            return Response(
                {"error": "Lecture text is empty"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Save extracted text to MongoDB
        save_extracted_text(
            lecture_id=str(lecture_id),
            extracted_text=text,
            student_id=str(student_id)
        )

        print(f"Extracted text saved for lecture {lecture_id}")

        # Send text to RabbitMQ for summarization
        send_to_queue({
            "lecture_id": str(lecture_id),
            "text": text,
            "user_id": user_id,
            "student_id": str(student_id)
        })

        return Response(
            {
                "message": "Text received and sent to queue",
                "lecture_id": str(lecture_id),
                "user_id": user_id
            },
            status=status.HTTP_202_ACCEPTED
        )



class SummaryStatusAPIView(APIView):
    def get(self, request, lecture_id):
        ready = is_summary_ready(lecture_id)

        return Response(
            {"lecture_id": lecture_id, "ready": ready}, status=status.HTTP_200_OK
        )


class SummaryRetrieveAPIView(APIView):
    def get(self, request, lecture_id):
        summary_doc = get_summary_by_lecture_id(lecture_id)

        if not summary_doc:
            return Response(
                {"error": "Summary not ready", "lecture_id": lecture_id},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"lecture_id": lecture_id, "summary": summary_doc.get("summary_text")},
            status=status.HTTP_200_OK,
        )

class SummaryPDFExportAPIView(APIView):

    def get(self, request, lecture_id):

        summary_doc = get_summary_by_lecture_id(lecture_id)

        if not summary_doc:
            return Response(
                {
                    "error": "Summary not ready",
                    "lecture_id": lecture_id
                },
                status=status.HTTP_404_NOT_FOUND
            )

        summary_text = summary_doc.get("summary_text", "")

        if not summary_text:
            return Response(
                {
                    "error": "Summary is empty"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        pdf_buffer = generate_pdf(summary_text)

        response = HttpResponse(
            pdf_buffer.getvalue(),
            content_type="application/pdf"
        )

        response["Content-Disposition"] = (
            f'attachment; filename="summary_{lecture_id}.pdf"'
        )

        return response


class SummaryWordExportAPIView(APIView):

    def get(self, request, lecture_id):

        summary_doc = get_summary_by_lecture_id(lecture_id)

        if not summary_doc:
            return Response(
                {
                    "error": "Summary not ready",
                    "lecture_id": lecture_id
                },
                status=status.HTTP_404_NOT_FOUND
            )

        summary_text = summary_doc.get("summary_text", "")

        if not summary_text:
            return Response(
                {
                    "error": "Summary is empty"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        word_buffer = generate_word(summary_text)

        response = HttpResponse(
            word_buffer.getvalue(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        )

        response["Content-Disposition"] = (
            f'attachment; filename="summary_{lecture_id}.docx"'
        )

        return response














































































