from django.conf.urls import url
from rest_framework.schemas import get_schema_view
from rest_framework_swagger.views import get_swagger_view
from rest_framework_swagger.renderers import SwaggerUIRenderer, OpenAPIRenderer
from . import views

schema_view = get_schema_view(title='Users API', renderer_classes=[OpenAPIRenderer, SwaggerUIRenderer])

urlpatterns = [
	url(r'^$', schema_view),

	#	kategorier: agg
	#	socken: agg
	#	topics: agg
	#	kön: agg
	#	insamlingsår: agg
	#	födelseår: agg
	#	personer: agg

	#	documents: list
	url(r'^documents/', views.getDocuments, name='getDocuments'),

	# aggregate topics för autocomplete
	url(r'^topics_autocomplete/', views.getTopicsAutocomplete, name='getTopicsAutocomplete'),

	# aggregate topics
	url(r'^topics/', views.getTopics, name='getTopics'),

	# aggregate title topics
	url(r'^title_topics/', views.getTitleTopics, name='getTitleTopics'),

	# aggregate title topics
	url(r'^title_topics_autocomplete/', views.getTitleTopicsAutocomplete, name='getTitleTopicsAutocomplete'),

	# aggregate topics
	url(r'^topics/', views.getTopics, name='getTopics'),

	# aggregate upptäckningsår
	url(r'^collection_years/', views.getCollectionYears, name='getCollectionYears'),

	# aggregate födelseår
	url(r'^birth_years/', views.getBirthYears, name='getBirthYears'),

	# aggregate kategorier
	url(r'^categories/', views.getCategories, name='getCategories'),

	# aggregate kategorier
	url(r'^types/', views.getTypes, name='getTypes'),

	# aggregate socken
	url(r'^socken/', views.getSocken, name='getSocken'),

	# aggregate harad
	url(r'^harad/', views.getHarad, name='getHarad'),

	# aggregate län
	url(r'^county/', views.getCounty, name='getCounty'),

	# aggregate landskap
	url(r'^landskap/', views.getLandskap, name='getLandskap'),

	# aggregate personer
	url(r'^persons/', views.getPersons, name='getPersons'),

	# aggregate informants
	url(r'^informants/', views.getInformants, name='getInformants'),

	# aggregate upptäcknare
	url(r'^collectors/', views.getCollectors, name='getCollectors'),

	# aggregate kön
	url(r'^gender/', views.getGender, name='getGender'),

	# aggregate kön
	url(r'^gender/', views.getGender, name='getGender'),

	# hämta similar document
	url(r'^similar/(?P<documentId>[^/]+)/$', views.getSimilar, name='getSimilar'),

	# aggregate titlar

	url(r'^document/(?P<documentId>[^/]+)/$', views.getDocument, name='getDocument'),
]