from django.http import JsonResponse
import requests, json, sys, os
from requests.auth import HTTPBasicAuth
from random import randint
#from django.conf.urls import url, include

from . import es_config
from . import geohash

import logging
logger = logging.getLogger(__name__)

from rest_framework.response import Response
from rest_framework import viewsets, permissions, mixins, status
from rest_framework.views import APIView
from rest_framework import authentication, permissions

def checkAuthentication(request):
	#if request.environ.get('REMOTE_USER') is None:
	if not request.user.is_authenticated:
		jsonResponse = Response({
			'authenticated': False,
			'error': 'not logged in'
		})
		jsonResponse['Access-Control-Allow-Origin'] = '*'

		return jsonResponse

class CheckAuthenticationViewSet(APIView):
	authentication_classes = [authentication.TokenAuthentication]
	permission_classes = [permissions.IsAuthenticated]

	def get(self, request):
		jsonResponse = Response({
			'authenticated': True,
			'user': request.user.username
		})
		jsonResponse['Access-Control-Allow-Origin'] = '*'

		return jsonResponse

def createQuery(request, data_restriction=None):
	"""
	Function som tar in request object och bygger upp Elasticsearch JSON query som skickas till es_config

	Den letar efter varje param som skickas via url:et (?search=söksträng&type=arkiv&...) och
	lägger till query object till bool.must i hela query:en

	Mer om bool: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-bool-query.html

	Frivillig parameter:
	data_restriction:
		Möjliga värden:
		opendata: Lägger till alla parametrar som måste finnas för öppen data
	"""

	# Om restriktion öppna data så läggs tvingande filter parametrar till
	if (len(request.GET) > 0 or data_restriction == 'opendata'):
		query = {
			'bool': {
				'must': []
			}
		}
	else:
		query = {}


	# Hämtar document av angiven transcriptionstatus (en eller flera). Exempel: `transcriptionstatus=readytotranscribe,transcribed`
	if ('transcriptionstatus' in request.GET):
		transcriptionstatus_should_bool = {
			'bool': {
				'should': []
			}
		}

		transcriptionstatus_strings = request.GET['transcriptionstatus'].split(',')

		for transcriptionstatus in transcriptionstatus_strings:
			transcriptionstatus_should_bool['bool']['should'].append({
				'match': {
					'transcriptionstatus': transcriptionstatus
				}
			})
		query['bool']['must'].append(transcriptionstatus_should_bool)


	# Hämtar document av angiven publishstatus (en eller flera). Exempel: `publishstatus=readytopublish,published`
	if ('publishstatus' in request.GET or data_restriction == 'opendata'):
		publishstatus_should_bool = {
			'bool': {
				'should': []
			}
		}
		publishstatus_strings = []
		if ('publishstatus' in request.GET):
			publishstatus_strings = request.GET['publishstatus'].split(',')

		if data_restriction == 'opendata':
			# For restriction opendata
			if 'published' not in publishstatus_strings:
				publishstatus_strings.append('published')

		for publishstatus in publishstatus_strings:
			publishstatus_should_bool['bool']['should'].append({
				'match': {
					'publishstatus': publishstatus
				}
			})
		query['bool']['must'].append(publishstatus_should_bool)

	# TODO transcriptiondate
#		query['bool']['must']['match'].append({
#			'transcriptiondate': {
#				'lt': Now() - 1,
#			}
#		})

	# Hämtar documenter var `year` är mellan från och till. Exempel: `collection_year=1900,1910`
	if ('collection_years' in request.GET):
		collectionYears = request.GET['collection_years'].split(',')

		query['bool']['must'].append({
			'range': {
				'year': {
					'gte': collectionYears[0],
					'lte': collectionYears[1]
				}
			}
		})

	# Hämtar documenter var ett eller flera eller alla ord förekommer i titel eller text. Exempel: (ett eller flera ord) `search=svart hund`, (alla ord) `search=svart,hund`, (fras sökning, endast i `text` fältet `search="svart hund"`
	if ('search' in request.GET):
		term = request.GET['search'].replace('"', '')
		raw = True if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else False
		matchType = 'phrase' if raw else 'best_fields'
		# vi viktar text dubbelt så mycket som de andra fälten
		# utan att vara säker på att det är bästa lösningen
		standardFields = [
			'text^2',
			'search_other',
			'metadata.value',
			'title',
			'contents',
			'archive.archive',
			'archive.archive_id',
			'archive.archive_id_row',
			'places.name',
			'places.landskap',
			'places.county',
			'places.harad',
			'persons.name',
			'id',
			'headwords',
		]
		rawFields = [
			'text.raw^2',
			'title.raw',
			'headwords.raw',
			'contents.raw'
		]
		# contents är en sammanfattning av innehållet, 
		# och när titeln saknas använder vi contents som
		# en titel i gränssnittet istället.
		# därför är contents med i titleFields
		titleFields = [
			'title',
			'contents',
		]
		contentFields = [
			'text',
		]
		titleRawFields = [
			'title.raw',
			'contents.raw',
		]
		contentRawFields = [
			'text.raw',
		]
		
		fields = standardFields
		if raw:
			fields = rawFields
		if 'search_title' in request.GET and request.GET['search_title'] != 'false':
			fields = titleFields
			if raw:
				fields = titleRawFields
		elif 'search_content' in request.GET and request.GET['search_content'] != 'false':
			fields = contentFields
			if raw:
				fields = contentRawFields

		matchObj = {
			'bool': {
				'should': [
					{
						'multi_match': {
							'query': term,
							'type': matchType,
							'fields': fields,
							'minimum_should_match': '100%'
						}
					}
				]
			}
		}

		# search_exclude_title = true, sök inte i titel fältet
		if (not 'search_exclude_title' in request.GET or request.GET['search_exclude_title'] == 'false') and (not 'search_raw' in request.GET or request.GET['search_raw'] != 'true'):
			matchObj['bool']['should'][0]['multi_match']['fields'].append('title')

		# if term.startswith('"') and term.endswith('"'):
		# 	if ('phrase_options' in request.GET):
		# 		if (request.GET['phrase_options'] == 'nearer'):
		# 			matchObj['bool']['should'][0]['multi_match']['slop'] = 1
		# 		if (request.GET['phrase_options'] == 'near'):
		# 			matchObj['bool']['should'][0]['multi_match']['slop'] = 3
		# 	else:
		# 		matchObj['bool']['should'][0]['multi_match']['slop'] = 50

		# # Används för sök i data av typ ortnamn för test att söka på börjar på och slutar på med basic wildcard
		# # Vid problem: Kan aktiveras med annat mycket sällan använt tecken som pipe |i		if (term.startswith('*') or term.endswith('*')):
		# 	matchObj = {
		# 		'wildcard': {
		# 			'title': {
		# 				'value': term,
		# 				'boost': 1.0,
		# 				'rewrite': 'constant_score'
		# 			}
		# 		}
		# 	}

		query['bool']['must'].append(matchObj)


	# Används inte längre, ersätts av 'search'
	if ('search_all' in request.GET):
		searchString = request.GET['search_all']

		matchObj = {
			'multi_match': {
				'query': searchString,
				'type': 'best_fields',
				'fields': [
					'title',
					'text',
					'taxonomy.name',
					'taxonomy.category',
					'metadata.value',
					'archive.archive',
					'places.name'
				],
				'minimum_should_match': '100%'
			}
		}


		query['bool']['must'].append(matchObj)


	# Hämtar documenter som har speciell typ av metadata. Exempel: `has_metadata=sitevision_url` (hämtar kurerade postar för matkartan).
	if 'has_metadata' in request.GET:
		metadata_types = request.GET['has_metadata'].split(',')
		should_query = []
		for metadata_type in metadata_types:
			should_query.append({
				'match': {
					'metadata.type': metadata_type
				}
			})
		query['bool']['must'].append({
			'bool': {
				'should': should_query,
				'minimum_should_match': 1
			}
		})

	if ('mediafiles_are_public' in request.GET and request.GET['mediafiles_are_public'] == 'true'):
		query['bool']['must'].append({
			'match': {
				'metadata.type': 'mediafiles_are_public',
			}
		})
		query['bool']['must'].append({
			'match': {
				'metadata.value': 'True',
			}
		})

	# Hämtar documenter som finns i angiven kategori (en eller flera). Exempel: `category=L,H`
	if ('category' in request.GET):
		categoryBool = {
			'bool': {
				'should': []
			}
		}

		categoryStrings = request.GET['category'].split(',')

		for category in categoryStrings:

			categoryBool['bool']['should'].append({
				'match': {
					'taxonomy.category': category.upper()
				}
			})

			categoryBool['bool']['should'].append({
				'match': {
					'taxonomy.category': category
				}
			})


		query['bool']['must'].append(categoryBool)


	# Hämtar documenter av angiven typ (en eller flera). Exempel: `type=arkiv,tryckt`
	if ('type' in request.GET):
		typeShouldBool = {
			'bool': {
				'should': []
			}
		}

		typeStrings = request.GET['type'].split(',')

		for type in typeStrings:
			typeShouldBool['bool']['should'].append({
				'match': {
					'materialtype': type
				}
			})
		query['bool']['must'].append(typeShouldBool)

	if ('recordtype' in request.GET):
		typeShouldBool = {
			'bool': {
				'should': []
			}
		}

		typeStrings = request.GET['recordtype'].split(',')

		for recordtype in typeStrings:
			typeShouldBool['bool']['should'].append({
				'match': {
					'recordtype': recordtype
				}
			})
		query['bool']['must'].append(typeShouldBool)

	# Hämtar dokument som har minst en mediafil (t.ex. pdf)
	if ('has_media' in request.GET and request.GET['has_media'].lower() == 'true'):
		query['bool']['must'].append({
			'exists' : {
				'field': 'media.source'
			}
		})

	# Hämtar dokument med media av angiven typ (en eller flera). Exempel: `mediatype=pdf,image,audio`
	if ('mediatype' in request.GET):
		mediatypeShouldBool = {
			'bool': {
				'should': []
			}
		}

		mediatypeStrings = request.GET['mediatype'].split(',')

		for mediatype in mediatypeStrings:
			mediatypeShouldBool['bool']['should'].append({
				'match': {
					'media.type.keyword': mediatype
				}
			})
		query['bool']['must'].append(mediatypeShouldBool)

	# Hämtar accessioner som har minst en transkriberad record
	if('has_transcribed_records' in request.GET and request.GET['has_transcribed_records'].lower() == 'true'):
		query['bool']['must'].append({
			'range' : {
				'numberoftranscribedonerecord' : {
					'gte' : 1
				}
			}
		})

	# Hämtar accessioner där numberoftranscribedonerecord är mindre än numberofonerecord
	# Check if 'has_untranscribed_records' parameter is present in the GET request
	# and its value is 'true' (case-insensitive)
	if ('has_untranscribed_records' in request.GET and request.GET['has_untranscribed_records'].lower() == 'true'):

		# Modify the Elasticsearch query
		query['bool']['filter'] = {

			# Use a 'bool' query to combine two conditions
			"bool": {
				"should": [

					# First condition: 'recordtype' is not 'one_accession_row'
					{
						"bool": {
							"must_not": {
								"term": {"recordtype": "one_accession_row"}
							}
						}
					},

					# Second condition: 'recordtype' is 'one_accession_row' and
					# 'numberoftranscribedonerecord' is less than 'numberofonerecord'
					{
						"bool": {
							"must": [

								# Check if 'recordtype' is 'one_accession_row'
								{
									"term": {"recordtype": "one_accession_row"}
								},

								# Check if 'numberoftranscribedonerecord' is less than 'numberofonerecord'
								{
									"script": {
										"script": {
											"source": "doc['numberoftranscribedonerecord'].value < doc['numberofonerecord'].value"
										}
									}
								}

							]
						}
					}

				]
			}
		}


	# Hämtar documenter som har speciella ID.
	if ('documents' in request.GET):
		docIdShouldBool = {
			'bool': {
				'should': []
			}
		}

		documentIds = request.GET['documents'].split(',')

		for docId in documentIds:
			docIdShouldBool['bool']['should'].append({
				'match': {
					'_id': docId
				}
			})
		query['bool']['must'].append(docIdShouldBool)


	# Hämtar documenter samlat in i angiven socken (en eller flera). Exempel: (sägner från Göteborgs stad och Partille) `socken_id=202,243`
	if ('socken_id' in request.GET):
		sockenShouldBool = {
			'nested': {
				'path': 'places',
				'query': {
					'bool': {
						'should': []
					}
				}
			}
		}

		sockenIds = request.GET['socken_id'].split(',')

		for socken in sockenIds:
			sockenShouldBool['nested']['query']['bool']['should'].append({
					'match': {
						'places.id': socken
					}
			})

		query['bool']['must'].append(sockenShouldBool)


	# Hämtar documenter samlat in i angiven socken, härad, landskap eller län, sök via namn (wildcard sökning). Exempel: `place=Bolle`
	if ('place' in request.GET):
		placeShouldBool = {
			'nested': {
				'path': 'places',
				'query': {
					'bool': {
						'should': []
					}
				}
			}
		}

		placeShouldBool['nested']['query']['bool']['should'].append({
			'wildcard': {
				# capitalize() gör första bokstaven stor: "göteborg" -> "Göteborg"
				'places.name': request.GET['place'].capitalize()+'*'
			}
		})

		placeShouldBool['nested']['query']['bool']['should'].append({
			'wildcard': {
				# capitalize() gör första bokstaven stor: "göteborg" -> "Göteborg"
				'places.harad': request.GET['place'].capitalize()+'*'
			}
		})

		placeShouldBool['nested']['query']['bool']['should'].append({
			'wildcard': {
				# capitalize() gör första bokstaven stor: "göteborg" -> "Göteborg"
				'places.landskap': request.GET['place'].capitalize()+'*'
			}
		})

		placeShouldBool['nested']['query']['bool']['should'].append({
			'wildcard': {
				# capitalize() gör första bokstaven stor: "göteborg" -> "Göteborg"
				'places.county': request.GET['place'].capitalize()+'*'
			}
		})

		# also match the id of the place
		placeShouldBool['nested']['query']['bool']['should'].append({
			'match': {
				'places.id': request.GET['place']
			}
		})

		query['bool']['must'].append(placeShouldBool)


	# Hämtar documenter samlat in i angiven socken, men här letar vi efter namn (wildcard sökning). Exempel: `socken=Fritsla`
	if ('socken' in request.GET):
		sockenShouldBool = {
			'nested': {
				'path': 'places',
				'query': {
					'bool': {
						'should': []
					}
				}
			}
		}

		sockenNames = request.GET['socken'].split(',')

		for socken in sockenNames:
			sockenShouldBool['nested']['query']['bool']['should'].append({
					'wildcard': {
						'places.name': socken+'*'
					}
			})

		query['bool']['must'].append(sockenShouldBool)


	# Hämtar documenter samlat in i angiven landskap. Exempel: `landskap=Värmland`
	if ('landskap' in request.GET):
		landskapShouldBool = {
			'nested': {
				'path': 'places',
				'query': {
					'bool': {
						'should': []
					}
				}
			}
		}

		sockenNames = request.GET['landskap'].split(',')

		for landskap in sockenNames:
			landskapShouldBool['nested']['query']['bool']['should'].append({
					'match': {
						'places.landskap': landskap
					}
			})

		query['bool']['must'].append(landskapShouldBool)


	# Hämtar documenter var uppteckare eller informant matchar angivet namn eller id. Exempel: (alla som heter Ragnar eller Nilsson) `person=Ragnar Nilsson` eller `person=acc1`
	if ('person' in request.GET):
		personNameQueries = request.GET['person'].split(',')

		for personNameQueryStr in personNameQueries:
			personNameQuery = personNameQueryStr.split(':')

			personShouldBool = {
				'nested': {
					'path': 'persons',
					'query': {
						'bool': {
							'must': [
								{
									'bool': {
										'should': [
											{
												'match': {
													'persons.name': personNameQuery[1] if len(personNameQuery) > 1 else personNameQuery[0]
												}
											},
											{
												'match': {
													'persons.id': personNameQueryStr
												}
											}
										]
									}
								}
							]
						}
					}
				}
			}

			if len(personNameQuery) == 2:
				personShouldBool['nested']['query']['bool']['must'].append({
					'match': {
						'persons.relation': personNameQuery[0]
					}
				})

			query['bool']['must'].append(personShouldBool)



	# Hämtar documenter var uppteckare eller informant matchar angivet helt namn. Exempel: (leter bara efter "Ragnar Nilsson") `person=Ragnar Nilsson`
	if ('person_exact' in request.GET):
		personNameQueries = request.GET['person_exact'].split(',')

		for personNameQueryStr in personNameQueries:
			personNameQuery = personNameQueryStr.split(':')

			personShouldBool = {
				'nested': {
					'path': 'persons',
					'query': {
						'bool': {
							'must': [
								{
									'match': {
										'persons.name_analysed.keyword': personNameQuery[1] if len(personNameQuery) > 1 else personNameQuery[0]
									}
								}
							]
						}
					}
				}
			}

			if len(personNameQuery) == 2:
				personShouldBool['nested']['query']['bool']['must'].append({
					'match': {
						'persons.relation': personNameQuery[0]
					}
				})

			query['bool']['must'].append(personShouldBool)


	# Hämtar documenter var uppteckare eller informant matchar angivet id.
	if ('person_id' in request.GET):
		personIdQueries = request.GET['person_id'].split(',')

		for personIdQueryStr in personIdQueries:
			personIdQuery = personIdQueryStr.split(':')

			personShouldBool = {
				'nested': {
					'path': 'persons',
					'query': {
						'bool': {
							'must': [
								{
									'match': {
										'persons.id': personIdQuery[1] if len(personIdQuery) > 1 else personIdQuery[0]
									}
								}
							]
						}
					}
				}
			}

			if len(personIdQuery) == 2:
				personShouldBool['nested']['query']['bool']['must'].append({
					'match': {
						'persons.relation': personIdQuery[0]
					}
				})

			query['bool']['must'].append(personShouldBool)


	# We mean "collector" as the person who has all possible roles that can be considered as a collector:
	# collector, interviewer, recorder
	if ('collector_id' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.id': request.GET['collector_id']
								}
							},
							{
								'bool': {
									'should': [
										{
											'match': {
												'persons.relation': 'c'
											}
										},
										{
											'match': {
												'persons.relation': 'collector'
											}
										},
										{
											'match': {
												'persons.relation': 'interviewer'
											}
										},
										{
											'match': {
												'persons.relation': 'recorder'
											}
										}
									],
									'minimum_should_match': 1
								}
						   }
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


	# We mean "informant" as the person who has all possible roles that can be considered as an informant:
	# informant, i
	if ('informant_id' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.id': request.GET['informant_id']
								}
							},
							{
								'bool': {
									'should': [
										{
											'match': {
												'persons.relation': 'i'
											}
										},
										{
											'match': {
												'persons.relation': 'informant'
											}
										}
									],
									'minimum_should_match': 1
								}
						   }							
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


	# We mean "collector" as the person who has all possible roles that can be considered as a collector:
	# c, collector, interviewer, recorder
	if ('collector' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									# 'persons.name.raw': request.GET['collector']
									'persons.name_analysed.keyword': request.GET['collector']
								}
							},
							{
								'bool': {
									'should': [
										{
											'match': {
												'persons.relation': 'c'
											}
										},
										{
											'match': {
												'persons.relation': 'collector'
											}
										},
										{
											'match': {
												'persons.relation': 'interviewer'
											}
										},
										{
											'match': {
												'persons.relation': 'recorder'
											}
										}
									],
									'minimum_should_match': 1
								}
						   }
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)

	# We mean "informant" as the person who has all possible roles that can be considered as an informant:
	# informant, i
	if ('informant' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									# 'persons.name.raw': request.GET['informant']
									'persons.name_analysed.keyword': request.GET['informant']
								}
							},
							{
								'bool': {
									'should': [
										{
											'match': {
												'persons.relation': 'i'
											}
										},
										{
											'match': {
												'persons.relation': 'informant'
											}
										}
									],
									'minimum_should_match': 1
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)

	# By "collector" we mean the person who has all possible roles that can be considered as a collector:
	# c, collector, interviewer, recorder
	if ('collectors_gender' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.gender': request.GET['collectors_gender']
								}
							},
							{
								'bool': {
									'should': [
										{
											'match': {
												'persons.relation': 'c'
											}
										},
										{
											'match': {
												'persons.relation': 'collector'
											}
										},
										{
											'match': {
												'persons.relation': 'interviewer'
											}
										},
										{
											'match': {
												'persons.relation': 'recorder'
											}
										}
									],
									'minimum_should_match': 1
								}
						   }
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)

	# By "informant" we mean the person who has all possible roles that can be considered as an informant:
	# informant, i
	if ('informants_gender' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.gender': request.GET['informants_gender']
								}
							},
							{
								'bool': {
									'should': [
										{
											'match': {
												'persons.relation': 'i'
											}
										},
										{
											'match': {
												'persons.relation': 'informant'
											}
										}
									],
									'minimum_should_match': 1
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


	# Hämtar documenter med koppling till personer av speciellt kön, möjligt att leta efter olika roll av personer. Exempel (informantar=män, upptecknare=kvinnor): gender=i:male,c:female
	if ('gender' in request.GET):
		genderQueries = request.GET['gender'].split(',')

		for genderQueryStr in genderQueries:
			genderQuery = genderQueryStr.split(':')

			personShouldBool = {
				'nested': {
					'path': 'persons',
					'query': {
						'bool': {
							'must': [
								{
									'match': {
										'persons.gender': genderQuery[1] if len(genderQuery) > 1 else genderQuery[0]
									}
								}
							]
						}
					}
				}
			}

			if len(genderQuery) > 1:
				personShouldBool['nested']['query']['bool']['must'].append({
					'match': {
						'persons.relation': genderQuery[0]
					}
				})

			query['bool']['must'].append(personShouldBool)

	if ('birth_years' in request.GET):
		birthYearsQueries = request.GET['birth_years'].split(',')

		for birthYearsQueryStr in birthYearsQueries:
			birthYearsQuery = birthYearsQueryStr.split(':')

			personRelation = None
			personGender = None

			if len(birthYearsQuery) == 1:
				birthYears = birthYearsQuery[0].split('-')
			elif len(birthYearsQuery) == 2:
				personRelation = birthYearsQuery[0]
				birthYears = birthYearsQuery[1].split('-')
			elif len(birthYearsQuery) == 3:
				personRelation = birthYearsQuery[0]
				personGender = birthYearsQuery[1]
				birthYears = birthYearsQuery[2].split('-')

			#birthYears = birthYearsQuery[1].split('-') if len(birthYearsQuery) > 1 else birthYearsQuery[0].split('-')

			personShouldBool = {
				'nested': {
					'path': 'persons',
					'query': {
						'bool': {
							'must': [
								{
									'range': {
										'persons.birth_year': {
											'gte': birthYears[0],
											'lt': birthYears[1]
										}
									}
								}
							]
						}
					}
				}
			}

			if personRelation and personRelation.lower() != 'all':
				personShouldBool['nested']['query']['bool']['must'].append({
					'match': {
						'persons.relation': personRelation
					}
				})

			if personGender and personRelation.lower() != 'all':
				personShouldBool['nested']['query']['bool']['must'].append({
					'match': {
						'persons.gender': personGender
					}
				})

			query['bool']['must'].append(personShouldBool)

	# We mean "collector" as the person who has all possible roles that can be considered as a collector:
	# c, collector, interviewer, recorder
	if ('collectors_birth_years' in request.GET):
		birthYears = request.GET['collectors_birth_years'].split(',')

		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'range': {
									'persons.birth_year': {
										'gte': birthYears[0],
										'lt': birthYears[1]
									}
								}
							},
							{
								'bool': {
									'should': [
										{
											'match': {
												'persons.relation': 'c'
											}
										},
										{
											'match': {
												'persons.relation': 'collector'
											}
										},
										{
											'match': {
												'persons.relation': 'interviewer'
											}
										},
										{
											'match': {
												'persons.relation': 'recorder'
											}
										}
									],
									'minimum_should_match': 1
								}
						   }
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)

	# We mean "informant" as the person who has all possible roles that can be considered as an informant:
	# informant, i
	if ('informants_birth_years' in request.GET):
		birthYears = request.GET['informants_birth_years'].split(',')

		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'range': {
									'persons.birth_year': {
										'gte': birthYears[0],
										'lt': birthYears[1]
									}
								}
							},
							{
								'bool': {
									'should': [
										{
											'match': {
												'persons.relation': 'i'
											}
										},
										{
											'match': {
												'persons.relation': 'informant'
											}
										}
									],
									'minimum_should_match': 1
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


	if ('terms' in request.GET):
		termsShouldBool = {
			'nested': {
				'path': 'topics_10_10',
				'query': {
					'bool': {
						'must': []
					}
				}
			}
		}

		termstrings = request.GET['terms'].split(',')

		for topic in termstrings:
			termsShouldBool['nested']['query']['bool']['must'].append({
				'nested': {
					'path': 'topics_10_10.terms',
					'query': {
						'bool': {
							'should': [
								{
									'function_score': {
										'query': {
											'match': {
												'topics_10_10.terms.term': topic
											}
										},
										'functions': [
											{
												'field_value_factor': {
													'field': 'topics_10_10.terms.probability'
												}
											}
										]
									}
								}
							]
						}
					}
				}
			})

		query['bool']['must'].append(termsShouldBool)

	if ('title_terms' in request.GET):
		titleTermsShouldBool = {
			'nested': {
				'path': 'title_topics_10_10',
				'query': {
					'bool': {
						'must': []
					}
				}
			}
		}

		titleTermsStrings = request.GET['title_terms'].split(',')

		for topic in titleTermsStrings:
			titleTermsShouldBool['nested']['query']['bool']['must'].append({
				'nested': {
					'path': 'title_topics_10_10.terms',
					'query': {
						'bool': {
							'should': [
								{
									'function_score': {
										'query': {
											'match': {
												'title_topics_10_10.terms.term': topic
											}
										},
										'functions': [
											{
												'field_value_factor': {
													'field': 'title_topics_10_10.terms.probability'
												}
											}
										]
									}
								}
							]
						}
					}
				}
			})

		query['bool']['must'].append(titleTermsShouldBool)

	# Hämtar dokument som liknar angivet document (id)
	# Använder more_like_this query, parametrar kan anges via api url params (min_word_length, min_term_freq, max_query_terms, minimum_should_match)
	if ('similar' in request.GET):
		query['bool']['must'].append({
			'more_like_this' : {
				'fields' : ['text', 'title'],
				'like' : [
					{
						'_index' : es_config.index_name,
						# '_type' : 'legend',
						'_id' : request.GET['similar']
					}
				],

				'min_word_length': int(request.GET['min_word_length']) if 'min_word_length' in request.GET else 4,
				'min_term_freq' : int(request.GET['min_term_freq']) if 'min_term_freq' in request.GET else 2,
				'max_query_terms' : int(request.GET['max_query_terms']) if 'max_query_terms' in request.GET else 25,
				'minimum_should_match' : request.GET['minimum_should_match'] if 'minimum_should_match' in request.GET else '30%'
			}
		})

	# Hämtar dokument var place (socken) coordinator finns inom angived geo_box (top,left,bottom,right)
	if ('geo_box' in request.GET):
		latLngs = request.GET['geo_box'].split(',')
		query['bool']['must'].append({
			'nested': {
				'path': 'places',
				'query': {
					'bool': {
						'must': {
							'geo_bounding_box' : {
								'places.location' : {
									'top_left' : {
										'lat' : latLngs[0],
										'lon' : latLngs[1]
									},
									'bottom_right' : {
										'lat' : latLngs[2],
										'lon' : latLngs[3]
									}
								}
							}
						}
					}
				}
			}
		})

	# Hämtar dokument som måste innehålla socken object (places)
	if ('only_geography' in request.GET and request.GET['only_geography'].lower() == 'true'):
		query['bool']['must'].append({
			'nested': {
				'path': 'places',
				'query': {
					'bool': {
						'filter': {
							'exists': {
								'field': 'places'
							}
						}
					}
				}
			}
		})

	# Hämtar dokument som måste finnas i en kategory, kollar om taxonomy.category existerar
	if ('only_categories' in request.GET and request.GET['only_categories'].lower() == 'true'):
		query['bool']['must'].append({
			'exists': {
				'field': 'taxonomy.category'
			}
		})

	# Hämtar dokument som har kategorityp(er):
	if ('categorytypes' in request.GET or data_restriction == 'opendata'):
		categorytypes_should_bool = {
			'bool': {
				'should': []
			}
		}
		categorytypes_strings = []
		if ('categorytypes' in request.GET):
			categorytypes_strings = request.GET['categorytypes'].split(',')

		if data_restriction == 'opendata':
			# For restriction opendata
			if 'sägner' not in categorytypes_strings:
				categorytypes_strings.append('sägner')
			# if 'tradark' not in categorytypes_strings:
				# categorytypes_strings.append('tradark')

		for categorytype in categorytypes_strings:
			categorytypes_should_bool['bool']['should'].append({
				'match': {
					'taxonomy.type': categorytype
				}
			})
		query['bool']['must'].append(categorytypes_should_bool)

	# Hämtar dokument från angivet land
	if ('country' in request.GET or data_restriction == 'opendata'):
		country_string = ''
		if ('country' in request.GET):
			country_string = request.GET['country'].lower()

		if  data_restriction == 'opendata':
			# For restriction opendata
			if 'sweden' not in country_string:
				country_string = 'sweden'
		query['bool']['must'].append({
			'term': {
				'archive.country': country_string.lower()
			}
		})

	# Hämtar dokument från angivet arkiv (arkiv är dock inte standardiserad i databasen)
	if ('archive' in request.GET):
		query['bool']['must'].append({
			'term': {
				'archive.archive.keyword': request.GET['archive']
			}
		})

	# Hämtar dokument med angiven range på angivet fält
	if ('range' in request.GET):
		range = request.GET['range'].replace('PLUS','+').split(',')
		query['bool']['must'].append({
			'range': {
				range[0]: {
					'from': range[1],
					'to': range[2]
				}
			}
		})

	# Hämtar dokument vars id börjar på angiven sträng
	if ('id_prefix' in request.GET):
		query['bool']['must'].append({
			'prefix': {
				'id.keyword': request.GET['id_prefix']
			}
		})
	
	return query

def esQuery(request, query, formatFunc = None, apiUrl = None, returnRaw = False):
	# Function som formulerar query och anropar ES

	# Tar in request (Django Rest API request), Elasticsearch query som skapas av createQuery och formatFunc

	# formatFunc:
	# function som formaterar resultatet som kom kommer från ES och skickar vidare (return JsonResponse(outputData))
	# formatFunc är definerad av metoder (enpoints) som anropar ES (se t.ex. getDocuments)

	# apiUrl: override url i config

	# returnRaw: levererar raw outputData som python objekt, om returnRaw är inte 'true' levereras outputData som json

	host = es_config.host
	protocol = es_config.protocol
	index_name = es_config.index_name
	user = None
	password = None
	if hasattr(es_config, 'user'):
		user = es_config.user
		password = es_config.password
	#Check if application has extra index configuration
	host, index_name, password, protocol, user = getExtraIndexConfiguration(host, index_name, password, protocol,
																			request, user)

	authentication_type_ES8 = False
	if hasattr(es_config, 'es_version'):
		if (es_config.es_version == '8'):
			authentication_type_ES8 = True
	# Anropar ES, bygger upp url från es_config och skickar data som json (query)
	# Old authentication up to version 7 with user in url
	esUrl = protocol + (user + ':' + password + '@' if (user is not None) else '') + host + '/' + index_name + (apiUrl if apiUrl else '/_search')
	# New authentication from version 8 has not user i url
	esUrl = protocol+host+'/'+index_name+(apiUrl if apiUrl else '/_search')
	if authentication_type_ES8 == True:
		pass

	query_request = {}
	if 'query' in query:
		if query['query']:
			query_request = query
			# From ES7: add track_total_hits to query without aggregation to get total value to count above 10000:
			if not 'aggs' in query:
				#query_request['track_total_hits'] = 100000
				query_request['track_total_hits'] = True
				track_total_hits = {
					"track_total_hits": True,
				}
			#track_total_hits.append(query_request)
			#query_request[].append(track_total_hits)
		#			logger.debug(query['query'])
		else:
			# Remove queryObject if it is empty (Elasticsearch 7 seems to not like empty query object)
			query.pop('query', None)

	headers = {'Accept': 'application/json', 'content-type': 'application/json'}

	#print("url, query %s %s", esUrl, query)
	query_json = query
	#query_json = json.dumps(query, indent=2, sort_keys=True)
	logger.debug("esQuery authentication_type_ES8, user, url, query: %s %s %s %s", authentication_type_ES8, user, esUrl, query_json)
	try:
		if authentication_type_ES8 == True and user is not None:
			esResponse = requests.get(esUrl,
									  auth=HTTPBasicAuth(user, password),
									  data=json.dumps(query),
									  verify=False,
									  headers=headers,
									  timeout=60)
		else:
			esResponse = requests.get(esUrl,
									  data=json.dumps(query),
									  verify=False,
									  headers=headers,
									  timeout=60)
	except Exception as e:
		logger.error(f"esQuery requests.get Exception: {e}")

	# Tar emot svaret som json
	if esResponse.status_code != 200:
		logger.error("esQuery requests.get: Exception %s ", esResponse.text)
		if esResponse.json() is not None:
			logger.error("Exception: Exception json %s ", esResponse.json())
	responseData = esResponse.json()
	message = esResponse.status_code
	#if 'error' in responseData:
	#message = message + responseData.get('error')
	logger.debug("response status_code %s %s ", message, responseData)

	if (formatFunc):
		# Om det finns formatFunc formatterar vi svaret och lägger i outputData.data
		outputData = {
			'data': formatFunc(responseData)
		}
	else:
		# Om formatFunc finns inte lägger vi responseData direkt till outputData
		outputData = responseData

	# Lägger till metadata section till outputData med information om total dokument och tiden som det tog för ES att hämta data
	outputData['metadata'] = {
		'total': responseData['hits']['total'] if 'hits' in responseData else 0,
		'took': responseData['took'] if 'took' in responseData else 0
	}

	# Om aggregations finns i responseData lägger vi det till outputData.aggregations,
	# förutom om vi har lagt till 'add_aggregations=false' till url:et
	# detta för att skicka mindre data till klienten om vi inte behöver aggregations
	if 'aggregations' in responseData and ('add_aggregations' not in request.GET or request.GET['add_aggregations'] != 'false'):
		outputData['aggregations'] = responseData['aggregations']
	else:
		outputData['aggregations'] = None

	# Om vi har lagt till 'showQuery=true' till url:et lägger vi hela querien till outputData.metadata
	if request is not None and ('showQuery' in request.GET) and request.GET['showQuery']:
		outputData['metadata']['query'] = query

	# If returnRaw leverar vi outputData som objekt, men annars som JsonResponse med Access-Control-Allow-Origin header
	# returnRaw används av functioner som behandlar svaret från esQuery och inte leverarar outputData direkt som svar till Rest API
	if returnRaw:
		return outputData
	else:
		jsonResponse = JsonResponse(outputData)
		jsonResponse['Access-Control-Allow-Origin'] = '*'

		return jsonResponse


def getExtraIndexConfiguration(host, index_name, password, protocol, request, user):
	if (hasattr(es_config, 'index_list')):
		if ('index' in request.GET):
			# Get index from request
			index = request.GET['index']
			index_config = es_config.index_list[index]
			# Get index configuration for this request
			if index_config is not None:
				if ('index' in index_config):
					index_name = index_config['index']
				if ('host' in index_config):
					host = index_config['host']
				if ('protocol' in index_config):
					protocol = index_config['protocol']
				if ('user' in index_config):
					user = index_config['user']
				if ('password' in index_config):
					password = index_config['password']
	return host, index_name, password, protocol, user



def getDocument(request, documentId):
	host = es_config.host
	protocol = es_config.protocol
	index_name = es_config.index_name
	user = None
	password = None

	#Check if application has extra index configuration
	host, index_name, password, protocol, user = getExtraIndexConfiguration(host, index_name, password, protocol,
																			request, user)
	# Hämtar enda dokument, använder inte esQuery för den anropar ES direkt
	esResponse = requests.get(protocol+(user+':'+password+'@' if (user is not None) else '')+host+'/'+index_name+'/_doc/'+documentId, verify=False)

	jsonResponse = JsonResponse(esResponse.json())
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse


def getRandomDocument(request):
	query = {
		'size': 1,
		'query': {
			'function_score': {
				'random_score': {
					'seed': randint(0, 1000000)
				},
				'query': createQuery(request)
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query)
	return esQueryResponse

def getTerms(request):
	# Aggrigerar terms (topic_10_10 fält)

	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'term': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['buckets']))

	if ('count' in request.GET):
		count = request.GET['count']
	else:
		count = 100

	if ('sort' in request.GET):
		order = request.GET['sort']
	else:
		order = '_count'

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'topics_10_10'
				},
				'aggs': {
					'data': {
						'nested': {
							'path': 'topics_10_10.terms'
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'topics_10_10.terms.term',
									'size': count,
									'order': {
										order: 'desc'
									}
								},
								'aggs': {
									'parent_doc_count': {
										'reverse_nested': {}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTermsAutocomplete(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'term': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['data']['buckets']))

	if ('count' in request.GET):
		count = request.GET['count']
	else:
		count = 100

	query = {
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'topics_10_10'
				},
				'aggs': {
					'data': {
						'nested': {
							'path': 'topics.10_10.terms'
						},
						'aggs': {
							'data': {
								'filter': {
									'bool': {
										'must': {
											'regexp': {
												'topics.10_10.terms.term': request.GET['search']+'.+'
											}
										}
									}
								},
								'aggs': {
									'data': {
										'terms': {
											'order': {
												'_count': 'desc'
											},
											'size': count,
											'field': 'topics_10_10.terms.term'
										},
										'aggs': {
											'parent_doc_count': {
												'reverse_nested': {}
											}
										}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTitleTerms(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'term': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['buckets']))

	if ('count' in request.GET):
		count = request.GET['count']
	else:
		count = 100

	if ('count' in request.GET):
		count = request.GET['count']
	else:
		count = 100

	if ('order' in request.GET):
		order = request.GET['order']
	else:
		order = '_count'

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'title_topics_10_10'
				},
				'aggs': {
					'data': {
						'nested': {
							'path': 'title_topics_10_10.terms'
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'title_topics_10_10.terms.term',
									'size': count,
									'order': {
										order: 'desc'
									}
								},
								'aggs': {
									'parent_doc_count': {
										'reverse_nested': {}
									},
									'probability_avg': {
										'avg': {
											'field': 'title_topics_10_10.terms.probability'
										}
									},
									'probability_max': {
										'max': {
											'field': 'title_topics_10_10.terms.probability'
										}
									},
									'probability_median': {
										'percentiles': {
											'field': 'title_topics_10_10.terms.probability',
											'percents': [
												50
											]
										}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTitleTermsAutocomplete(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'term': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['data']['buckets']))

	if ('count' in request.GET):
		count = request.GET['count']
	else:
		count = 100

	query = {
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'title_topics_10_10'
				},
				'aggs': {
					'data': {
						'nested': {
							'path': 'title_topics_10_10.terms'
						},
						'aggs': {
							'data': {
								'filter': {
									'bool': {
										'must': {
											'regexp': {
												'title_topics_10_10.terms.term': request.GET['search']+'.+'
											}
										}
									}
								},
								'aggs': {
									'data': {
										'terms': {
											'order': {
												'_count': 'desc'
											},
											'size': count,
											'field': 'title_topics_10_10.terms.term'
										},
										'aggs': {
											'parent_doc_count': {
												'reverse_nested': {}
											}
										}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getCollectionYearsTotal(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	query = {
		'size': 0,
		'aggs': {
			'data': {
				'terms': {
					'field': 'materialtype',
					'size': 10000,
					'order': {
						'_key': 'asc'
					}
				}
			}
		}
	}

	response = {}

	typesResponse = esQuery(request, query, None, None, True)

	for type in typesResponse['aggregations']['data']['buckets']:
		query = {
			'query': {
				'query_string': {
					'query': 'materialtype: '+type['key']
				}
			},
			'size': 0,
			'aggs': {
				'data': {
					'filter': {
						'range': {
							'year': {
								'lte': 2020
							}
						}
					},
					'aggs': {
						'data': {
							'date_histogram' : {
								'field' : 'year',
								'interval' : 'year',
								'format': 'yyyy'
							}
						}
					}
				}
			}
		}

		queryResponse = esQuery(request, query, jsonFormat, None, True)

		response[type['key']] = type['doc_count'] = queryResponse


	jsonResponse = JsonResponse(response)
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getCollectionYears(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'filter': {
					'range': {
						'year': {
							'lte': 2020
						}
					}
				},
				'aggs': {
					'data': {
						'date_histogram' : {
							'field' : 'year',
							'interval' : 'year',
							'format': 'yyyy'
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getBirthYearsTotal(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		ret = {}

		for agg in json['aggregations']:
			if 'buckets' in json['aggregations'][agg]['data']:
				ret[agg] = list(map(itemFormat, json['aggregations'][agg]['data']['buckets']))
			elif 'buckets' in json['aggregations'][agg]['data']['data']:
				ret[agg] = list(map(itemFormat, json['aggregations'][agg]['data']['data']['buckets']))

		return ret

	query = {
		'size': 0,
		'aggs': {
			'data': {
				'terms': {
					'field': 'materialtype',
					'size': 10000,
					'order': {
						'_key': 'asc'
					}
				}
			}
		}
	}

	def createAggregations(roles):
		aggs = {
			'all': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'date_histogram' : {
							'field' : 'persons.birth_year',
							'interval' : 'year',
							'format': 'yyyy'
						},
						'aggs': {
							'person_count': {
								'cardinality': {
									'field': 'persons.id'
								}
							}
						}
					}
				}
			}
		}

		for role in roles:
			aggs[role] = {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': role
							}
						},
						'aggs': {
							'data': {
								'date_histogram' : {
									'field' : 'persons.birth_year',
									'interval' : 'year',
									'format': 'yyyy'
								},
								'aggs': {
									'person_count': {
										'cardinality': {
											'field': 'persons.id'
										}
									}
								}
							}
						}
					}
				}
			}

		return aggs

	roles = getPersonRoles(None)

	response = {}

	typesResponse = esQuery(request, query, None, None, True)

	for type in typesResponse['aggregations']['data']['buckets']:
		query = {
			'query': {
				'query_string': {
					'query': 'materialtype: '+type['key']
				}
			},
			'size': 0,
			'aggs': createAggregations(roles)
		}

		queryResponse = esQuery(request, query, jsonFormat, None, True)

		response[type['key']] = type['doc_count'] = queryResponse


	jsonResponse = JsonResponse(response)
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getBirthYears(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		ret = {}

		for agg in json['aggregations']:
			if 'buckets' in json['aggregations'][agg]['data']:
				ret[agg] = list(map(itemFormat, json['aggregations'][agg]['data']['buckets']))
			elif 'buckets' in json['aggregations'][agg]['data']['data']:
				ret[agg] = list(map(itemFormat, json['aggregations'][agg]['data']['data']['buckets']))

		return ret

	def createAggregations(roles):
		aggs = {
			'all': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'date_histogram' : {
							'field' : 'persons.birth_year',
							'interval' : 'year',
							'format': 'yyyy'
						},
						'aggs': {
							'person_count': {
								'cardinality': {
									'field': 'persons.id'
								}
							}
						}
					}
				}
			}
		}

		for role in roles:
			aggs[role] = {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': role
							}
						},
						'aggs': {
							'data': {
								'date_histogram' : {
									'field' : 'persons.birth_year',
									'interval' : 'year',
									'format': 'yyyy'
								},
								'aggs': {
									'person_count': {
										'cardinality': {
											'field': 'persons.id'
										}
									}
								}
							}
						}
					}
				}
			}

		return aggs

	roles = getPersonRoles(request)

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': createAggregations(roles)
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getCategories(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		retObj = {
			'key': item['key'],
			'doc_count': item['doc_count']
		}

		if len(item['data']['buckets']) > 0:
			retObj['name'] = item['data']['buckets'][0]['key']

			if len(item['data']['buckets'][0]['data']['buckets']) > 0:
				retObj['type'] = item['data']['buckets'][0]['data']['buckets'][0]['key']

		return retObj

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['buckets']))

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'terms': {
					'field': 'taxonomy.category',
					'size': 10000
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'taxonomy.name',
							'size': 10000
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'taxonomy.type'
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getCategoryTypes(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		retObj = {
			'key': item['key'],
			'doc_count': item['doc_count']
		}

		return retObj

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['buckets']))

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'terms': {
					'field': 'taxonomy.type',
					'size': 10000
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTypes(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'type': item['key'],
			'doc_count': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['buckets']))

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'terms': {
					'field': 'materialtype',
					'size': 10000,
					'order': {
						'_key': 'asc'
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getMediaCount(request):
	"""
	Returns number of media files (representing pages) for a record id

	parameters:
	-search (same name as /count): id prefix
	-transcriptionstatus

	 Return:
	 	value (same name as /count): Number of media files in media

	 Test:
	 http://127.0.0.1:8000/api/es/mediacount/?search=liu00198_194713_
	 http://127.0.0.1:8000/api/es/mediacount/?search=liu00198_194713_&transcriptionstatus=published,autopublished
	"""

	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			# 'type': item['key'],
			'value': item['value']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return itemFormat(json['aggregations']['sub_values_count'])

	if "search" in request.GET:
		record_id = request.GET['search']

	query = {
		'size': 0,
		#'query': createQuery(request),
		"query": {
			"bool": {
				"must": [
					{
						"prefix": {
							"id": record_id
						}
					}
				]
			}
		},
		"aggs": {
			"sub_values_count": {
				"scripted_metric": {
					"init_script": "state['count'] = 0",
					"map_script": "if (doc.containsKey('media.source.keyword')) { state.count += doc['media.source.keyword'].length }",
					"combine_script": "return state",
					"reduce_script": "int totalCount = 0; for (state in states) { totalCount += state.count } return totalCount"
				}
			}
		},
	}

	"""
	if "id" in request.GET:
		record_id = request.GET['id']
		query['query']['bool'].append({
			"bool": {
				"must": [
					{
						"prefix": {
							"id": record_id
						}
					}
				]
			}
		})
	"""

	if "transcriptionstatus" in request.GET:
		transcriptionstatus_strings = request.GET['transcriptionstatus'].split(',')

		# query['query']['bool'].append(transcriptionstatus_filter)
		query['query']['bool'].update({
			"filter": {
				"terms": {
					"media.transcriptionstatus": transcriptionstatus_strings
				}
			}
		})

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getSockenTotal(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'harad': item['harad']['buckets'][0]['key'] if len(item['harad']['buckets']) > 0 else None,
			'landskap': item['landskap']['buckets'][0]['key'] if len(item['landskap']['buckets']) > 0 else None,
			'lan': item['lan']['buckets'][0]['key'] if len(item['lan']['buckets']) > 0 else None,
			'lm_id': item['lm_id']['buckets'][0]['key'] if len(item['lm_id']['buckets']) > 0 else '',
			'location': geohash.decode(item['location']['buckets'][0]['key']),
			'doc_count': item['data']['buckets'][0]['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	query = {
		'size': 0,
		'aggs': {
			'data': {
				'terms': {
					'field': 'materialtype',
					'size': 10000,
					'order': {
						'_key': 'asc'
					}
				}
			}
		}
	}

	response = {}

	typesResponse = esQuery(request, query, None, None, True)

	for type in typesResponse['aggregations']['data']['buckets']:
		query = {
			'query': {
				'query_string': {
					'query': 'materialtype: '+type['key']
				}
			},
			'size': 0,
			'aggs': {
				'data': {
					'nested': {
						'path': 'places'
					},
					'aggs': {
						'data': {
							'terms': {
								'field': 'places.id',
								'size': 10000
							},
							'aggs': {
								'data': {
									'terms': {
										'field': 'places.name',
										'size': 1,
										'order': {
											'_key': 'asc'
										}
									}
								},
								'harad': {
									'terms': {
										'field': 'places.harad',
										'size': 1,
										'order': {
											'_key': 'asc'
										}
									}
								},
								'landskap': {
									'terms': {
										'field': 'places.landskap',
										'size': 1,
										'order': {
											'_key': 'asc'
										}
									}
								},
								'lan': {
									'terms': {
										'field': 'places.county',
										'size': 1,
										'order': {
											'_key': 'asc'
										}
									}
								},
								'location': {
									'geohash_grid': {
										'field': 'places.location',
										'precision': 12
									}
								},
								'lm_id': {
									'terms': {
										'field': 'places.lm_id',
										'size': 1,
										'order': {
											'_key': 'asc'
										}
									}
								}
							}
						}
					}
				}
			}
		}

		queryResponse = esQuery(request, query, jsonFormat, None, True)

		response[type['key']] = type['doc_count'] = queryResponse


	jsonResponse = JsonResponse(response)
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getSocken(request, sockenId = None):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'harad': item['harad']['buckets'][0]['key'] if len(item['harad']['buckets']) > 0 else None,
			'landskap': item['landskap']['buckets'][0]['key'] if len(item['landskap']['buckets']) > 0 else None,
			'lan': item['lan']['buckets'][0]['key'] if len(item['lan']['buckets']) > 0 else None,
			'lm_id': item['lm_id']['buckets'][0]['key'] if len(item['lm_id']['buckets']) > 0 else '',
			'location': geohash.decode(item['location']['buckets'][0]['key']),
			'doc_count': item['parent_doc_count']['doc_count'],
			'page_count': item['page_count']['pages']['value'],
			'relation_type': [relation_type['key'] for relation_type in item['relation_type']['buckets'] if len(item['relation_type']['buckets']) > 0]
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		if sockenId is not None:
			socken = [item for item in map(itemFormat, json['aggregations']['data']['data']['buckets']) if item['id'] == sockenId]
			return socken[0]
		else:
			return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	if sockenId is not None:
		queryObject = {
			'bool': {
				'must': [
					{
						'nested': {
						'path': 'places',
						'query': {
							'bool': {
								'should': [
									{
										'match': {
											'places.id': sockenId
										}
									}
								]
							}
						}
					}
				}
			]
		}
	}
	else:
		queryObject = createQuery(request)

	query = {
		'query': queryObject,
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'places'
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'places.id',
							'size': 10000
						},
						'aggs': {
							'page_count': {
								'reverse_nested': {},
								'aggs': {
									'pages': {
										'sum': {
											'field': 'archive.total_pages'
										}
									}
								}
							},
							'data': {
								'terms': {
									'field': 'places.name',
									'size': 1,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'parent_doc_count': {
								'reverse_nested': {}
							},
							'harad': {
								'terms': {
									'field': 'places.harad',
									'size': 1,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'landskap': {
								'terms': {
									'field': 'places.landskap',
									'size': 1,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'lan': {
								'terms': {
									'field': 'places.county',
									'size': 1,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'location': {
								'geohash_grid': {
									'field': 'places.location',
									'precision': 12
								}
							},
							'lm_id': {
								'terms': {
									'field': 'places.lm_id',
									'size': 1,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'relation_type': {
								'terms': {
									'field': 'places.type',
									'size': 100,
									'order': {
										'_key': 'asc'
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat, None, True)
	logger.debug("getSocken url, query %s %s", request, query)

	if ('mark_metadata' in request.GET):
		if not 'bool' in query['query']:
			query['query'] = {
				'bool': {
					# we use should, so that one of the conditions
					# must be met, but not all of them
					'should': []
				}
			}
		# Get data to calculate flag on socken for quick map selection and different map symbol, currently using  value 'has_metadata"
		if request.GET['mark_metadata'] == 'transcriptionstatus':
			query['query']['bool']['must'].append({
				'match': {
					'transcriptionstatus': 'readytotranscribe'
				}
			})
		else:
			query['query']['bool']['must'].append({
				'match': {
					'metadata.type': request.GET['mark_metadata']
				}
			})
		metadataSockenResponse = esQuery(request, query, jsonFormat, None, True)
		logger.debug("getSocken url, query %s %s", request, query)

		sockenJson = esQueryResponse

		for socken in sockenJson['data']:
			socken['has_metadata'] = any(s['id'] == socken['id'] for s in metadataSockenResponse['data'])

	jsonResponse = JsonResponse(esQueryResponse)
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getLetters(request, sockenId = None):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		ret = {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'harad': item['harad']['buckets'][0]['key'] if len(item['harad']['buckets']) > 0 else None,
			'landskap': item['landskap']['buckets'][0]['key'] if len(item['landskap']['buckets']) > 0 else None,
			'lan': item['lan']['buckets'][0]['key'] if len(item['lan']['buckets']) > 0 else None,
			'lm_id': item['lm_id']['buckets'][0]['key'] if len(item['lm_id']['buckets']) > 0 else '',
			'location': geohash.decode(item['location']['buckets'][0]['key'])
		}

		if 'destination_places' in item:
			ret['destinations'] = subItemListFormat(item)

		return ret

	def subItemListFormat(subItem):
		return [item for item in map(itemFormat, subItem['destination_places']['sub']['places']['places']['buckets'])]

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		if sockenId is not None:
			socken = [item for item in map(itemFormat, json['aggregations']['data']['data']['buckets']) if item['id'] == sockenId]
			return socken[0]
		else:
			return list(map(itemFormat, json['aggregations']['letters']['dispatch_places']['places']['buckets']))

	if sockenId is not None:
		queryObject = {
			'bool': {
				'must': [
					{
						'nested': {
						'path': 'places',
						'query': {
							'bool': {
								'should': [
									{
										'match': {
											'places.id': sockenId
										}
									}
								]
							}
						}
					}
				}
			]
		}
	}
	else:
		queryObject = createQuery(request)

	query = {
		'query': queryObject,
		'size': 0,
		'aggs': {
			'letters': {
				'aggs': {
					'dispatch_places': {
						'aggs': {
							'places': {
								'aggs': {
									'data': {
										'terms': {
											'field': 'places.name',
											'order': {
												'_key': 'asc'
											},
											'size': 1
										}
									},
									'destination_places': {
										'aggs': {
											'sub': {
												'aggs': {
													'places': {
														'aggs': {
															'places': {
																'aggs': {
																	'data': {
																		'terms': {
																			'field': 'places.name',
																			'order': {
																				'_key': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'harad': {
																		'terms': {
																			'field': 'places.harad',
																			'order': {
																				'_key': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'lan': {
																		'terms': {
																			'field': 'places.county',
																			'order': {
																				'_key': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'landskap': {
																		'terms': {
																			'field': 'places.landskap',
																			'order': {
																				'_key': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'lm_id': {
																		'terms': {
																			'field': 'places.lm_id',
																			'order': {
																				'_key': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'location': {
																		'geohash_grid': {
																			'field': 'places.location',
																			'precision': 12
																		}
																	}
																},
																'terms': {
																	'field': 'places.id',
																	'size': 1000
																}
															}
														},
														'filter': {
															'term': {
																'places.type': 'destination_place'
															}
														}
													}
												},
												'nested': {
													'path': 'places'
												}
											}
										},
										'reverse_nested': {}
									},
									'harad': {
										'terms': {
											'field': 'places.harad',
											'order': {
												'_key': 'asc'
											},
											'size': 1
										}
									},
									'lan': {
										'terms': {
											'field': 'places.county',
											'order': {
												'_key': 'asc'
											},
											'size': 1
										}
									},
									'landskap': {
										'terms': {
											'field': 'places.landskap',
											'order': {
												'_key': 'asc'
											},
											'size': 1
										}
									},
									'lm_id': {
										'terms': {
											'field': 'places.lm_id',
											'order': {
												'_key': 'asc'
											},
											'size': 1
										}
									},
									'location': {
										'geohash_grid': {
											'field': 'places.location',
											'precision': 12
										}
									}
								},
								'terms': {
									'field': 'places.id',
									'size': 1000
								}
							}
						},
						'filter': {
							'term': {
								'places.type': 'dispatch_place'
							}
						}
					}
				},
				'nested': {
					'path': 'places'
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat, None, True)

	if ('mark_metadata' in request.GET):
		if not 'bool' in query['query']:
			query['query'] = {
				'bool': {
					'must': []
				}
			}
		query['query']['bool']['must'].append({
			'match': {
				'metadata.type': request.GET['mark_metadata']
			}
		})
		metadataSockenResponse = esQuery(request, query, jsonFormat, None, True)

		sockenJson = esQueryResponse

		for socken in sockenJson['data']:
			socken['has_metadata'] = any(s['id'] == socken['id'] for s in metadataSockenResponse['data'])

	jsonResponse = JsonResponse(esQueryResponse)
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getLandskapAutocomplete(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'id': item['key'],
			'name': item['key'],
			'doc_count': item['doc_count']
		}
	
	def jsonFormat(response):
		return list(map(itemFormat, response['aggregations']['data']['data']['data']['buckets']))
	
	newRegExString = ''
	for char in request.GET['search']:
		if char == '[' or char == ']':
			newRegExString += '\\' + char
		else:
			newRegExString += '[' + char.lower() + char.upper() + ']'

	
	# query objekt som skickas till esQuery
	query = {
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'places'
			},
			'aggs': {
				'data': {
					'filter': {
						'bool': {
							'must': [
								{
									'regexp': {
										'places.landskap': {
											'value': '(.+)?' + newRegExString + '(.+)?',
											'case_insensitive': True
										}
									}
								}
							]
						}
					},
					'aggs': {
						'data': {
							'terms': {
								'field': 'places.landskap',
								'size': 1000,
								'order': {
									'_key': 'asc'
								}
							}
						}
					}
				}
			}
		}
	}
	}
		
	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse



def getSockenAutocomplete(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'harad': item['harad']['buckets'][0]['key'] if len(item['harad']['buckets']) > 0 else '',
			'landskap': item['landskap']['buckets'][0]['key'] if len(item['landskap']['buckets']) > 0 else '',
			'lan': item['lan']['buckets'][0]['key'] if len(item['lan']['buckets']) > 0 else '',
			'lm_id': item['lm_id']['buckets'][0]['key'] if len(item['lm_id']['buckets']) > 0 else '',
			'location': geohash.decode(item['location']['buckets'][0]['key']),
			'comment': item['comment']['buckets'][0]['key'] if ('comment' in item and len(item['comment']['buckets']) > 0) else '',
			'doc_count': item['data']['buckets'][0]['doc_count'],
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['buckets']))
	
	# Skapar en ny string som är en regex som matchar alla bokstäver i söksträngen oavsett om de är stora eller små
	# Detta behövs för att case_insensitive inte fungerar med åäö och andra icke-ASCII tecken
	newRegExString = ''
	for char in request.GET['search']:
		if char == '[' or char == ']':
			newRegExString += '\\' + char
		else:
			newRegExString += '[' + char.lower() + char.upper() + ']'

	query = {
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'places'
				},
				'aggs': {
					'data': {
						'filter': {
							'bool': {
								'must': [
									{
										'bool': 
										{
											'should': [
												{
													'regexp': {
														'places.name': { 
															'value': '(.+?)'+newRegExString+'(.+?)',
															'case_insensitive': True,
														}
													}
												},
												{
													'regexp': {
														'places.comment.keyword': {
															'value': '(.+?)'+newRegExString+'(.+?)',
															'case_insensitive': True,
														}
													}
												}
											]
										}
									}
								]
							}
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'places.name',
									'size': 10000,
									'order': {
										'_key': 'asc',
									}
								},
								'aggs': {
									'data': {
										'terms': {
											'field': 'places.name',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'harad': {
										'terms': {
											'field': 'places.harad',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'landskap': {
										'terms': {
											'field': 'places.landskap',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'lan': {
										'terms': {
											'field': 'places.county',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'location': {
										'geohash_grid': {
											'field': 'places.location',
											'precision': 12
										}
									},
									'comment': {
										'terms': {
											'field': 'places.comment.keyword',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'lm_id': {
										'terms': {
											'field': 'places.lm_id',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getArchiveIdsAutocomplete(request):
	# från request.GET['search'] skapar en ny regEx string som används i query. ersätt mellanslag med [0 ]{0,3}
	newRegExString = ''
	for char in request.GET['search']:
		if char == ' ':
			# [0 ]{0,3} betyder att det kan vara en 0 eller ett mellanslag, och det kan vara 0-3 av dem
			newRegExString += '[0 ]{0,3}'
		else:
			newRegExString += '[' + char.lower() + char.upper() + ']'
	
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'id': item['key'],
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['distinct_ids']['buckets']))

	query = {
		"size": 10,
		"aggs": {
			"data": {
				"filter": {
					"bool": {
						"filter": [
							{
								"regexp": {
									"archive.archive_id.keyword": {
										"value": '(.+?)'+newRegExString+'(.+?)',
										"case_insensitive": True
									}
								}
							}
						]
					}
				},
				"aggs": {
					"distinct_ids": {
						"terms": {
							"field": "archive.archive_id.keyword",
							"size": 30,
							"order": {"_key": "asc"},
						}
					}
				}
			}
		}
	}

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getHarad(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'landskap': item['landskap']['buckets'][0]['key'],
			'lan': item['lan']['buckets'][0]['key'],
			'doc_count': item['data']['buckets'][0]['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'places'
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'places.harad_id',
							'size': 10000
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'places.harad',
									'size': 10000,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'parent_doc_count': {
								'reverse_nested': {}
							},
							'landskap': {
								'terms': {
									'field': 'places.landskap',
									'size': 10000,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'lan': {
								'terms': {
									'field': 'places.county',
									'size': 10000,
									'order': {
										'_key': 'asc'
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getLandskap(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'name': item['key'],
			'doc_count': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'places'
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'places.landskap',
							'size': 10000
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getCounty(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'name': item['key'],
			'doc_count': item['doc_count']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'places'
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'places.county',
							'size': 10000
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getPersons(request, personId = None):
	# itemFormat definerar hur varje object i esQuery-resultatet ska formateras
	def itemFormat(item):
		retObj = {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'] if 0 < len(item['data']['buckets']) else 'kunde inte ladda namnet',
			'doc_count': item['doc_count']
		}

		if (len(item['birth_year']['buckets']) > 0):
			retObj['birth_year'] = item['birth_year']['buckets'][0]['key_as_string'].split('-')[0]

		if len(item['home']['buckets']) > 0:
			retObj['home'] = {
				'id': item['home']['buckets'][0]['key'],
				'name': item['home']['buckets'][0]['data']['buckets'][0]['key']
			}

		return retObj

	# jsonFormat, definerar hur esQuery-resultatet ska formateras och vilkan del som ska användas (hits eller aggregation buckets)
	def jsonFormat(json):
		if personId is not None:
			person = [item for item in map(itemFormat, json['aggregations']['data']['data']['buckets']) if item['id'] == personId]
			return person[0]
		else:
			return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	if personId is not None:
		queryObject = {
			'bool': {
				'must': [
					{
						'nested': {
						'path': 'persons',
						'query': {
							'bool': {
								'should': [
									{
										'match': {
											'persons.id': personId
										}
									}
								]
							}
						}
					}
				}
			]
		}
	}
	else:
		queryObject = createQuery(request)

	query = {
		'query': queryObject,
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'persons.id',
							'size': request.GET['count'] if 'count' in request.GET else 10000
						},
						'aggs': {
							'data': {
								'terms': {
									# 'field': 'persons.name.raw',
									'field': 'persons.name_analysed.keyword',
									'size': 1,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'birth_year': {
								'terms': {
									'field': 'persons.birth_year',
									'size': 1,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'relation': {
								'terms': {
									'field': 'persons.relation',
									'size': 1,
									'order': {
										'_key': 'asc'
									}
								}
							},
							'home': {
								'terms': {
									'field': 'persons.home.id',
									'size': 10,
									'order': {
										'_key': 'asc'
									}
								},
								'aggs': {
									'data': {
										'terms': {
											'field': 'persons.home.name',
											'size': 10,
											'order': {
												'_key': 'asc'
											}
										}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


def _getPerson(request, personId):
	query = {
		'query': {
			'filter': {
				'term': {
					'persons.id': personId
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query)
	return esQueryResponse


def getPersonsAutocomplete(request):
	""" Get list of persons for autocomplete

	Get list of persons for automcomplete

    :param request:
	Arguments for formatting response data in json
	 -relation:

    :return: documents: Fromat json.
			  May return None if no hit.

	"""

	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		retObj = {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'doc_count': item['doc_count']
		}

		if (len(item['birth_year']['buckets']) > 0):
			retObj['birth_year'] = item['birth_year']['buckets'][0]['key_as_string'].split('-')[0]

		if len(item['home']['buckets']) > 0:
			retObj['home'] = {
				'id': item['home']['buckets'][0]['key'],
				'name': item['home']['buckets'][0]['data']['buckets'][0]['key']
			}

		return retObj

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['buckets']))

	# Skapar en ny string som är en regex som matchar alla bokstäver i söksträngen oavsett om de är stora eller små
	# Detta behövs för att case_insensitive inte fungerar med åäö och andra icke-ASCII tecken
	# --------------------
	# create a new string, for every character in request.GET['search'], create a character class to match both the upper
	# and lower case version of the character
	# characters in request.get['search'] can be upper or lowercase
	# e.g. search=abc will match Abc, aBc, abC, ABC, AbC, aBC, ABc, abc
	# and search=AbC will match Abc, aBc, abC, ABC, AbC, aBC, ABc, abc
	# escape the characters [ and ]
	newRegExString = ''
	for char in request.GET['search']:
		if char == '[' or char == ']':
			newRegExString += '\\' + char
		else:
			newRegExString += '[' + char.lower() + char.upper() + ']'

	query = {
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'bool': {
								'must': [
									{
										'regexp': {
											# 'persons.name.raw': '(.+?)'+request.GET['search']+'(.+?)'
											'persons.name_analysed.keyword': {
												'value': '(.+?)'+newRegExString+'(.+?)',
												'case_insensitive': True,
											}
										}
									},
									{
										# e.g. idprefix=acc,crwd
										'regexp': {
											'persons.id': {
												'value': ('(' + ('|'.join(request.GET['idprefix'].split(',')) + ')') if 'idprefix' in request.GET else '') + '(.+?)',
												'case_insensitive': True,
											}
										}
									}
								]
							}
						},
						'aggs': {
							'data': {

								'terms': {
									'field': 'persons.id',
									'size': request.GET['count'] if 'count' in request.GET else 10000
								},
								'aggs': {
									'data': {
										'terms': {
											'field': 'persons.name_analysed.keyword',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'birth_year': {
										'terms': {
											'field': 'persons.birth_year',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'relation': {
										'terms': {
											'field': 'persons.relation',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'home': {
										'terms': {
											'field': 'persons.home.id',
											'size': 10,
											'order': {
												'_key': 'asc'
											}
										},
										'aggs': {
											'data': {
												'terms': {
													'field': 'persons.home.name',
													'size': 10,
													'order': {
														'_key': 'asc'
													}
												}
											}
										}
									}
								}

							}
						}
					}
				}
			}
		}
	}

	if ('relation' in request.GET):
		relationObj = {
			'match': {
				'persons.relation': request.GET['relation']
			}
		}
		query['aggs']['data']['aggs']['data']['filter']['bool']['must'].append(relationObj)

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


# does not work, list index out of range at 'name': item['data']['buckets'][0]['key'],
def getRelatedPersons(request, relation):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		retObj = {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'doc_count': item['doc_count'],
			'relation': item['relation']['buckets'][0]['key']
		}

		if (len(item['birth_year']['buckets']) > 0):
			retObj['birth_year'] = item['birth_year']['buckets'][0]['key_as_string'].split('-')[0]

		if len(item['home']['buckets']) > 0:
			retObj['home'] = {
				'id': item['home']['buckets'][0]['key'],
				'name': item['home']['buckets'][0]['data']['buckets'][0]['key']
			}

		return retObj

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['buckets']))

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': relation
							}
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'persons.id',
									'size': 10000
								},
								'aggs': {
									'data': {
										'terms': {
											# 'field': 'persons.name.raw'
											'field': 'persons.name_analysed.keyword',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'birth_year': {
										'terms': {
											'field': 'persons.birth_year',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'relation': {
										'terms': {
											'field': 'persons.relation',
											'size': 1,
											'order': {
												'_key': 'asc'
											}
										}
									},
									'home': {
										'terms': {
											'field': 'persons.home.id',
											'size': 10,
											'order': {
												'_key': 'asc'
											}
										},
										'aggs': {
											'data': {
												'terms': {
													'field': 'persons.home.name',
													'size': 10,
													'order': {
														'_key': 'asc'
													}
												}
											}
										}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	print(query)
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

# does not work, list index out of range at 'name': item['data']['buckets'][0]['key'],
# in the future, all roles that can be considered as informants should be added to this list:
# i, informant
# idea: the second parameter should be a list of roles
def getInformants(request):
	return getRelatedPersons(request, 'i')

# does not work, list index out of range at 'name': item['data']['buckets'][0]['key'],
# in the future, all roles that can be considered as collectors should be added to this list:
# c, collector, interviewer, recorder
# idea: the second parameter should be a list of roles
def getCollectors(request):
	return getRelatedPersons(request, 'c')

def getPersonRoles(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return item['key']

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

	roleQuery = {
		'query': createQuery(request) if request is not None else {},
		'size': 0,
		'aggs': {
			'data': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'persons.relation',
							'size': 50
						}
					}
				}
			}
		}
	}

	roles = esQuery(request, roleQuery, jsonFormat, None, True)

	return list(filter(None, roles['data']))

def getGenderTotal(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'gender': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		ret = {}

		for agg in json['aggregations']:
			if 'buckets' in json['aggregations'][agg]['data']:
				ret[agg] = list(map(itemFormat, json['aggregations'][agg]['data']['buckets']))
			elif 'buckets' in json['aggregations'][agg]['data']['data']:
				ret[agg] = list(map(itemFormat, json['aggregations'][agg]['data']['data']['buckets']))

		return ret

	query = {
		'size': 0,
		'aggs': {
			'data': {
				'terms': {
					'field': 'materialtype',
					'size': 10000,
					'order': {
						'_key': 'asc'
					}
				}
			}
		}
	}

	def createAggregations(roles):
		aggs = {
			'all': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'persons.gender',
							'size': 10000,
							'order': {
								'_key': 'asc'
							}
						},
						'aggs': {
							'person_count': {
								'cardinality': {
									'field': 'persons.id'
								}
							}
						}
					}
				}
			}
		}

		for role in roles:
			aggs[role] = {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': role
							}
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'persons.gender',
									'size': 10000,
									'order': {
										'_key': 'asc'
									}
								},
								'aggs': {
									'person_count': {
										'cardinality': {
											'field': 'persons.id'
										}
									}
								}
							}
						}
					}
				}
			}

		return aggs

	roles = getPersonRoles(None)

	response = {}

	typesResponse = esQuery(request, query, None, None, True)

	for type in typesResponse['aggregations']['data']['buckets']:
		query = {
			'query': {
				'query_string': {
					'query': 'materialtype: '+type['key']
				}
			},
			'size': 0,
			'aggs': createAggregations(roles)
		}

		queryResponse = esQuery(request, query, jsonFormat, None, True)

		response[type['key']] = type['doc_count'] = queryResponse


	jsonResponse = JsonResponse(response)
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getGender(request):
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		return {
			'gender': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		ret = {}

		for agg in json['aggregations']:
			if 'buckets' in json['aggregations'][agg]['data']:
				ret[agg] = list(map(itemFormat, json['aggregations'][agg]['data']['buckets']))
			elif 'buckets' in json['aggregations'][agg]['data']['data']:
				ret[agg] = list(map(itemFormat, json['aggregations'][agg]['data']['data']['buckets']))

		return ret

	def createAggregations(roles):
		aggs = {
			'all': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'persons.gender',
							'size': 10000,
							'order': {
								'_key': 'asc'
							}
						},
						'aggs': {
							'person_count': {
								'cardinality': {
									'field': 'persons.id'
								}
							}
						}
					}
				}
			}
		}

		for role in roles:
			aggs[role] = {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': role
							}
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'persons.gender',
									'size': 10000,
									'order': {
										'_key': 'asc'
									}
								},
								'aggs': {
									'person_count': {
										'cardinality': {
											'field': 'persons.id'
										}
									}
								}
							}
						}
					}
				}
			}

		return aggs

	roles = getPersonRoles(request)

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': createAggregations(roles)
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


def getSimilar(request, documentId):
	query = {
		'query': {
			'more_like_this' : {
				'fields' : ['text', 'title'],
				'like' : [
					{
						'_index' : 'sagenkarta_v3',
						'_type' : 'legend',
						'_id' : documentId
					}
				],
				'min_term_freq' : 1,
				'max_query_terms' : 12
			}
		},
		'highlight': {
			'pre_tags': [
				'<span class="highlight">'
			],
			'post_tags': [
				'</span>'
			],
			'fields': {
				'text': {
					'number_of_fragments': 0
				}
			}
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query)
	return esQueryResponse

def getDocuments(request, data_restriction=None):
	""" Get documents with filter
	Get documents of data in json using suitable standard filter parameters.
	Arguments for formatting response data in json
	 -mark_metadata: adds boolean mark_metadata.
	 -sort: Sort principle.
	Returns
		documents: Fromat json.
			  May return None if no hit.
	"""
	# itemFormat som säger till hur varje object i esQuery resultatet skulle formateras
	def itemFormat(item):
		if '_source' in item:
			returnItem = dict(item)
			returnItem['_source'] = {}

			for key in item['_source']:
				if not 'topics' in key:
					#item['_source'].pop(key)
					returnItem['_source'][key] = item['_source'][key]

			return returnItem
		else:
			return item

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return list(map(itemFormat, json['hits']['hits']))

	textField = 'text.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'text'
	titleField = 'title.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'title'
	contentsField = 'contents.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'contents'
	headwordsField = 'headwords.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'headwords'
	query = {
		'query': createQuery(request, data_restriction),
		'size': request.GET['size'] if 'size' in request.GET else 100,
		'from': request.GET['from'] if 'from' in request.GET else 0,
		'highlight' : {
			'pre_tags': [
				'<span class="highlight">'
			],
			'post_tags': [
				'</span>'
			],
			'fields' : [
				{
					textField : {
						# The maximum number of fragments to return. If the number
						# of fragments is set to 0, no fragments are returned. Instead,
						# the entire field contents are highlighted and returned. 
						# https://www.elastic.co/guide/en/elasticsearch/reference/current/highlighting.html
						'number_of_fragments': 0
					} 
				}, 
				{
					titleField : {
						'number_of_fragments': 0
					}
				},
				{
					contentsField : {
						'number_of_fragments': 0
					}
				},
				{
					headwordsField : {
						'number_of_fragments': 0
					}
				}
			]
			
		}
	}

	if('aggregation' in request.GET):
		query['size'] = 0
		aggregation = request.GET['aggregation'].split(',')
		query['aggs'] = {
			'aggresult': {
				aggregation[0]: {
					'field': aggregation[1],
					'size': aggregation[2] if len(aggregation) >= 3 else "50"
				}
			}
		}
	

	if ('mark_metadata' in request.GET):
		query['query']['bool']['should'] = [
			{
				'match': {
					'metadata.type': {
						'query': request.GET['mark_metadata'],
						'boost': 5
					}
				}
			},
			{
				'exists': {
					'field': 'text',
					'boost': 10
				}
			}
		]

	if('id' in request.GET):
		# match the id for the document exactly
		# do not mess up the existing query structure
		# add the id match as a must clause, but keep the existing must clauses if there are any
		# also, make sure that only the document is returned, not a list with one document
		# also, make sure only one document is returned by querying id.keyword (needs mapping id.keyword as type keyword)
		query['query']['bool']['must'] = query['query']['bool']['must'] if 'must' in query['query']['bool'] else []
		query['query']['bool']['must'].append({
			'match': {
				'id.keyword': request.GET['id']
			}
		})


	if ('sort' in request.GET):
		sort = []
		sortObj = {}
		# if sorting by archive_id_row.keyword, sort first by archive_id, then by page number as integer
		if request.GET['sort'] == 'archive.archive_id_row.keyword':
			# sort.append({'archive.archive_id_row.keyword': request.GET['order'] if 'order' in request.GET else 'asc'})
			# sort.append({'archive.page': request.GET['order'] if 'order' in request.GET else 'asc'})
			sortObj[request.GET['sort']] = request.GET['order'] if 'order' in request.GET else 'asc'
			# add secondary sort
			sortObj['archive.page.long'] = request.GET['order'] if 'order' in request.GET else 'asc'
				
		else:
			sortObj[request.GET['sort']] = request.GET['order'] if 'order' in request.GET else 'asc'

		sort.append(sortObj)
		query['sort'] = sort

	# An
	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


def getTexts(request):
	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		retList = []
		analyzedFieldList = ['title', 'text', 'contents', 'headwords']
		rawFieldList = ['title.raw', 'text.raw', 'contents.raw', 'headwords.raw']
		fieldList = rawFieldList if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else analyzedFieldList

		for hit in json['hits']['hits']:
			if 'highlight' in hit:
				for field in fieldList:
					if field in hit['highlight']:
						for highlight in hit['highlight'][field]:
							retList.append({
								'_id': hit['_id'],
								'title': hit['_source']['title'],
								'materialtype': hit['_source']['materialtype'],
								'taxonomy': hit['_source']['taxonomy'],
								'archive': hit['_source']['archive'],
								'year': hit['_source']['year'] if 'year' in hit['_source'] else '',
								'source': hit['_source']['source'],
								'highlight': '<td>'+highlight+'</td>'
							})
		return retList

	textField = 'text.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'text'
	titleField = 'title.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'title'
	contentsField = 'contents.raw' if 'search.raw' in request.GET and request.GET['search_raw'] != 'false' else 'contents'
	headwordsField = 'headwords.raw' if 'search.raw' in request.GET and request.GET['search_raw'] != 'false' else 'headwords'
	query = {
		'query': createQuery(request),
		'size': request.GET['size'] if 'size' in request.GET else 100,
		'from': request.GET['from'] if 'from' in request.GET else 0,
		'highlight' : {
			'pre_tags': [
				'</td><td class="highlight-cell"><span class="highlight">'
			],
			'post_tags': [
				'</span></td><td>'
			],
			'fields' : {
				titleField: {},
				textField : {},
				contentsField: {},
				headwordsField: {}
			}
		}
	}

	if ('sort' in request.GET):
		sort = []
		sortObj = {}
		sortObj[request.GET['sort']] = request.GET['order'] if 'order' in request.GET else 'asc'

		sort.append(sortObj)

		query['sort'] = sort

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat)

	return esQueryResponse


def getTermsGraph(request):
	# Hämtar graphs data för visualisering i terms network graph delen av Digitalt Kulturarv

	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return json

	queryObject = createQuery(request)

	basicQueryObject = {};

	if 'country' in request.GET or 'type' in request.GET:
		basicQueryObject['query_string'] = {
			'query': '*'
		}

		criterias = []

		if 'country' in request.GET:
			criterias.append('archive.country: '+request.GET['country'])

		if 'type' in request.GET:
			criterias.append('(materialtype: '+' OR materialtype: '.join(request.GET['type'].split(','))+')')

		basicQueryObject['query_string']['query'] = ' AND '.join(criterias)

	query = {
		'query': queryObject,
		'controls': {
			'use_significance': True,
			'sample_size': int(request.GET['sample_size']) if 'sample_size' in request.GET else 20000,
			'timeout': 20000
		},
		'vertices': [
			{
				'field': request.GET['terms_field'] if 'terms_field' in request.GET else 'topics_graph',
				'size': int(request.GET['vertices_size']) if 'vertices_size' in request.GET else 160,
				'min_doc_count': 2
			}
		],
		'connections': {
			'query': queryObject if 'query_connections' in request.GET and request.GET['query_connections'] == 'true' else basicQueryObject,
			'vertices': [
				{
					'field': request.GET['terms_field'] if 'terms_field' in request.GET else 'topics_graph',
					'size': 10
				}
			]
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat, '/_xpack/_graph/_explore')
	return esQueryResponse


def getPersonsGraph(request):
	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		return json

	queryObject = createQuery(request)

	query = {
		'query': queryObject,
		'controls': {
			'use_significance': True,
			'sample_size': int(request.GET['sample_size']) if 'sample_size' in request.GET else 200000,
			'timeout': 20000,
			'sample_diversity': {
				'field': 'id',
				'max_docs_per_value': 500
			}
		},
		'vertices': [
			{
				'field': 'persons_graph.name_id.keyword',
				'min_doc_count': int(request.GET['min_doc_count']) if 'min_doc_count' in request.GET else 1
			}
		],
		'connections': {
			'query': queryObject,
			'vertices': [
				{
					'field': 'persons_graph.name_id.keyword',
					'size': 100000,
					'min_doc_count': 1
				}
			]
		}
	}

	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(request, query, jsonFormat, '/_xpack/_graph/_explore')
	return esQueryResponse


# import mappings file from importer_files/mappings.json and create a new index with that mapping and the settings from
# import_files/analysis.json

def createIndex(request):
	# import Elasticsearch
	from elasticsearch import Elasticsearch

	# create es variable
	es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

	# Skapar nytt index med mappings och settings från importer_files mappen

	# Hämtar settings från analysis.json
	with open('importer_files/analysis.json') as analysisFile:
		analysis = json.load(analysisFile)

	# Hämtar mappings från mappings.json
	with open('importer_files/mappings.json') as mappingsFile:
		mappings = json.load(mappingsFile)

	# Skapar index med settings och mappings
	es.indices.create(index='digitalt_kulturarv', body={
		'settings': analysis,
		'mappings': mappings
	})

	return HttpResponse('Index created')

# räkna antal träffar för en sökning
def getCount(requests):
	# jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
	def jsonFormat(json):
		if('aggregation' in requests.GET):
			return json['aggregations']['aggresult']
		else:
			return json['hits']['total']

	query = {
		'query': createQuery(requests),
		'size': 0
	}

	if('aggregation' in requests.GET):
		aggregation = requests.GET['aggregation'].split(',')
		query['aggs'] = {
			'aggresult': {
				aggregation[0]: {
					'field': aggregation[1]
				}
			}
		}


	# Anropar esQuery, skickar query objekt och eventuellt jsonFormat funktion som formaterar resultat datat
	esQueryResponse = esQuery(requests, query, jsonFormat)

	return esQueryResponse

def getTopTranscribersByPagesStatistics(requests):
	"""
    Returns top transcribers by page statistics.
    """
	
	def jsonFormatFunction(json):
		"""
		Formats json to required format.
		"""
		try:
			data = json['aggregations']['aggresult']['buckets']
		except KeyError:
			logger.error("jsonFormatFunction Invalid JSON format.")
			# print("Invalid JSON format.")
			return []
		# Using list comprehension for more pythonic code
		return [{"key": x["key"], "value": x["total_pages"]["value"]} for x in data]

	query = {
		'query': createQuery(requests),
		'size': 0,
		'aggs': {
			"aggresult": {
				"terms": {
					"field": "transcribedby.keyword",
					"size": 10,
					"order": {
						"total_pages": "desc"
					}
				},
				"aggs": {
					"total_pages": {
						"sum": {
							"field": "archive.total_pages"
						}
					}
				}
			}
		},
	}
    
	try:
		esQueryResponse = esQuery(requests, query, jsonFormatFunction)
	except Exception as e:
		# print(f"Error in Elasticsearch query: {e}")
		logger.error(f"getTopTranscribersByPagesStatistics Error in Elasticsearch query: {e}")
		return []

	return esQueryResponse

def getCurrentTime(request):
	# returnerar ES-serverns nuvarande tid
	# returnera bara nuvarande timestamp från result['hits']['hits'][0]['fields']['now'][0]
	return esQuery(request, {
		'size': 1,
		'script_fields': {
			'now': {
				'script': 'new Date().getTime()'
			}
		}
	}, 
		lambda json: json['hits']['hits'][0]['fields']['now'][0]
	)


