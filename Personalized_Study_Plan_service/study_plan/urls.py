
from django.urls import path
from .views import test_study_plan,generate_study_plan,list_study_plans,study_plan_detail,update_study_task,replan_saved_study_plan

urlpatterns = [
    path("test/", test_study_plan, name="test_study_plan"),
    path("generate/", generate_study_plan, name="generate_study_plan"),
     # Get all saved study plans
    path("",list_study_plans,name="list_study_plans"),
    # Get one saved study plan
    path("<uuid:plan_id>/",study_plan_detail,name="study_plan_detail"),
     # Update task progress
    path("<uuid:plan_id>/tasks/<uuid:task_id>/",update_study_task,name="update_study_task"),
    # Adaptive Replanning
    path("<uuid:plan_id>/replan/",replan_saved_study_plan,name="replan_saved_study_plan"),

]
