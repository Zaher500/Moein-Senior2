def get_user_from_headers(request):
    user_id = request.META.get("HTTP_X_USER_ID")

    if not user_id:
        return None

    return {
        "user_id": user_id
    }