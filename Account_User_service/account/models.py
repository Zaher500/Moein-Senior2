from django.db import models
import uuid
from django.contrib.auth.hashers import make_password, check_password

class User(models.Model):
    class Role(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        ADMIN = 'ADMIN', 'Admin'
        MAIN_ADMIN = 'MAIN_ADMIN', 'Main Admin'

    user_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=10, blank=True, null=True)
    password = models.CharField(max_length=128)  

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT
    )

    is_active = models.BooleanField(default=True)

    must_change_password = models.BooleanField(
        default=False
    )

    token_version = models.PositiveIntegerField(          #For when you change the temporary password
    default=1                                               #Because we already have existing users, and we want to add the field without having to manually provide a value for each user.
    )
    
    admin_permissions = models.ManyToManyField(
        'AdminPermission',
        blank=True,                          #Admin account can start without any permissions, until the Main Admin assigns the appropriate permissions
        related_name='users'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def set_password(self, raw_password):
        """Hash the password before saving"""
        self.password = make_password(raw_password)
    
    def check_password(self, raw_password):
        """Check if the raw password matches the hashed one"""
        return check_password(raw_password, self.password)
    
    def __str__(self):
        return self.username
    
    class Meta:
        db_table = 'Account'


class Student(models.Model):

    student_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    user_id = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='student_profile'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Student: {self.user_id.username}"
    
    class Meta:
        db_table = 'Student'

class AdminPermission(models.Model):

    class Code(models.TextChoices):
        VIEW_STUDENTS = 'VIEW_STUDENTS', 'View Students'
        EDIT_STUDENTS = 'EDIT_STUDENTS', 'Edit Students'
        DELETE_STUDENTS = 'DELETE_STUDENTS', 'Delete Students'

        VIEW_COURSES = 'VIEW_COURSES', 'View Courses'
        CREATE_COURSES = 'CREATE_COURSES', 'Create Courses'
        EDIT_COURSES = 'EDIT_COURSES', 'Edit Courses'
        DELETE_COURSES = 'DELETE_COURSES', 'Delete Courses'

    code = models.CharField(
        max_length=30,
        choices=Code.choices,
        unique=True
    )

    def __str__(self):
        return self.code

    class Meta:
        db_table = 'AdminPermission'


#A
from django.utils import timezone
from datetime import timedelta

class PendingRegistration(models.Model):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150)

    password = models.CharField(max_length=128)  # سيتم تخزينه hashed

    phone = models.CharField(max_length=10, blank=True, null=True)
    
    otp_hash = models.CharField(max_length=255)
    otp_expires_at = models.DateTimeField()

    otp_sent_at = models.DateTimeField(default=timezone.now)

    otp_attempts = models.IntegerField(default=0)  #A

    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.otp_expires_at

    def __str__(self):
        return self.email