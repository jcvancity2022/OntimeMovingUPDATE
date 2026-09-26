from flask import request
from config import Config


def paginate(query, serializer):
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get('per_page', Config.DEFAULT_PAGE_SIZE))
    except ValueError:
        per_page = Config.DEFAULT_PAGE_SIZE
    per_page = max(1, min(per_page, Config.MAX_PAGE_SIZE))

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, (total + per_page - 1) // per_page)

    return {
        'items': [serializer(i) for i in items],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages
    }
