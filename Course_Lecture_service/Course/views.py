import os
from django.shortcuts import get_object_or_404

from .models import Lecture
import uuid
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from .jwt_utils import get_student_id_from_token
from django.views.decorators.http import require_GET
import mimetypes

import threading
from django.http import FileResponse, Http404, HttpResponseForbidden

from django.http import FileResponse, Http404, HttpResponseForbidden ,JsonResponse
from rest_framework.decorators import api_view, permission_classes, parser_classes
from .utils.text_extractor import extract_text_from_file
from .services.summarization_client import get_summary
from .services.summarization_client import send_for_summarization, is_summary_ready
from .services.rag_client import send_for_rag_ingestion
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Course, Lecture
from .serializers import (
    CourseSerializer,
    LectureCreateSerializer,
    LectureSerializer
)




@api_view(['POST'])
def create_course(request):
    """
    Create a new course for the authenticated student
    Body: {"course_name": "Mathematics", "course_teacher": "Dr. Smith"}
    """
    print("HEADERS RECEIVED:", request.headers)

    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    serializer = CourseSerializer(data=request.data)
    if serializer.is_valid():
        # Create course with the authenticated student_id
        course = Course.objects.create(
            student_id=student_id,
            course_name=serializer.validated_data['course_name'],
            course_teacher=serializer.validated_data.get('course_teacher', '')
        )
        return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# READ - Get all courses for student
@api_view(['GET'])
def get_my_courses(request):
    """
    Get all courses for the authenticated student
    """
    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    courses = Course.objects.filter(student_id=student_id)
    serializer = CourseSerializer(courses, many=True, context={'request': request})
    return Response({
        'count': courses.count(),
        'courses': serializer.data
    })

# READ - Get specific course
@api_view(['GET'])
def get_course(request, course_id):
    """
    Get a specific course (only if owned by student)
    """
    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        course = Course.objects.get(course_id=course_id, student_id=student_id)
        serializer = CourseSerializer(course)
        return Response(serializer.data)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
def get_course_lectures(request, course_id):
    """
    Get all lectures for a specific course WITH FILE URLS
    URL: GET /api/courses/COURSE_ID/lectures/
    """
    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        course = Course.objects.get(course_id=course_id, student_id=student_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found'}, status=404)
    
    lectures = Lecture.objects.filter(course_id=course_id, student_id=student_id).order_by('created_at')
    
    # Get all files in the folder
    folder_path = os.path.join(settings.MEDIA_ROOT, str(student_id), str(course_id))
    all_files = os.listdir(folder_path) if os.path.exists(folder_path) else []
    
    lectures_data = []
    for lecture in lectures:
        lecture_dict = LectureSerializer(lecture).data
        
        # Add basic info for UI
        lecture_dict['course_id'] = str(course.course_id)
        lecture_dict['course_name'] = course.course_name
        
        # Check for file
        if lecture.file_name and lecture.file_name in all_files:
            gateway = settings.SERVICES['gateway']
            file_url = f"{gateway}/api/media/{student_id}/{course_id}/{lecture.file_name}/"
            
            lecture_dict['file_url'] = file_url
            lecture_dict['filename'] = lecture.file_name
            lecture_dict['has_file'] = True
            lecture_dict['file_exists'] = True
        else:
            lecture_dict['file_url'] = None
            lecture_dict['filename'] = lecture.file_name if lecture.file_name else None
            lecture_dict['has_file'] = bool(lecture.file_name)
            lecture_dict['file_exists'] = False
        
        # Add lecture detail URL
        lecture_dict['detail_url'] = f"/api/lectures/{lecture.lecture_id}/"
        
        lectures_data.append(lecture_dict)
    
    return Response({
        'course': {
            'course_id': str(course.course_id),
            'course_name': course.course_name,
            'course_teacher': course.course_teacher,
            'created_at': course.created_at,
            'lecture_count': lectures.count()
        },
        'lectures': lectures_data,
        'count': lectures.count()
    })


@api_view(['PUT'])
def update_course(request, course_id):
    """
    Update a course (only if owned by student)
    Body: {"course_name": "New Name", "course_teacher": "New Teacher"}
    """
    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        course = Course.objects.get(course_id=course_id, student_id=student_id)
        serializer = CourseSerializer(course, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Course.DoesNotExist:
        return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
def delete_course(request, course_id):
    """
    Delete a course (only if owned by student) AND ALL ITS FILES
    """
    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        course = Course.objects.get(course_id=course_id, student_id=student_id)
        
        # 1. Delete all files and the folder
        course_folder = os.path.join(
            settings.MEDIA_ROOT,
            str(student_id),
            str(course_id)
        )
        
        files_deleted = []
        folder_deleted = False
        
        if os.path.exists(course_folder):
            # Delete all files
            for filename in os.listdir(course_folder):
                file_path = os.path.join(course_folder, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    files_deleted.append(filename)
            
            # Delete the folder
            os.rmdir(course_folder)
            folder_deleted = True
        
        # 2. Delete the course (cascades to lectures)
        course_name = course.course_name
        course.delete()
        
        return Response({
            'message': 'Course and all lectures deleted',
            'deleted_course': course_name,
            'files_deleted': files_deleted,
            'files_count': len(files_deleted),
            'folder_deleted': folder_deleted
        })
        
    except Course.DoesNotExist:
        return Response({'error': 'Course not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

#///////////////////////////////////////////////////////////////////////////////////////////////////////

@api_view(['POST'])
@csrf_exempt
@parser_classes([MultiPartParser, FormParser])
def upload_lecture(request, course_id):
    """
    Upload lecture to a specific course
    URL: POST /api/courses/COURSE_ID/lectures/upload/
    """
    # 1. Authentication
    student_id = get_student_id_from_token(request)

    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # 2. Authorization - check if course belongs to student
    try:
        course = Course.objects.get(course_id=course_id, student_id=student_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found or access denied'}, status=status.HTTP_404_NOT_FOUND)
    
    # 3. Validate lecture data using serializer
    serializer = LectureCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # 4. File validation
    if 'file' not in request.FILES:
        return Response({'error': 'No file submitted'}, status=status.HTTP_400_BAD_REQUEST)
    
    uploaded_file = request.FILES['file']
    
    allowed_types = [
        'application/pdf', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    ]
    
    allowed_extensions = ['.pdf', '.docx', '.pptx']
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    
    if (uploaded_file.content_type not in allowed_types and 
        file_extension not in allowed_extensions):
        return Response(
            {'error': 'Only PDF, Word, and PowerPoint files are allowed'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # 5. Create secure file path
        student_id_str = str(student_id)
        course_id_str = str(course_id)
        
        upload_dir = os.path.join(settings.MEDIA_ROOT, student_id_str, course_id_str)
        os.makedirs(upload_dir, exist_ok=True)
        
        # 6. Generate unique filename
        file_extension = os.path.splitext(uploaded_file.name)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(upload_dir, unique_filename)
        

        print(f"DEBUG - MEDIA_ROOT: {settings.MEDIA_ROOT}")
        print(f"DEBUG - upload_dir: {upload_dir}")
        print(f"DEBUG - File saved to: {file_path}")
        
        # 7. Save file
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
        
        # 8. Get lecture name
        lecture_name = serializer.validated_data['lecture_name']

        # 9. CREATE LECTURE IMMEDIATELY ✅
        lecture = Lecture.objects.create(
            student_id=student_id,
            course_id=course,
            lecture_name=lecture_name,
            file_name=unique_filename,
            summary_status='PROCESSING',
        )

        # 10. Extract text
        try:
            extracted_text = extract_text_from_file(file_path)
        except Exception as e:
            lecture.summary_status = 'FAILED'
            lecture.save(update_fields=['summary_status'])

            if os.path.exists(file_path):
                os.remove(file_path)

            return Response(
                {'error': f'Text extraction failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        # 11. Fire-and-forget: send extracted text to RAG and Summarization services
        def send_to_rag():
            try:
                send_for_rag_ingestion(
                    lecture_id=lecture.lecture_id,
                    course_id=course.course_id,
                    student_id=student_id,
                    text=extracted_text,
                    source_type="lecture",
                )
            except Exception as e:
                print(f"RAG ingestion failed: {e}")

        # def send_to_summarizer():
        #     try:
        #         send_for_summarization(lecture.lecture_id, extracted_text)
        #     except Exception as e:
        #         print(f"Summarization request failed: {e}")

        def send_to_summarizer():
         try:
            user_id = request.META.get("HTTP_X_USER_ID")
            username = request.META.get("HTTP_X_USERNAME")

            send_for_summarization(
                lecture_id=lecture.lecture_id,
                text=extracted_text,
                student_id=student_id,
                user_id=user_id,
                username=username,
                )

         except Exception as e:
            print(f"Summarization request failed: {e}")

        rag_thread = threading.Thread(
            target=send_to_rag,
            daemon=True,
        )
        summarizer_thread = threading.Thread(target=send_to_summarizer, daemon=True)

        rag_thread.start()
        summarizer_thread.start()
        
        # 13. Return response
        return Response({
            'message': 'Lecture uploaded successfully',
            'lecture': LectureSerializer(lecture).data,
            'file_saved_as': unique_filename
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(
        {'error': f'Upload failed: {str(e)}'},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR
    )



@api_view(['PUT'])
def update_lecture_name(request, course_id, lecture_id):
    """
    Update lecture name within a specific course
    URL: PUT /api/courses/COURSE_ID/lectures/LECTURE_ID/update-name/
    Body: {"lecture_name": "New Lecture Name"}
    """
    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        course = Course.objects.get(course_id=course_id, student_id=student_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found or access denied'}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        # FIXED: Use course_id (ForeignKey) with the course object or course_id value
        lecture = Lecture.objects.get(
            lecture_id=lecture_id,
            course_id=course_id,  # This works because course_id is the UUID value
            student_id=student_id
        )
    except Lecture.DoesNotExist:
        return Response({'error': 'Lecture not found or access denied'}, status=status.HTTP_404_NOT_FOUND)
    
    new_lecture_name = request.data.get('lecture_name')
    if not new_lecture_name:
        return Response({'error': 'lecture_name field is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    if new_lecture_name == lecture.lecture_name:
        return Response({'error': 'New name is identical to current name'}, status=status.HTTP_400_BAD_REQUEST)
    
    # FIXED: Use course_id with the UUID value
    existing_lecture = Lecture.objects.filter(
        course_id=course_id,  # Use the UUID value
        student_id=student_id,
        lecture_name__iexact=new_lecture_name
    ).exclude(lecture_id=lecture_id)
    
    if existing_lecture.exists():
        return Response({'error': f'Lecture name "{new_lecture_name}" already exists in this course'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        old_name = lecture.lecture_name
        lecture.lecture_name = new_lecture_name
        lecture.save()
        
        serializer = LectureSerializer(lecture)
        return Response({
            'message': 'Lecture name updated successfully',
            'old_name': old_name,
            'new_name': new_lecture_name,
            'lecture': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({'error': f'Failed to update lecture name: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
def delete_lecture(request, course_id, lecture_id):
    """
    Delete a lecture from a course and remove the physical file.
    URL: DELETE /api/courses/COURSE_ID/lectures/LECTURE_ID/delete/
    """
    # 1. Authentication
    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response({'error': 'Authentication required'}, status=401)
    
    # 2. Authorization - check if course belongs to student
    try:
        course = Course.objects.get(course_id=course_id, student_id=student_id)
    except Course.DoesNotExist:
        return Response({'error': 'Course not found or access denied'}, status=404)
    
    # 3. Get the lecture and verify ownership
    try:
        lecture = Lecture.objects.get(lecture_id=lecture_id, course_id=course_id, student_id=student_id)
    except Lecture.DoesNotExist:
        return Response({'error': 'Lecture not found or access denied'}, status=404)
    
    file_deleted = False
    folder_deleted = False
    
    # 4. Delete the physical file
    if lecture.file_name:
        # Construct the file path
        file_path = os.path.join(settings.MEDIA_ROOT, str(student_id), str(course_id), lecture.file_name)
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                file_deleted = True
                print(f"✅ Deleted file: {file_path}")
                
                # Delete folder if empty
                folder_path = os.path.join(settings.MEDIA_ROOT, str(student_id), str(course_id))
                if os.path.exists(folder_path) and not os.listdir(folder_path):
                    os.rmdir(folder_path)
                    folder_deleted = True
                    print(f"✅ Deleted empty folder: {folder_path}")
            except Exception as e:
                print(f"⚠️ Failed to delete file/folder: {e}")
        else:
            print(f"⚠️ File not found: {file_path}")
    else:
        print(f"⚠️ Lecture has no file_name stored: {lecture.lecture_id}")
    
    # 5. Delete the lecture record from the database
    lecture_name = lecture.lecture_name
    lecture.delete()
    
    return Response({
        'message': 'Lecture deleted successfully',
        'deleted_lecture': lecture_name,
        'course': course.course_name,
        'file_deleted': file_deleted,
        'folder_deleted': folder_deleted,
        'note': 'Folder only deleted if it became empty'
    }, status=200)


@api_view(['DELETE'])
def delete_student_courses(request, student_id):
    """Simple endpoint to delete all courses for a student"""
    print("🔥 DELETE STUDENT COURSES CALLED FOR:", student_id)
    try:
        Course.objects.filter(student_id=student_id).delete()
        
        return Response({
            'message': f'Courses deleted for student {student_id}',
            'deleted': True
        })
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
def get_lecture(request, lecture_id):

    """
    Get a single lecture by ID with file download URL
    URL: GET /api/lectures/{lecture_id}/
    """
    # 1. Authentication - try multiple ways to get student_id
    student_id = None
    
    # Method 1: From JWT token
    student_id = get_student_id_from_token(request)
    
    # Method 2: From gateway headers (if forwarded)
    if not student_id and 'HTTP_X_STUDENT_ID' in request.META:
        student_id = request.META.get('HTTP_X_STUDENT_ID')
    
    # Method 3: From request attribute set by gateway middleware
    if not student_id and hasattr(request, 'student_id'):
        student_id = request.student_id
    
    if not student_id:
        return Response({'error': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)
    
    # 2. Get lecture
    try:
        lecture = Lecture.objects.get(lecture_id=lecture_id, student_id=student_id)
    except Lecture.DoesNotExist:
        return Response({'error': 'Lecture not found or access denied'}, status=status.HTTP_404_NOT_FOUND)

    # Poll summarization service if still processing
    if lecture.summary_status == 'PROCESSING':
        try:
            if is_summary_ready(str(lecture.lecture_id)):
                lecture.summary_status = 'READY'
                lecture.save(update_fields=['summary_status'])
        except Exception as e:
            print("Summary readiness check failed:", e)
            # Do NOT fail the request
            # Keep PROCESSING and try again next poll
            
    
    # 3. Serialize lecture data
    lecture_data = LectureSerializer(lecture).data
    
    # 4. Add course info
    course = lecture.course_id
    lecture_data['course'] = {
        'course_id': str(course.course_id),
        'course_name': course.course_name,
        'course_teacher': course.course_teacher
    }
    
    # 5. Add file URL if file exists
    if lecture.file_name:
        folder_path = os.path.join(
            settings.MEDIA_ROOT, 
            str(student_id), 
            str(course.course_id)
        )
        file_path = os.path.join(folder_path, lecture.file_name)
        
        if os.path.exists(file_path):
            # Use relative URL for gateway
            lecture_data['file_url'] = f"/api/media/{student_id}/{course.course_id}/{lecture.file_name}/"
            lecture_data['has_file'] = True
            lecture_data['file_exists'] = True
        else:
            lecture_data['file_url'] = None
            lecture_data['has_file'] = False
            lecture_data['file_exists'] = False
    else:
        lecture_data['file_url'] = None
        lecture_data['has_file'] = False
        lecture_data['file_exists'] = False
    
    return Response(lecture_data)


@api_view(['GET'])
def get_lecture_summary(request, lecture_id):
    """
    Get lecture summary from summarization service
    URL: GET /api/lectures/<lecture_id>/summary/
    """
    # 1. Authentication
    student_id = get_student_id_from_token(request)
    if not student_id:
        return Response(
            {'error': 'Authentication required'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # 2. Get lecture & verify ownership
    try:
        lecture = Lecture.objects.get(
            lecture_id=lecture_id,
            student_id=student_id
        )
    except Lecture.DoesNotExist:
        return Response(
            {'error': 'Lecture not found or access denied'},
            status=status.HTTP_404_NOT_FOUND
        )

    # 3. Check summary status
    if lecture.summary_status != 'READY':
        return Response(
            {
                'error': 'Summary is not ready yet',
                'summary_status': lecture.summary_status
            },
            status=status.HTTP_409_CONFLICT
        )

    # 4. Fetch summary from summarization service
    try:
        summary_data = get_summary(lecture.lecture_id)
    except Exception as e:
        return Response(
            {'error': f'Failed to fetch summary: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # 5. Return summary to frontend
    return Response(
        {
            'lecture_id': str(lecture.lecture_id),
            'summary': summary_data.get('summary')
        },
        status=status.HTTP_200_OK
    )


def _get_header_case_insensitive(request, header_name):
    """
    Return header value reading case-insensitively from request.headers or request.META.
    header_name should be like 'X-GATEWAY-SECRET' or 'X-Student-ID'.
    """
    # 1) check request.headers (Django 2.2+ provides a case-insensitive mapping, but be defensive)
    try:
        for k, v in request.headers.items():
            if k.lower() == header_name.lower():
                return v
    except Exception:
        pass

    # 2) fallback to request.META (HTTP_ prefix, hyphens -> underscores)
    meta_key = "HTTP_" + header_name.replace("-", "_").upper()
    return request.META.get(meta_key)


@require_GET
def serve_media_file(request, student_id, course_id, filename):
    """
    Serve a file from MEDIA_ROOT/<student_id>/<course_id>/<filename>
    - Checks gateway secret header (case-insensitive).
    - Optionally checks X-Student-ID (case-insensitive) to confirm ownership.
    """
    # Debug: show the incoming key header names once (temporary)
    # print("[Course DEBUG] headers keys sample:", list(request.headers.keys())[:15])

    # 1) Verify gateway secret header (case-insensitive)
    gateway_secret = _get_header_case_insensitive(request, 'X-GATEWAY-SECRET')
    expected = getattr(settings, 'GATEWAY_SECRET', None)
    if not gateway_secret or expected is None or gateway_secret != expected:
        # Optional: log actual vs expected for debugging (remove in prod)
        print(f"[Course DEBUG] Gateway secret mismatch. Received: {gateway_secret!r} Expected: {expected!r}")
        return HttpResponseForbidden("Forbidden: missing or invalid gateway secret")

    # 2) Optional: verify student ownership header (case-insensitive)
    forwarded_student = _get_header_case_insensitive(request, 'X-Student-ID')
    if forwarded_student and str(forwarded_student) != str(student_id):
        print(f"[Course DEBUG] Student ID mismatch. Forwarded: {forwarded_student} path: {student_id}")
        return HttpResponseForbidden("Forbidden: student mismatch")

    # 3) Build the file path and check existence
    file_path = os.path.join(settings.MEDIA_ROOT, str(student_id), str(course_id), filename)
    if not os.path.exists(file_path):
        print(f"[Course DEBUG] File not found at path: {file_path}")
        raise Http404("File not found")

    # 4) Serve file (use inline for previews; change to attachment to force download)
    content_type, _ = mimetypes.guess_type(file_path)
    response = FileResponse(open(file_path, 'rb'), content_type=content_type or 'application/octet-stream')
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(filename)}"'
    return response
    


import os
from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404

from .models import Lecture

def get_lecture_file(request, lecture_id):
    lecture = get_object_or_404(Lecture, lecture_id=lecture_id)

    if not lecture.file_name:
        return JsonResponse(
            {"success": False, "message": "Lecture file is not attached."},
            status=404,
        )

    media_root = getattr(settings, "MEDIA_ROOT", None)
    if not media_root:
        media_root = os.path.join(settings.BASE_DIR, "media")

    file_path = os.path.join(
        media_root,
        str(lecture.student_id),
        str(lecture.course_id.course_id),
        lecture.file_name,
    )

    if not os.path.isfile(file_path):
        return JsonResponse(
            {"success": False, "message": "Lecture file not found on disk."},
            status=404,
        )

    return FileResponse(
        open(file_path, "rb"),
        as_attachment=False,
        filename=lecture.file_name,
    )