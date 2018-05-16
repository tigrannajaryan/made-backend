def post_or_get(request, key, default=None):
    return request.POST.get(key, request.GET.get(key, default))
