from rest_framework import serializers


class RetrieveContextSerializer(serializers.Serializer):
    student_id = serializers.CharField()
    query = serializers.CharField(allow_blank=True)
    course_id = serializers.CharField(required=False, allow_null=True)
    lecture_id = serializers.CharField(required=False, allow_null=True)
    top_k = serializers.IntegerField(
        required=False,
        default=5,
        min_value=1,
    )


class IngestLectureSerializer(serializers.Serializer):
    lecture_text = serializers.CharField()
    lecture_id = serializers.CharField()
    course_id = serializers.CharField()
    student_id = serializers.CharField()
    source_type = serializers.CharField(
        required=False,
        default="lecture",
    )
