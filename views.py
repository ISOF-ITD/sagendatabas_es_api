from django.http import JsonResponse
import requests, json, sys
from requests.auth import HTTPBasicAuth
from random import randint

import es_config
import geohash

def createQuery(request):
	# Parameters:

	#	sokstrang (title, text, acc. number) X
	#	kategori X
	#	typ X
	#	institut ?
	#	terms X
	#	title_terms X

	#	insamlingsar (fran och till) X
	#	insamlingsort (sockennamn, socken-id, harad, landskap, bounding box, ...)

	#	liknande dokumenter X

	#	person relation X
	#	namn X
	#	fodelsear
	#	kon X
	#	fodelseort

	if (len(request.GET) > 0):
		query = {
			'bool': {
				'must': []
			}
		}
	else:
		query = {}

	if ('collection_years' in request.GET):
		collectionYears = request.GET['collection_years'].split(',')

		query['bool']['must'].append({
			'range': {
				'year': {
					'gte': collectionYears[0],
					'lt': collectionYears[1]
				}
			}
		})

	if ('search' in request.GET):
		term = request.GET['search']
		textField = 'text.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'text'

		matchObj = {
			'multi_match': {
				'query': term.replace('"', ''),
				'type': 'phrase' if (term.startswith('"') and term.endswith('"')) else 'best_fields',
				'fields': [
					textField+'^2'
				],
				'minimum_should_match': '100%'
			}
		}

		# search_exclude_title = true, sök inte i titel fältet
		if (not 'search_exclude_title' in request.GET or request.GET['search_exclude_title'] == 'false') and (not 'search_raw' in request.GET or request.GET['search_raw'] != 'true'):
			matchObj['multi_match']['fields'].append('title')

		if term.startswith('"') and term.endswith('"'):
			if ('phrase_options' in request.GET):
				if (request.GET['phrase_options'] == 'nearer'):
					matchObj['multi_match']['slop'] = 1
				if (request.GET['phrase_options'] == 'near'):
					matchObj['multi_match']['slop'] = 3
			else:
				matchObj['multi_match']['slop'] = 50

		query['bool']['must'].append(matchObj)


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


	if ('has_metadata' in request.GET):
		query['bool']['must'].append({
			'match': {
				'metadata.type': request.GET['has_metadata']
			}
		})


	if ('category' in request.GET):
		categoryShouldBool = {
			'bool': {
				'should': []
			}
		}

		categoryStrings = request.GET['category'].split(',')

		for category in categoryStrings:
			categoryShouldBool['bool']['should'].append({
				'match': {
					'taxonomy.category': category.upper()
				}
			})
			categoryShouldBool['bool']['should'].append({
				'match': {
					'taxonomy.category': category
				}
			})
		query['bool']['must'].append(categoryShouldBool)


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
				'places.name': request.GET['place']+'*'
			}
		})

		placeShouldBool['nested']['query']['bool']['should'].append({
			'wildcard': {
				'places.harad': request.GET['place']+'*'
			}
		})

		placeShouldBool['nested']['query']['bool']['should'].append({
			'wildcard': {
				'places.landskap': request.GET['place']+'*'
			}
		})

		placeShouldBool['nested']['query']['bool']['should'].append({
			'wildcard': {
				'places.county': request.GET['place']+'*'
			}
		})

		query['bool']['must'].append(placeShouldBool)


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
									'match': {
										'persons.name': personNameQuery[1] if len(personNameQuery) > 1 else personNameQuery[0]
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
										'persons.name.raw': personNameQuery[1] if len(personNameQuery) > 1 else personNameQuery[0]
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
								'match': {
									'persons.relation': 'c'
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


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
								'match': {
									'persons.relation': 'i'
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


	if ('collector' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.name.raw': request.GET['collector']
								}
							},
							{
								'match': {
									'persons.relation': 'c'
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


	if ('informant' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.name.raw': request.GET['informant']
								}
							},
							{
								'match': {
									'persons.relation': 'i'
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


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
								'match': {
									'persons.relation': 'c'
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


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
								'match': {
									'persons.relation': 'i'
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


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
										'persons.gender': genderQuery[1]
									}
								},
								{
									'match': {
										'persons.relation': genderQuery[0]
									}
								}
							]
						}
					}
				}
			}

			query['bool']['must'].append(personShouldBool)


	if ('birth_years' in request.GET):
		birthYearsQueries = request.GET['birth_years'].split(',')

		for birthYearsQueryStr in birthYearsQueries:
			birthYearsQuery = birthYearsQueryStr.split(':')

			birthYears = birthYearsQuery[1].split('-')

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
									'match': {
										'persons.relation': birthYearsQuery[0]
									}
								}
							]
						}
					}
				}
			}

			query['bool']['must'].append(personShouldBool)


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
								'match': {
									'persons.relation': 'c'
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


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
								'match': {
									'persons.relation': 'i'
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

	if ('similar' in request.GET):
		query['bool']['must'].append({
			'more_like_this' : {
				'fields' : ['text', 'title'],
				'like' : [
					{
						'_index' : es_config.index_name,
						'_type' : 'legend',
						'_id' : request.GET['similar']
					}
				],

				'min_word_length': int(request.GET['min_word_length']) if 'min_word_length' in request.GET else 4,
				'min_term_freq' : int(request.GET['min_term_freq']) if 'min_term_freq' in request.GET else 1,
				'max_query_terms' : int(request.GET['max_query_terms']) if 'max_query_terms' in request.GET else 25,
				'minimum_should_match' : request.GET['minimum_should_match'] if 'minimum_should_match' in request.GET else '30%'
			}
		})

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

	if ('only_categories' in request.GET and request.GET['only_categories'].lower() == 'true'):
		query['bool']['must'].append({
			'exists': {
				'field': 'taxonomy.category'
			}
		})

	if ('country' in request.GET):
		query['bool']['must'].append({
			'term': {
				'archive.country': request.GET['country'].lower()
			}
		})

	if ('archive' in request.GET):
		query['bool']['must'].append({
			'term': {
				'archive.archive.keyword': request.GET['archive']
			}
		})

	return query

def esQuery(request, query, formatFunc = None, apiUrl = None, returnRaw = False):
	esResponse = requests.get('https://'+es_config.user+':'+es_config.password+'@'+es_config.host+'/'+es_config.index_name+(apiUrl if apiUrl else '/legend/_search'), data=json.dumps(query), verify=False)

	responseData = esResponse.json()

	if (formatFunc):
		outputData = {
			'data': formatFunc(responseData)
		}
	else:
		outputData = responseData

	outputData['metadata'] ={
		'total': responseData['hits']['total'] if 'hits' in responseData else 0,
		'took': responseData['took'] if 'took' in responseData else 0
	}

	if request is not None and ('showQuery' in request.GET) and request.GET['showQuery']:
		outputData['metadata']['query'] = query

	if returnRaw:
		return outputData
	else:
		jsonResponse = JsonResponse(outputData)
		jsonResponse['Access-Control-Allow-Origin'] = '*'

		return jsonResponse

def getDocument(request, documentId):
	esResponse = requests.get('https://'+es_config.user+':'+es_config.password+'@'+es_config.host+'/'+es_config.index_name+'/legend/'+documentId, verify=False)

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

	esQueryResponse = esQuery(request, query)
	return esQueryResponse

def getTerms(request):
	def itemFormat(item):
		return {
			'term': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		}

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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTermsAutocomplete(request):
	def itemFormat(item):
		return {
			'term': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		}

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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTitleTerms(request):
	def itemFormat(item):
		return {
			'term': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		}

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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTitleTermsAutocomplete(request):
	def itemFormat(item):
		return {
			'term': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		}

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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getCollectionYearsTotal(request):
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count']
		}

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
						'_term': 'asc'
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
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count']
		}

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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getBirthYearsTotal(request):
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

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
						'_term': 'asc'
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
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getCategories(request):
	def itemFormat(item):
		retObj = {
			'key': item['key'],
			'doc_count': item['doc_count']
		}

		if len(item['data']['buckets']) > 0:
			retObj['name'] = item['data']['buckets'][0]['key']

		return retObj

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
						}
					}
				}
			}
		}
	}

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTypes(request):
	def itemFormat(item):
		return {
			'type': item['key'],
			'doc_count': item['doc_count']
		}

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
						'_term': 'asc'
					}
				}
			}
		}
	}

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getSockenTotal(request):
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
						'_term': 'asc'
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
											'_term': 'asc'
										}
									}
								},
								'harad': {
									'terms': {
										'field': 'places.harad',
										'size': 1,
										'order': {
											'_term': 'asc'
										}
									}
								},
								'landskap': {
									'terms': {
										'field': 'places.landskap',
										'size': 1,
										'order': {
											'_term': 'asc'
										}
									}
								},
								'lan': {
									'terms': {
										'field': 'places.county',
										'size': 1,
										'order': {
											'_term': 'asc'
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
											'_term': 'asc'
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
			'page_count': item['page_count']['pages']['value']
		}

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
										'_term': 'asc'
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
										'_term': 'asc'
									}
								}
							},
							'landskap': {
								'terms': {
									'field': 'places.landskap',
									'size': 1,
									'order': {
										'_term': 'asc'
									}
								}
							},
							'lan': {
								'terms': {
									'field': 'places.county',
									'size': 1,
									'order': {
										'_term': 'asc'
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
										'_term': 'asc'
									}
								}
							}
						}
					}
				}
			}
		}
	}

	esQueryResponse = esQuery(request, query, jsonFormat, None, True)

	if ('mark_metadata' in request.GET):
		if not 'bool' in query['query']:
			query['query'] = {
				'bool': {
					'must': []
				}
			}
		query['query']['bool']['must'].append({
			'match_phrase': {
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

def getLetters(request, sockenId = None):
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
												'_term': 'asc'
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
																				'_term': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'harad': {
																		'terms': {
																			'field': 'places.harad',
																			'order': {
																				'_term': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'lan': {
																		'terms': {
																			'field': 'places.county',
																			'order': {
																				'_term': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'landskap': {
																		'terms': {
																			'field': 'places.landskap',
																			'order': {
																				'_term': 'asc'
																			},
																			'size': 1
																		}
																	},
																	'lm_id': {
																		'terms': {
																			'field': 'places.lm_id',
																			'order': {
																				'_term': 'asc'
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
												'_term': 'asc'
											},
											'size': 1
										}
									},
									'lan': {
										'terms': {
											'field': 'places.county',
											'order': {
												'_term': 'asc'
											},
											'size': 1
										}
									},
									'landskap': {
										'terms': {
											'field': 'places.landskap',
											'order': {
												'_term': 'asc'
											},
											'size': 1
										}
									},
									'lm_id': {
										'terms': {
											'field': 'places.lm_id',
											'order': {
												'_term': 'asc'
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

	esQueryResponse = esQuery(request, query, jsonFormat, None, True)

	if ('mark_metadata' in request.GET):
		if not 'bool' in query['query']:
			query['query'] = {
				'bool': {
					'must': []
				}
			}
		query['query']['bool']['must'].append({
			'match_phrase': {
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


def getSockenAutocomplete(request):
	def itemFormat(item):
		return {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'harad': item['harad']['buckets'][0]['key'],
			'landskap': item['landskap']['buckets'][0]['key'],
			'lan': item['lan']['buckets'][0]['key'],
			'lm_id': item['lm_id']['buckets'][0]['key'] if len(item['lm_id']['buckets']) > 0 else '',
			'location': geohash.decode(item['location']['buckets'][0]['key']),
			'doc_count': item['data']['buckets'][0]['doc_count']
		}

	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['buckets']))

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
											'places.name': '(.+?)'+request.GET['search']+'(.+?)'
										}
									}
								]
							}
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
												'_term': 'asc'
											}
										}
									},
									'harad': {
										'terms': {
											'field': 'places.harad',
											'size': 1,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'landskap': {
										'terms': {
											'field': 'places.landskap',
											'size': 1,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'lan': {
										'terms': {
											'field': 'places.county',
											'size': 1,
											'order': {
												'_term': 'asc'
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
												'_term': 'asc'
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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


def getHarad(request):
	def itemFormat(item):
		return {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'landskap': item['landskap']['buckets'][0]['key'],
			'lan': item['lan']['buckets'][0]['key'],
			'doc_count': item['data']['buckets'][0]['doc_count']
		}

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
										'_term': 'asc'
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
										'_term': 'asc'
									}
								}
							},
							'lan': {
								'terms': {
									'field': 'places.county',
									'size': 10000,
									'order': {
										'_term': 'asc'
									}
								}
							}
						}
					}
				}
			}
		}
	}

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getLandskap(request):
	def itemFormat(item):
		return {
			'name': item['key'],
			'doc_count': item['doc_count']
		}

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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getCounty(request):
	def itemFormat(item):
		return {
			'name': item['key'],
			'doc_count': item['doc_count']
		}

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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getPersons(request, personId = None):
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
									'field': 'persons.name.raw',
									'size': 1,
									'order': {
										'_term': 'asc'
									}
								}
							},
							'birth_year': {
								'terms': {
									'field': 'persons.birth_year',
									'size': 1,
									'order': {
										'_term': 'asc'
									}
								}
							},
							'relation': {
								'terms': {
									'field': 'persons.relation',
									'size': 1,
									'order': {
										'_term': 'asc'
									}
								}
							},
							'home': {
								'terms': {
									'field': 'persons.home.id',
									'size': 10,
									'order': {
										'_term': 'asc'
									}
								},
								'aggs': {
									'data': {
										'terms': {
											'field': 'persons.home.name',
											'size': 10,
											'order': {
												'_term': 'asc'
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

	esQueryResponse = esQuery(request, query)
	return esQueryResponse

def getPersonsAutocomplete(request):
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

	def jsonFormat(json):
		return list(map(itemFormat, json['aggregations']['data']['data']['data']['buckets']))

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
											'persons.name.raw': '(.+?)'+request.GET['search']+'(.+?)'
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
											'field': 'persons.name.raw',
											'size': 1,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'birth_year': {
										'terms': {
											'field': 'persons.birth_year',
											'size': 1,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'relation': {
										'terms': {
											'field': 'persons.relation',
											'size': 1,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'home': {
										'terms': {
											'field': 'persons.home.id',
											'size': 10,
											'order': {
												'_term': 'asc'
											}
										},
										'aggs': {
											'data': {
												'terms': {
													'field': 'persons.home.name',
													'size': 10,
													'order': {
														'_term': 'asc'
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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


def getRelatedPersons(request, relation):
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
											'field': 'persons.name.raw',
											'size': 1,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'birth_year': {
										'terms': {
											'field': 'persons.birth_year',
											'size': 1,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'relation': {
										'terms': {
											'field': 'persons.relation',
											'size': 1,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'home': {
										'terms': {
											'field': 'persons.home.id',
											'size': 10,
											'order': {
												'_term': 'asc'
											}
										},
										'aggs': {
											'data': {
												'terms': {
													'field': 'persons.home.name',
													'size': 10,
													'order': {
														'_term': 'asc'
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

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


def getInformants(request):
	return getRelatedPersons(request, 'i')


def getCollectors(request):
	return getRelatedPersons(request, 'c')

def getPersonRoles(request):
	def itemFormat(item):
		return item['key']

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
	def itemFormat(item):
		return {
			'gender': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

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
						'_term': 'asc'
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
								'_term': 'asc'
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
										'_term': 'asc'
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
	def itemFormat(item):
		return {
			'gender': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

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
								'_term': 'asc'
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
										'_term': 'asc'
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

	esQueryResponse = esQuery(request, query)
	return esQueryResponse


def getDocuments(request):
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

	def jsonFormat(json):
		return list(map(itemFormat, json['hits']['hits']))

	textField = 'text.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'text'
	query = {
		'query': createQuery(request),
		'size': request.GET['size'] if 'size' in request.GET else 100,
		'from': request.GET['from'] if 'from' in request.GET else 0,
		'highlight' : {
			'pre_tags': [
				'<span class="highlight">'
			],
			'post_tags': [
				'</span>'
			],
			'fields' : {
				textField : {
					'number_of_fragments': 0
				}
			}
		}
	}

	if ('mark_metadata' in request.GET):
		query['query']['bool']['should'] = [
			{
				'match': {
					'metadata.type': {
						'query': request.GET['mark_metadata'],
						'boost': 10
					}
				}
			}
		]

	if ('sort' in request.GET):
		sort = []
		sortObj = {}
		sortObj[request.GET['sort']] = request.GET['order'] if 'order' in request.GET else 'asc'

		sort.append(sortObj)

		query['sort'] = sort

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


def getTexts(request):
	def jsonFormat(json):
		retList = []

		for hit in json['hits']['hits']:
			if 'title' in hit['highlight']:
				for highlight in hit['highlight']['title']:
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
			if 'text' in hit['highlight']:
				for highlight in hit['highlight']['text']:
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
			if 'text.raw' in hit['highlight']:
				for highlight in hit['highlight']['text.raw']:
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
				'title': {},
				textField : {}
			}
		}
	}

	if ('sort' in request.GET):
		sort = []
		sortObj = {}
		sortObj[request.GET['sort']] = request.GET['order'] if 'order' in request.GET else 'asc'

		sort.append(sortObj)

		query['sort'] = sort

	esQueryResponse = esQuery(request, query, jsonFormat)

	return esQueryResponse


def getTermsGraph(request):
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

	esQueryResponse = esQuery(request, query, jsonFormat, '/_xpack/_graph/_explore')
	return esQueryResponse


def getPersonsGraph(request):
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

	esQueryResponse = esQuery(request, query, jsonFormat, '/_xpack/_graph/_explore')
	return esQueryResponse
