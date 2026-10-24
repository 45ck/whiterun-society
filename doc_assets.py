"""Explicit public documentation surface; no arbitrary filesystem serving."""
import re

def documentation_asset(root,route):
    if route in ('/docs','/docs/'):
        path=root/'docs/index.html';kind='text/html; charset=utf-8'
    elif route.startswith('/docs/images/'):
        name=route.removeprefix('/docs/images/')
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(png|jpg|jpeg|webp)',name):return None
        path=root/'docs/images'/name
        kind={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}[path.suffix]
    else:return None
    if not path.is_file() or path.resolve().is_relative_to((root/'docs').resolve()) is not True:return None
    return kind,path.read_bytes()
