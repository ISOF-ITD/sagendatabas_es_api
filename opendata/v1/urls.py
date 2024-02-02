from django.urls import path, re_path
from . import views

# App name must be specified,
# otherwise Django will complain about the URL's.
app_name = "folke-opendata-v1"

urlpatterns = [
    path(r'documents', views.documents, name=views.Documents.name),

]
