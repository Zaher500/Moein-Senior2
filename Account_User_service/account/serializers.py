from rest_framework import serializers
from .models import User, Student

class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True, min_length=6)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password', 'password_confirm']
    
    def validate(self, data):
        # Check if passwords match
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        
        # Check if username already exists
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError("Username already exists")
        
        # Check if email already exists
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError("Email already exists")
        
        return data
    
    def create(self, validated_data):
        # Remove password_confirm from validated data
        validated_data.pop('password_confirm')
        
        # Create user
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            phone=validated_data.get('phone', '')
        )
        
        # Set hashed password
        user.set_password(validated_data['password'])
        user.save()
        
        # Create student profile automatically
        Student.objects.create(user_id=user)
        
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'username', 'email', 'phone', 'created_at']

# login
class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    
    def validate(self, data):
        username = data.get('username')
        password = data.get('password')
        
        # Check if user exists
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid username or password")
        
        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError("Invalid username or password")

        # Reject inactive accounts
        if not user.is_active:
            raise serializers.ValidationError("Account is deactivated")

        # Add user to validated data
        data['user'] = user
        return data


class EditAccountSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=6)
    password_confirm = serializers.CharField(write_only=True, required=False, min_length=6)

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'password', 'password_confirm']

    def validate(self, data):
        user = self.context.get('auth_user')

        if not user:
            raise serializers.ValidationError("Authentication required")

        if 'username' in data:
            if User.objects.exclude(user_id=user.user_id).filter(username=data['username']).exists():
                raise serializers.ValidationError("Username already exists")

        if 'email' in data:
            if User.objects.exclude(user_id=user.user_id).filter(email=data['email']).exists():
                raise serializers.ValidationError("Email already exists")

        if 'password' in data or 'password_confirm' in data:
            if data.get('password') != data.get('password_confirm'):
                raise serializers.ValidationError("Passwords don't match")

        return data

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        validated_data.pop('password_confirm', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


class DeleteAccountSerializer(serializers.Serializer):

    password = serializers.CharField(write_only=True, required=True)
    
    def validate(self, data):
        user = self.context['request'].user
        password = data.get('password')
        
        # Verify password
        if not user.check_password(password):
            raise serializers.ValidationError("Incorrect password")
        return data

