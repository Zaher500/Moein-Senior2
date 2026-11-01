from rest_framework import serializers
from .models import Quiz, Question, QuizAttempt, Answer


class QuestionSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = '__all__'

    def get_options(self, obj):
        if obj.options:
            return [opt.strip() for opt in obj.options.split('|')]
        return []

    def validate(self, data):
        question_type = data.get('question_type')
        options_str = data.get('options')
        correct_answer = data.get('correct_answer')

        if question_type == 'MCQ':
            if not options_str:
                raise serializers.ValidationError({"options": "MCQ questions must have options."})

            options_list = [opt.strip() for opt in options_str.split('|')]

            if len(options_list) != 4:
                raise serializers.ValidationError({"options": "MCQ must have exactly 4 options separated by a pipe (|)."})

            if correct_answer not in options_list:
                raise serializers.ValidationError({"correct_answer": "Correct answer must exactly match one of the options."})

        return data


class StudentQuestionSerializer(QuestionSerializer):
    """Expose only safe question fields to students."""

    class Meta(QuestionSerializer.Meta):
        fields = [
            'question_id',
            'question_type',
            'question_text',
            'options',
            'order',
        ]


class QuizSerializer(serializers.ModelSerializer):
    questions = StudentQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'quiz_id',
            'lecture_id',
            'course_id',
            'student_id',
            'title',
            'source',
            'status',
            'error',
            'num_questions',
            'difficulty',
            'created_at',
            'updated_at',
            'questions',
        ]


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = '__all__'


class QuizAttemptSerializer(serializers.ModelSerializer):
    answers = AnswerSerializer(many=True, read_only=True)

    class Meta:
        model = QuizAttempt
        fields = '__all__'
