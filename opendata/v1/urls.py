from django.urls import path, re_path
from . import views

#from rest_framework_swagger.views import get_swagger_view

#schema_view = get_swagger_view(title='Folke open data')

# App name must be specified,
# otherwise Django will complain about the URL's.
app_name = "folke-opendata-v1"

urlpatterns = [
    path(r'documents-def', views.documents, name="views.documents.name"),
    path(r'documents', views.Documents.as_view(), name=views.Documents.name),
    #path(r'^$', schema_view, name="Schema"),
    #url(r'^$', schema_view)
]
