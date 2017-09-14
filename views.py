from django.http import JsonResponse
import requests, json, sys
from requests.auth import HTTPBasicAuth

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
		searchTerms = request.GET['search'].split(',')

		for term in searchTerms:
			if (term.startswith('"') and term.endswith('"')):
				matchObj = {
					'bool': {
						'should': [
							{
								'match_phrase': {
									'text': {
										'query': term.replace('"', '')
									}
								}
							}
						]
					}
				}
				if ('search_options' in request.GET):
					if (request.GET['search_options'] == 'nearer'):
						matchObj['bool']['should'][0]['match_phrase']['text']['slop'] = 1
					if (request.GET['search_options'] == 'near'):
						matchObj['bool']['should'][0]['match_phrase']['text']['slop'] = 3

			else:
				matchObj = {
					'bool': {
						'should': [
							{
								'match': {
									'title': term
								}
							},
							{
								'match': {
									'text': {
										'query': term,
										'boost': 2
									}
								}
							}
						]
					}
				}

			query['bool']['must'].append(matchObj)


	if ('phrase' in request.GET):
		query['bool']['must'].append({
			'match_phrase': {
				'text': request.GET['phrase']
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
					'match': {
						'places.name': socken
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
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.name_analysed': request.GET['person']
								}
							}
						]
					}
				}
			}
		}

		if ('person_relation' in request.GET):
			personShouldBool['nested']['query']['bool']['must'].append({
				'match': {
					'persons.relation': request.GET['person_relation']
				}
			})

		query['bool']['must'].append(personShouldBool)


	if ('person_exact' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.name': request.GET['person_exact']
								}
							}
						]
					}
				}
			}
		}

		if ('person_relation' in request.GET):
			personShouldBool['nested']['query']['bool']['must'].append({
				'match': {
					'persons.relation': request.GET['person_relation']
				}
			})

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
									'persons.name': request.GET['collector']
								}
							},
							{
								'match': {
									'persons.relation': 'collector'
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
									'persons.name': request.GET['informant']
								}
							},
							{
								'match': {
									'persons.relation': 'informant'
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
									'persons.relation': 'collector'
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
									'persons.relation': 'informant'
								}
							}
						]
					}
				}
			}
		}

		query['bool']['must'].append(personShouldBool)


	if ('gender' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.gender': request.GET['gender']
								}
							}
						]
					}
				}
			}
		}

		if ('person_relation' in request.GET):
			personShouldBool['nested']['query']['bool']['must'].append({
				'match': {
					'persons.relation': request.GET['person_relation']
				}
			})

		query['bool']['must'].append(personShouldBool)


	if ('birth_years' in request.GET):
		birthYears = request.GET['birth_years'].split(',')

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

		if ('person_relation' in request.GET):
			personShouldBool['nested']['query']['bool']['must'].append({
				'match': {
					'persons.relation': request.GET['person_relation']
				}
			})

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
									'persons.relation': 'collector'
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
									'persons.relation': 'informant'
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
				'path': 'topics',
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
					'path': 'topics.terms',
					'query': {
						'bool': {
							'should': [
								{
									'function_score': {
										'query': {
											'match': {
												'topics.terms.term': topic
											}
										},
										'functions': [
											{
												'field_value_factor': {
													'field': 'topics.terms.probability'
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
				'path': 'title_topics',
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
					'path': 'title_topics.terms',
					'query': {
						'bool': {
							'should': [
								{
									'function_score': {
										'query': {
											'match': {
												'title_topics.terms.term': topic
											}
										},
										'functions': [
											{
												'field_value_factor': {
													'field': 'title_topics.terms.probability'
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
				
				'min_word_length': 4,

				'min_term_freq' : 1,
				'max_query_terms' : 500
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

	return query

def esQuery(request, query, formatFunc = None, apiUrl = None):
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

	if ('showQuery' in request.GET) and request.GET['showQuery']:
		outputData['metadata']['query'] = query

	jsonResponse = JsonResponse(outputData)
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getDocument(request, documentId):
	esResponse = requests.get('https://'+es_config.user+':'+es_config.password+'@'+es_config.host+'/'+es_config.index_name+'/legend/'+documentId, verify=False)

	jsonResponse = JsonResponse(esResponse.json())
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

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
					'path': 'topics'
				},
				'aggs': {
					'data': {
						'nested': {
							'path': 'topics.terms'
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'topics.terms.term',
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
					'path': 'topics'
				},
				'aggs': {
					'data': {
						'nested': {
							'path': 'topics.terms'
						},
						'aggs': {
							'data': {
								'filter': {
									'bool': {
										'must': {
											'regexp': {
												'topics.terms.term': request.GET['search']+'.+'
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
											'field': 'topics.terms.term'
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
					'path': 'title_topics'
				},
				'aggs': {
					'data': {
						'nested': {
							'path': 'title_topics.terms'
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'title_topics.terms.term',
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
											'field': 'title_topics.terms.probability'
										}
									},
									'probability_max': {
										'max': {
											'field': 'title_topics.terms.probability'
										}
									},
									'probability_median': {
										'percentiles': {
											'field': 'title_topics.terms.probability',
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
					'path': 'title_topics'
				},
				'aggs': {
					'data': {
						'nested': {
							'path': 'title_topics.terms'
						},
						'aggs': {
							'data': {
								'filter': {
									'bool': {
										'must': {
											'regexp': {
												'title_topics.terms.term': request.GET['search']+'.+'
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
											'field': 'title_topics.terms.term'
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

def getBirthYears(request):
	def itemFormat(item):
		return {
			'year': item['key_as_string'],
			'timestamp': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

	def jsonFormat(json):
		return {
			'all': list(map(itemFormat, json['aggregations']['data']['data']['buckets'])),
			'collectors': list(map(itemFormat, json['aggregations']['collectors']['data']['data']['buckets'])),
			'informants': list(map(itemFormat, json['aggregations']['informants']['data']['data']['buckets']))
		}

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'collectors': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': 'collector'
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
			},
			'informants': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': 'informant'
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
			},
			'data': {
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
					'size': 10000,
					'order': {
						'_term': 'asc'
					}
				},
				'aggs': {
					'data': {
						'terms': {
							'field': 'taxonomy.name',
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

def getSocken(request):
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

	print(json.dumps(query))

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


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

	print(json.dumps(query))

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

def getPersons(request):
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
		return list(map(itemFormat, json['aggregations']['data']['data']['buckets']))

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
						'terms': {
							'field': 'persons.id',
							'size': request.GET['count'] if 'count' in request.GET else 10000
						},
						'aggs': {
							'data': {
								'terms': {
									'field': 'persons.name',
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


def getPerson(request, personId):
	query = {
		'query': {
			'filter': {
				'term': {
					'persons.id': personId
				}
			}
		}
	}

	print(query)

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
											'persons.name': '(.+?)'+request.GET['search']+'(.+?)'
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
									'field': 'persons.name',
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
											'field': 'persons.name',
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
	return getRelatedPersons(request, 'informant')


def getCollectors(request):
	return getRelatedPersons(request, 'collector')


def getGender(request):
	def itemFormat(item):
		return {
			'gender': item['key'],
			'doc_count': item['doc_count'],
			'person_count': item['person_count']['value']
		}

	def jsonFormat(json):
		return {
			'all': list(map(itemFormat, json['aggregations']['data']['data']['buckets'])),
			'collectors': list(map(itemFormat, json['aggregations']['collectors']['data']['data']['buckets'])),
			'informants': list(map(itemFormat, json['aggregations']['informants']['data']['data']['buckets']))
		}

	query = {
		'query': createQuery(request),
		'size': 0,
		'aggs': {
			'collectors': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': 'collector'
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
			},
			'informants': {
				'nested': {
					'path': 'persons'
				},
				'aggs': {
					'data': {
						'filter': {
							'term': {
								'persons.relation': 'informant'
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
			},
			'data': {
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
					'fragment_size': 1000
				}
			}
		}
	}

	esQueryResponse = esQuery(request, query)
	return esQueryResponse


def getDocuments(request):
	def jsonFormat(json):
		return json['hits']['hits']

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
				'text' : {
					'fragment_size': 1000
				}
			}
		}
	}

	if ('sort' in request.GET):
		sort = []
		sortObj = {}
		sortObj[request.GET['sort']] = request.GET['order'] if 'order' in request.GET else 'asc'

		sort.append(sortObj)

		query['sort'] = sort

	print(json.dumps(query))

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse


def getGraph(request):
	def jsonFormat(json):
		return json

	query = {
		'query': createQuery(request),
		'controls': {
			'use_significance': True,
			'sample_size': 20000,
			'timeout': 20000
		},
		'vertices': [
			{
				'field': 'topics_graph',
				'size': 100,
				'min_doc_count': 2
			}
		],
		'connections': {
			'vertices': [
				{
					'field': 'topics_graph'
				}
			]
		}
	}

	# Flera resultat (men inte sa bra):
	# sample_size 50000
	# size 550
	# min_doc_count 2

	esQueryResponse = esQuery(request, query, jsonFormat, '/_xpack/_graph/_explore')
	return esQueryResponse
