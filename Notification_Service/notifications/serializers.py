from rest_framework import serializers


class SendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)
    username = serializers.CharField(required=False, allow_blank=True)