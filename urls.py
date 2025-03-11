from django.urls import path, re_path, include
from rest_framework.authtoken import views as authviews
from . import views

# App name must be specified, otherwise Django will complain about the URLs.
app_name = 'api-es'

# Parameters used by ElasticSearch aggregations:
#	kategorier: agg
#	socken: agg
#	terms: agg
#	kon: agg
#	insamlingsar: agg
#	fodelsear: agg
#	personer: agg

urlpatterns = [
    # Authentication
    path('api-token-auth/', authviews.obtain_auth_token),

    # Check Authentication
    path('check_authentication/', views.CheckAuthenticationViewSet.as_view(), name='check_authentication'),

    # Documents
    path('documents/', views.getDocuments, name='getDocuments'),

    # Aggregations
    path('terms/', views.getTerms, name='getTerms'),
    path('title_terms/', views.getTitleTerms, name='getTitleTerms'),
    path('collection_years/', views.getCollectionYears, name='getCollectionYears'),
    path('birth_years/', views.getBirthYears, name='getBirthYears'),
    path('categories/', views.getCategories, name='getCategories'),
    path('category_types/', views.getCategoryTypes, name='getCategoryTypes'),
    path('types/', views.getTypes, name='getTypes'),
    path('socken/', views.getSocken, name='getSocken'),
    path('mediacount/', views.getMediaCount, name='getMediaCount'),
    path('harad/', views.getHarad, name='getHarad'),
    path('county/', views.getCounty, name='getCounty'),
    path('landskap/', views.getLandskap, name='getLandskap'),
    path('persons/', views.getPersons, name='getPersons'),
    path('informants/', views.getInformants, name='getInformants'),
    path('collectors/', views.getCollectors, name='getCollectors'),
    path('gender/', views.getGender, name='getGender'),
    path('letters/', views.getLetters, name='getLetters'),

    # Similar Documents
    re_path(r'^similar/(?P<documentId>[^/]+)/$', views.getSimilar, name='getSimilar'),

    # Graph Views
    path('terms_graph/', views.getTermsGraph, name='getTermsGraph'),
    path('persons_graph/', views.getPersonsGraph, name='getPersonsGraph'),

    # Text Highlighting Interface
    path('texts/', views.getTexts, name='getTexts'),

    # Autocomplete
    path('autocomplete/terms/', views.getTermsAutocomplete, name='getTermsAutocomplete'),
    path('autocomplete/title_terms/', views.getTitleTermsAutocomplete, name='getTitleTermsAutocomplete'),
    path('autocomplete/persons/', views.getPersonsAutocomplete, name='getPersonsAutocomplete'),
    path('autocomplete/socken/', views.getSockenAutocomplete, name='getSockenAutocomplete'),
    path('autocomplete/landskap/', views.getLandskapAutocomplete, name='getLandskapAutocomplete'),
    path('autocomplete/archive_ids/', views.getArchiveIdsAutocomplete, name='getArchiveIdsAutocomplete'),

    # Totals by Type
    path('total_by_type/socken/', views.getSockenTotal, name='getSockenTotal'),
    path('total_by_type/collection_years/', views.getCollectionYearsTotal, name='getCollectionYearsTotal'),
    path('total_by_type/birth_years/', views.getBirthYearsTotal, name='getBirthYearsTotal'),
    path('total_by_type/gender/', views.getGenderTotal, name='getGenderTotal'),

    # Specific Entities
    re_path(r'^get_socken/(?P<sockenId>[^/]+)/$', views.getSocken, name='getSocken'),
    re_path(r'^get_person/(?P<personId>[^/]+)/$', views.getPersons, name='getPersons'),
    path('random_document/', views.getRandomDocument, name='getRandomDocument'),
    re_path(r'^document/(?P<documentId>[^/]+)/$', views.getDocument, name='getDocument'),

    # Statistics
    path('count/', views.getCount, name='getCount'),
    path('statistics/get_top_transcribers_by_pages/', views.getTopTranscribersByPagesStatistics, name="getTopTranscribersByPageStatistics"),

    # Miscellaneous
    path('current_time/', views.getCurrentTime, name='getCurrentTime'),
]