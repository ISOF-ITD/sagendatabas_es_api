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
	#	topics: agg
	#	kon: agg
	#	insamlingsar: agg
	#	fodelsear: agg
	#	personer: agg

	#	documents: list
	url(r'^documents/', views.getDocuments, name='getDocuments'),

	# aggregate topics
	url(r'^topics/', views.getTopics, name='getTopics'),

	# aggregate title topics
	url(r'^title_topics/', views.getTitleTopics, name='getTitleTopics'),

	# aggregate topics
	url(r'^topics/', views.getTopics, name='getTopics'),

	# aggregate upptackningsar
	url(r'^collection_years/', views.getCollectionYears, name='getCollectionYears'),

	# aggregate fodelsear
	url(r'^birth_years/', views.getBirthYears, name='getBirthYears'),

	# aggregate kategorier
	url(r'^categories/', views.getCategories, name='getCategories'),

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

	# aggregate informants
	url(r'^informants/', views.getInformants, name='getInformants'),

	# aggregate upptacknare
	url(r'^collectors/', views.getCollectors, name='getCollectors'),

	# aggregate kon
	url(r'^gender/', views.getGender, name='getGender'),

	# aggregate kon
	url(r'^gender/', views.getGender, name='getGender'),

	# hamta similar document
	url(r'^similar/(?P<documentId>[^/]+)/$', views.getSimilar, name='getSimilar'),

	# autocomplete
	url(r'^topics_autocomplete/', views.getTopicsAutocomplete, name='getTopicsAutocomplete'),
	url(r'^title_topics_autocomplete/', views.getTitleTopicsAutocomplete, name='getTitleTopicsAutocomplete'),
	url(r'^persons_autocomplete/', views.getPersonsAutocomplete, name='getPersonsAutocomplete'),

	url(r'^document/(?P<documentId>[^/]+)/$', views.getDocument, name='getDocument'),
]
