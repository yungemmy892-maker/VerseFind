from django.urls import path
from . import views

urlpatterns = [
    path("identify/", views.identify_verse, name="identify"),
    path("transcribe/", views.transcribe_audio, name="transcribe"),
    path("verse/", views.get_verse, name="verse"),
    path("chapter/", views.get_chapter, name="chapter"),
    path("saved/", views.saved_verses, name="saved"),
    path("saved/<int:pk>/", views.delete_saved, name="delete-saved"),
    path("versions/", views.list_versions, name="versions"),
]