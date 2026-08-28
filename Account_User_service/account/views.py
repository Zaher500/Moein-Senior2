from django.utils import timezone   #A
from datetime import timedelta   #A
from django.contrib.auth.hashers import make_password   #A  

from .models import PendingRegistration    #A
from .services import generate_otp, send_otp   #A
from django.contrib.auth.hashers import check_password  #A
from django.db import transaction           #A
import requests
from rest_framework import status, exceptions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import User, Student
from .serializers import (
    DeleteAccountSerializer,
    UserLoginSerializer,
    UserSignupSerializer,
    UserSerializer,
    EditAccountSerializer
)
from .auth import create_jwt_for_user
from .jwt_utils import get_user_from_token
from django.conf import settings




@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    User registration endpoint
    Expected JSON:
    {
        "username": "john_doe",
        "email": "john@example.com", 
        "phone": "1234567890",
        "password": "password123",
        "password_confirm": "password123"
    }
    """
    serializer = UserSignupSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.save() 
        
        # Get the student profile
        student = Student.objects.get(user_id=user)
        
        return Response({
            'message': 'User created successfully. Please login to continue.',
            'user': {
                'user_id': str(user.user_id),
                'username': user.username,
                'email': user.email,
                'phone': user.phone
            },
            'student': {
                'student_id': str(student.student_id)
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    User login endpoint
    Expected JSON:
    {
        "username": "john_doe",
        "password": "password123"
    }
    """
    serializer = UserLoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        
        # Generate JWT token
        token = create_jwt_for_user(user, student=Student.objects.get(user_id=user))
        
        
        # Get student profile
        student = Student.objects.get(user_id=user)
        
        return Response({
            'message': 'Login successful',
            'token': token,
            'user': {
                'user_id': str(user.user_id),
                'username': user.username,
                'email': user.email,
                'phone': user.phone
            },
            'student': {
                'student_id': str(student.student_id)
            }
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['PUT', 'PATCH'])
def edit_account(request):
    """
    Edit authenticated user's account
    Requires: Authorization: Bearer <token>
    """
    user = get_user_from_token(request)

    if not user:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

    serializer = EditAccountSerializer(
        user,
        data=request.data,
        partial=True,
        context={
            'request': request,
            'auth_user': user,
            },
    )

    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Account updated successfully',
            'user': {
                'user_id': str(user.user_id),
                'username': user.username,
                'email': user.email,
                'phone': user.phone
            }
        }, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def delete_account(request):
    try:
        # 1) Authenticate user
        user = get_user_from_token(request)
        if not user:
            return Response({'error': 'Authentication required'}, status=401)

        # 2) Validate password
        password = request.data.get('password')
        if not password or not user.check_password(password):
            return Response({'error': 'Incorrect password'}, status=400)

        # 3) Get student's UUID
        try:
            student = Student.objects.get(user_id=user)
            student_id = str(student.student_id)  
        except Student.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=404)

        courses_deleted = False
        
        course_service_url = settings.SERVICES['course']  # DIRECT CALL to course MS
        delete_url = f"{course_service_url}/api/delete-student-courses/{student_id}/"

        headers = {
            "Authorization": request.META.get("HTTP_AUTHORIZATION", ""),
            "X-GATEWAY-SECRET": settings.GATEWAY_SECRET,
        }

        try:
            print("Sending DELETE to Course MS:", delete_url)
            resp = requests.delete(delete_url, headers=headers, timeout=10)

            print("Course delete response status:", resp.status_code)
            print("Course delete response text:", resp.text)

            courses_deleted = (resp.status_code == 200)

        except Exception as e:
            print(f"Failed to delete courses from Course MS: {e}")

        username = user.username
        user.delete()  

        return Response({
            "message": f"Account {username} deleted successfully",
            "courses_deleted": courses_deleted,
            "deleted": True,
        }, status=200)

    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
def get_current_user(request):
    """
    Get current authenticated user's information
    Requires: Authorization: Bearer <token>
    """
    user = get_user_from_token(request)
    
    if not user:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        # Get student profile
        student = Student.objects.get(user_id=user)
        
        return Response({
            'user': {
                'user_id': str(user.user_id),
                'username': user.username,
                'email': user.email,
                'phone': user.phone,
                'created_at': user.created_at
            },
            'student': {
                'student_id': str(student.student_id)
            }
        }, status=status.HTTP_200_OK)
        
    except Student.DoesNotExist:
        return Response({
            'user': {
                'user_id': str(user.user_id),
                'username': user.username,
                'email': user.email,
                'phone': user.phone,
                'created_at': user.created_at
            },
            'student': None,
            'message': 'Student profile not found'
        }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])  
def decode_token_contents(request):
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    
    if not auth_header:
        return Response({'error': 'No Authorization header'}, status=400)
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return Response({'error': 'Invalid Authorization format'}, status=400)
    
    token = parts[1]
    
    try:
        import jwt
        # Decode WITHOUT verification to see raw contents
        decoded = jwt.decode(token, options={"verify_signature": False})
        
        return Response({
            'token': token[:50] + '...' if len(token) > 50 else token,
            'token_length': len(token),
            'decoded_payload': decoded,
            'sub_field': decoded.get('sub'),
            'sub_field_type': type(decoded.get('sub')).__name__,
            'sub_field_length': len(str(decoded.get('sub', ''))),
            'all_fields': list(decoded.keys())
        })
    except Exception as e:
        return Response({'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_student_exists(request, student_id):

    """
    Check if a student (and their user account) exists
    Using: Student ID → Find Student → Find User
    """
    try:
        # 1. Find the student by student_id
        student = Student.objects.get(student_id=student_id)
        
        # 2. Get the user from the student
        user = student.user_id
        
        return Response({
            'exists': True,
            'user_id': str(user.user_id),
            'student_id': str(student.student_id),
            'username': user.username,
            'is_active': True
        })
        
    except Student.DoesNotExist:
        # Student not found = user account deleted
        return Response({
            'exists': False,
            'message': 'Student account not found'
        }, status=404)   


@api_view(['GET'])
@permission_classes([AllowAny])
def check_user_exists(request, user_id):

    """Check if user exists by user_id"""
    try:
        user = User.objects.get(user_id=user_id)
        
        # Get the student profile
        student = Student.objects.get(user_id=user)
        
        return Response({
            'exists': True,
            'user_id': str(user.user_id),
            'student_id': str(student.student_id),
            'username': user.username,
            'is_active': True
        })
        
    except User.DoesNotExist:
        return Response({'exists': False}, status=404)
    except Student.DoesNotExist:
        return Response({'exists': False}, status=404)

#A
@api_view(['POST'])
@permission_classes([AllowAny])
def register_initiate(request):
    """
    Step 1: Start registration (send OTP)
    """
    print("Received registration initiation request with data:", request.data)
    serializer = UserSignupSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    data = serializer.validated_data              # 

    username = data['username']
    email = data['email']
    password = data['password']
    phone = data['phone']

    # Generate OTP
    otp = generate_otp()
    otp_hash = make_password(otp)               

    # Hash password
    password_hash = make_password(password)

    expires_at = timezone.now() + timedelta(minutes=10)

    # Save or update pending registration
    PendingRegistration.objects.update_or_create(
        email=email,
        defaults={
            "username": username,
            "password": password_hash,
            "otp_hash": otp_hash,
            "otp_expires_at": expires_at,
            "phone": phone,   
        }
    )

    # Send OTP via Notification Service
    try:
        send_otp(email, otp, username)
    except Exception as e:
        return Response(
            {"error": "Failed to send OTP", "details": str(e)},
            status=500
        )

    return Response({
        "message": "OTP sent successfully",
        "email": email
    }, status=200)


#A

@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def verify_otp(request):
    """
    Step 2: Verify OTP and complete signup
    """
    email = request.data.get("email")
    otp = request.data.get("otp")

    if not email or not otp:
        return Response({"error": "Email and OTP are required"}, status=400)

    try:
        pending = PendingRegistration.objects.get(email=email)
    except PendingRegistration.DoesNotExist:
        return Response({"error": "No pending registration found"}, status=404)

    # Check expiration
    if pending.is_expired():
        return Response(
            {"error": "OTP expired. Please request a new one"},
            status=400
        )

    # Check attempts
    if pending.otp_attempts >= 5:
        return Response(
            {"error": "Too many attempts. Please request a new OTP"},
            status=400
        )

    # Check OTP
    if not check_password(otp, pending.otp_hash):
        pending.otp_attempts += 1
        pending.save()
        return Response({"error": "Invalid OTP"}, status=400)

    #  OTP صحيح → إنشاء الحساب

    signup_data = {
        "username": pending.username,
        "email": pending.email,
        "password": pending.password,   # hashed
        "password_confirm": pending.password,  # نفس الشيء لتجاوز validation
        "phone": pending.phone
    }

    serializer = UserSignupSerializer(data=signup_data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    user = serializer.save()

    #  مهم: نعدل الباسورد لأنه already hashed
    user.password = pending.password
    user.save()

    # حذف pending
    pending.delete()

    # جلب student
    student = Student.objects.get(user_id=user)

    return Response({
        "message": "Account created successfully",
        "user": {
            "user_id": str(user.user_id),
            "username": user.username,
            "email": user.email
        },
        "student": {
            "student_id": str(student.student_id)
        }
    }, status=201)