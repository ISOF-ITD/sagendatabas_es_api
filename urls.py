from django.conf.urls import url
# from rest_framework.schemas import get_schema_view
# from rest_framework_swagger.views import get_swagger_view
# from rest_framework_swagger.renderers import SwaggerUIRenderer, OpenAPIRenderer
from . import views

# schema_view = get_schema_view(title='Users API', renderer_classes=[OpenAPIRenderer, SwaggerUIRenderer])

urlpatterns = [
	#	url(r'^$', schema_view),

	#	kategorier: agg
	#	socken: agg
	#	terms: agg
	#	kon: agg
	#	insamlingsar: agg
	#	fodelsear: agg
	#	personer: agg

	#	documents: list
	url(r'^documents/', views.getDocuments, name='getDocuments'),

	# aggregate terms
	url(r'^terms/', views.getTerms, name='getTerms'),

	# aggregate title terms
	url(r'^title_terms/', views.getTitleTerms, name='getTitleTerms'),

	# aggregate upptackningsar
	url(r'^collection_years/', views.getCollectionYears, name='getCollectionYears'),

	# aggregate fodelsear
	url(r'^birth_years/', views.getBirthYears, name='getBirthYears'),

	# aggregate kategorier
	url(r'^categories/', views.getCategories, name='getCategories'),

	# aggregate kategorier
	url(r'^category_types/', views.getCategoryTypes, name='getCategoryTypes'),

	# aggregate kategorier
	url(r'^types/', views.getTypes, name='getTypes'),

	# aggregate socken
	url(r'^socken/', views.getSocken, name='getSocken'),

	# aggregate harad
	url(r'^harad/', views.getHarad, name='getHarad'),

	# aggregate lan
	url(r'^county/', views.getCounty, name='getCounty'),

	# aggregate landskap
	url(r'^landskap/', views.getLandskap, name='getLandskap'),

	# aggregate personer
	url(r'^persons/', views.getPersons, name='getPersons'),

	# enskild person
	#url(r'^person/(?P<personId>[^/]+)/$', views.getPerson, name='getPerson'),

	# aggregate informants
	url(r'^informants/', views.getInformants, name='getInformants'),

	# aggregate upptacknare
	url(r'^collectors/', views.getCollectors, name='getCollectors'),

	# aggregate kon
	url(r'^gender/', views.getGender, name='getGender'),

	# aggregate kon
	url(r'^gender/', views.getGender, name='getGender'),

	# aggregate brev avsändings- och destinationort
	url(r'^letters/', views.getLetters, name='getLetters'),

	# hamta similar document
	url(r'^similar/(?P<documentId>[^/]+)/$', views.getSimilar, name='getSimilar'),

	# graph
	url(r'^terms_graph/', views.getTermsGraph, name='getTermsGraph'),
	url(r'^persons_graph/', views.getPersonsGraph, name='getPersonsGraph'),

	# text highlight interface
	url(r'^texts/', views.getTexts, name='getTexts'),

	# autocomplete
	url(r'^autocomplete/terms/', views.getTermsAutocomplete, name='getTermsAutocomplete'),
	url(r'^autocomplete/title_terms/', views.getTitleTermsAutocomplete, name='getTitleTermsAutocomplete'),
	url(r'^autocomplete/persons/', views.getPersonsAutocomplete, name='getPersonsAutocomplete'),
	url(r'^autocomplete/socken/', views.getSockenAutocomplete, name='getSockenAutocomplete'),

	url(r'^total_by_type/socken/', views.getSockenTotal, name='getSockenTotal'),
	url(r'^total_by_type/collection_years/', views.getCollectionYearsTotal, name='getCollectionYearsTotal'),
	url(r'^total_by_type/birth_years/', views.getBirthYearsTotal, name='getBirthYearsTotal'),
	url(r'^total_by_type/gender/', views.getGenderTotal, name='getGenderTotal'),

	url(r'^get_socken/(?P<sockenId>[^/]+)/$', views.getSocken, name='getSocken'),
	url(r'^get_person/(?P<personId>[^/]+)/$', views.getPersons, name='getPersons'),
	url(r'^random_document', views.getRandomDocument, name='getRandomDocument'),
	url(r'^document/(?P<documentId>[^/]+)/$', views.getDocument, name='getDocument'),
]
