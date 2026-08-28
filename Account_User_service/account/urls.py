from django.urls import path
from . import views
from .views import register_initiate  #A
from .views import verify_otp  #A

urlpatterns = [
    # path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('delete/', views.delete_account, name='delete-account'),
    path('edit/', views.edit_account, name='edit-account'),
    path('decode-token/', views.decode_token_contents, name='decode-token'),
    path('check-student/<uuid:student_id>/', views.check_student_exists, name='check-student'),
    path('check-user/<uuid:user_id>/', views.check_user_exists, name='check-user'),
    path('me/', views.get_current_user, name='current-user'),
    path('signup/', register_initiate),   #A
    path('verify-otp/', verify_otp),  #A

]
