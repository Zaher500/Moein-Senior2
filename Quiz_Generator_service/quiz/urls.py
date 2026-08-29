from django.urls import path
from . import views

urlpatterns = [
    # Generation Endpoints
    path('generate/file/', views.generate_from_file_view, name='generate_file'),
    path('generate/existing/', views.generate_from_existing_view, name='generate_existing'),
    path('generate/scope/', views.generate_from_scope_view, name='generate_scope'),
    
    # Quiz Management / Retrieval
    path('progress/', views.learning_progress_view, name='learning_progress'),
    path('lecture/<uuid:lecture_id>/', views.quiz_by_lecture_view, name='quiz_by_lecture'),
    path('<uuid:quiz_id>/status/', views.quiz_status_view, name='quiz_status'),
    path('<uuid:quiz_id>/submit/', views.quiz_submit_view, name='quiz_submit'),
    path('<uuid:quiz_id>/', views.quiz_detail_view, name='quiz_detail'),
]
