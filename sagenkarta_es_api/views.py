from django.http import JsonResponse
import requests, json, sys
from requests.auth import HTTPBasicAuth

def createQuery(request):
	# Parameters:

	#	sokstrang (title, text, acc. number) X
	#	kategori X
	#	typ X
	#	institut ?
	#	topic X
	#	title_topic X

	#	insamlingsar (fran och till) X
	#	insamlingsort (sockennamn, socken-id, harad, landskap, bounding box, ...)

	#	liknande dokumenter X

	#	person relation X
	#	namn X
	#	fodelsear
	#	kon X
	#	fodelseort

	# mogulegt að leita eftir 'svart' en ekki 'svarta'
	# exact leit 'den svarta hunden' : phrase leit

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
			query['bool']['must'].append({
				'bool': {
					'should': [
						{
							'match': {
								'title': term
							}
						},
						{
							'match': {
								'text': term
							}
						}
					]
				}
			})


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


	if ('person' in request.GET):
		personShouldBool = {
			'nested': {
				'path': 'persons',
				'query': {
					'bool': {
						'must': [
							{
								'match': {
									'persons.name_analyzed': request.GET['person']
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


	if ('topics' in request.GET):
		topicsShouldBool = {
			'nested': {
				'path': 'topics',
				'query': {
					'bool': {
						'must': []
					}
				}
			}
		}

		topicStrings = request.GET['topics'].split(',')

		for topic in topicStrings:
			topicsShouldBool['nested']['query']['bool']['must'].append({
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

		query['bool']['must'].append(topicsShouldBool)

	if ('title_topics' in request.GET):
		titleTopicsShouldBool = {
			'nested': {
				'path': 'title_topics',
				'query': {
					'bool': {
						'must': []
					}
				}
			}
		}

		titleTopicStrings = request.GET['title_topics'].split(',')

		for topic in titleTopicStrings:
			titleTopicsShouldBool['nested']['query']['bool']['must'].append({
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

		query['bool']['must'].append(titleTopicsShouldBool)

	if ('similar' in request.GET):
		query['bool']['must'].append({
			'more_like_this' : {
				'fields' : ['text', 'title'],
				'like' : [
					{
						'_index' : 'sagenkarta_v3',
						'_type' : 'legend',
						'_id' : request.GET['similar']
					}
				],
				'min_term_freq' : 1,
				'max_query_terms' : 500
			}
		})
	return query

def esQuery(request, query, formatFunc = None):
	esResponse = requests.get('http://localhost:9200/sagenkarta_v3/legend/_search', data=json.dumps(query), auth=HTTPBasicAuth('elastic', 'changeme'))
	
	responseData = esResponse.json()

	if (formatFunc):
		outputData = {
			'data': formatFunc(responseData)
		}
	else:
		outputData = responseData

	outputData['metadata'] ={
		'total': responseData['hits']['total'],
		'took': responseData['took']
	}

	if ('showQuery' in request.GET) and request.GET['showQuery']:
		outputData['metadata']['query'] = query

	jsonResponse = JsonResponse(outputData)
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getDocument(request, documentId):
	esResponse = requests.get('http://localhost:9200/sagenkarta_v3/legend/'+documentId, auth=HTTPBasicAuth('elastic', 'changeme'))

	jsonResponse = JsonResponse(esResponse.json())
	jsonResponse['Access-Control-Allow-Origin'] = '*'

	return jsonResponse

def getTopics(request):
	def itemFormat(item):
		return {
			'topic': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		};

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

	print(query)

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse

def getTopicsAutocomplete(request):
	def itemFormat(item):
		return {
			'topic': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		};

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

def getTitleTopics(request):
	def itemFormat(item):
		return {
			'topic': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		};

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

def getTitleTopicsAutocomplete(request):
	def itemFormat(item):
		return {
			'topic': item['key'],
			'doc_count': item['parent_doc_count']['doc_count'],
			'terms': item['doc_count']
		};

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
		};

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
		};

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
		};

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
			'doc_count': item['data']['buckets'][0]['doc_count']
		};

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
									'size': 10000,
									'order': {
										'_term': 'asc'
									}
								}
							},
							'harad': {
								'terms': {
									'field': 'places.harad',
									'size': 10000,
									'order': {
										'_term': 'asc'
									}
								}
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

def getHarad(request):
	def itemFormat(item):
		return {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'landskap': item['landskap']['buckets'][0]['key'],
			'lan': item['lan']['buckets'][0]['key'],
			'doc_count': item['data']['buckets'][0]['doc_count']
		};

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
		};

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
		};

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
									'size': request.GET['count'] if 'count' in request.GET else 10000,
									'order': {
										'_term': 'asc'
									}
								}
							},
							'relation': {
								'terms': {
									'field': 'persons.relation',
									'size': request.GET['count'] if 'count' in request.GET else 10000,
									'order': {
										'_term': 'asc'
									}
								}
							},
							'home': {
								'terms': {
									'field': 'persons.home.id',
									'size': request.GET['count'] if 'count' in request.GET else 10000,
									'order': {
										'_term': 'asc'
									}
								},
								'aggs': {
									'data': {
										'terms': {
											'field': 'persons.home.name',
											'size': request.GET['count'] if 'count' in request.GET else 10000,
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


def getRelatedPersons(request, relation):
	def itemFormat(item):
		retObj = {
			'id': item['key'],
			'name': item['data']['buckets'][0]['key'],
			'doc_count': item['doc_count'],
			'relation': item['relation']['buckets'][0]['key']
		}

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
											'size': 10000,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'relation': {
										'terms': {
											'field': 'persons.relation',
											'size': 10000,
											'order': {
												'_term': 'asc'
											}
										}
									},
									'home': {
										'terms': {
											'field': 'persons.home.id',
											'size': 10000,
											'order': {
												'_term': 'asc'
											}
										},
										'aggs': {
											'data': {
												'terms': {
													'field': 'persons.home.name',
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
		};

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
		'size': 100,
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

	print(query)

	esQueryResponse = esQuery(request, query, jsonFormat)
	return esQueryResponse
