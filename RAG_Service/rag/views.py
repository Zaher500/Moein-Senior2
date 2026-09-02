from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import HasInternalServiceKey
from .serializers import IngestLectureSerializer, RetrieveContextSerializer
from .services.lecture_ingestion_service import LectureIngestionService
from .services.rag_service import RAGService


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response(
            {
                "service": "rag",
                "status": "ok",
            }
        )


class RetrieveContextView(APIView):
    authentication_classes = []
    permission_classes = [HasInternalServiceKey]

    def post(self, request):
        serializer = RetrieveContextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = RAGService.retrieve_context(
            student_id=serializer.validated_data["student_id"],
            query=serializer.validated_data["query"],
            course_id=serializer.validated_data.get("course_id"),
            lecture_id=serializer.validated_data.get("lecture_id"),
            top_k=serializer.validated_data["top_k"],
        )

        return Response(result, status=status.HTTP_200_OK)


class IngestLectureView(APIView):
    authentication_classes = []
    permission_classes = [HasInternalServiceKey]

    def post(self, request):
        serializer = IngestLectureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = LectureIngestionService.ingest_lecture_text(
            lecture_text=serializer.validated_data["lecture_text"],
            lecture_id=serializer.validated_data["lecture_id"],
            course_id=serializer.validated_data["course_id"],
            student_id=serializer.validated_data["student_id"],
            source_type=serializer.validated_data["source_type"],
        )

        return Response(result, status=status.HTTP_201_CREATED)
