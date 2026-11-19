from django.urls import path
from . import views
from .views import register_initiate  #A
from .views import verify_otp  #A
from .views import resend_otp
from .internal_admin_views import authorize_admin_internal
from .internal_token_views import validate_token_internal
from .admin_views import (create_admin,list_admins,update_admin_permissions,edit_admin,deactivate_admin,
)
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
    path('resend-otp/', resend_otp),  #A
    path('admin/change-password/', views.change_admin_password, name='change_admin_password'),  #admin
    path('internal/admin/authorize/', authorize_admin_internal, name='internal-admin-authorize',),
    path("internal/token/validate/", validate_token_internal, name="internal-token-validate",),
    path('admin/create/', create_admin, name='create-admin',),
    path("admin/list/", list_admins, name="list-admins",),
    path("admin/<uuid:admin_id>/permissions/",update_admin_permissions,name="update-admin-permissions",),
    path("admin/<uuid:admin_id>/edit/",edit_admin,name="edit-admin",),
    path("admin/<uuid:admin_id>/deactivate/",deactivate_admin,name="deactivate-admin",),
]
