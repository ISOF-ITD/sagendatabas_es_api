# Sagendatabas-ES-Django

Enkelt Django application som visar hur man kan göra enkel API som hämtar data från Elasticserach utan att definera models.
Django samt requests modulen måste vara installerad för att köra applicationen.
Applicationen startas via `python manage.py runserver`.

Koden för API:et finns i `sagenkarta_api/urls.py` och `sagenkarta_api/views.py`

## Endpoints

* documents/?[params]
* terms/?[params]
* title_terms/?[params]
* collection_years/?[params]
* birth_years/?[params]
* categories/?[params]
* category_types/?[params]
* types/?[params]
* socken/?[params]
* get_socken/?[id]
* harad/?[params]
* landskap/?[params]
* persons/?[params]
* informants/?[params]
* collectors/?[params]
* gender/?[params]
* document/?[id]
* random_document/
* similar/?[id]
* graph/?[params]

### Autocomplete anrop
* autocomplete/terms/?search=[söksträng]
* autocomplete/title_terms/?search=[söksträng]
* autocomplete/persons/?search=[söksträng]
* autocomplete/socken/?search=[söksträng]

### Total by type

* total_by_type/socken
* total_by_type/collection_years
* total_by_type/birth_years
* total_by_type/gender

## sagenkarta_es_api

### createQuery
`def createQuery(request)`

Tar inn request object från Django och bygger upp Elasticsearch query baserad på querysträng från URL:et. Levererar Elasticsearch query som dictionary.

Giltiga params:
- **collection_years=[från,till]**
Hämtar documenter var `year` är mellan från och till. Exempel: `collection_year=1900,1910`

- **search=[söksträng]**
Hämtar documenter var ett eller flera eller alla ord förekommer i titel eller text. Exempel: (ett eller flera ord) `search=svart hund`, (alla ord) `search=svart,hund`, (fras sökning, endast i `text` fältet `search="svart hund"`

- **phrase=[söksträng]**
Hämtar documenter var fras förekommer i text. Exempel: `phrase=svart hund`

- **has_metadata=[metadata typ]**
Hämtar documenter som har speciell typ av metadata. Exempel: `has_metadata=sitevision_url` (hämtar kurerade postar för matkartan).

- **mark_metadata=[metadata typ]**
Markerar socknar som är kopplade till textar som har speciell typ av metadata. Funkar bara för socken/.

- **category=[kategori bokstav]**
Hämtar documenter som finns i angiven kategori (en eller flera). Exempel: `category=L,H`

- **type=[type]**
Hämtar documenter av angiven typ (en eller flera). Exempel: `type=arkiv,tryckt`

- **documents=[type]**
Hämtar documenter som har speciella ID.

- **soken_id=[id]**
Hämtar documenter samlat in i angiven socken (en eller flera). Exempel: (sägner från Göteborgs stad och Partille) `socken_id=202,243`

- **socken=[socken namn]**
Hämtar documenter samlat in i angiven socken, men här letar vi efter namn (wildcard sökning). Exempel: `socken=Fritsla`

- **landskap=[landskap namn]**
Hämtar documenter samlat in i angiven landskap. Exempel: `landskap=Värmland`

- **place=[socken namn]**
Hämtar documenter samlat in i angiven socken, härad, landskap eller län, sök via namn (wildcard sökning). Exempel: `place=Bolle`
- **person=[person namn]**

Hämtar documenter var uppteckare eller informant matchar angivet namn. Exempel: (alla som heter Ragnar eller Nilsson) `person=Ragnar Nilsson`

- **person_exact=[person namn]**
Hämtar documenter var uppteckare eller informant matchar angivet helt namn. Exempel: (leter bara efter "Ragnar Nilsson") `person=Ragnar Nilsson`

- **person_id=[person id]**
Hämtar documenter var uppteckare eller informant matchar angivet id.
- **person_relation=[informant,collector]**

Säger till om `person` eller `person_exact` letar efter uppteckare eller informantar. Exempel: `person_relation=informant`

- **collector=[person namn]**
Hämtar documenter var uppteckare matchar angivet namn. Exempel: (alla som heter Ragnar eller Nilsson) `collector=Ragnar Nilsson`

- **informant=[person namn]**
Hämtar documenter var informant matchar angivet namn. Exempel: (alla som heter Ragnar eller Nilsson) `informant=Ragnar Nilsson`

- **collectors_gender=[female|male|unknown]**
Hämtar documenter med uppteckare som är kvinnor, män eller okänt. Exempel: `collectors_gender=female`

- **informants_gender=[female|male|unknown]**
Hämtar documenter med informantar som är kvinnor, män eller okänt. Exempel: `informants_gender=female`

- **gender=[female|male|unknown]**
Hämtar documenter med informantar eller uppteckare som är kvinnor, män eller okänt. Exempel: `gender=female`

- **birth_years=[från,till]**
Hämtar documenter med informantar eller uppteckare föddes i en viss period. Exempel: `birth_years=1870,1890`

- **collectors_birth_years=[från,till]**
Hämtar documenter med uppteckare föddes i en viss period. Exempel: `collectors_birth_years=1870,1890`

- **informants_birth_years=[från,till]**
Hämtar documenter med informantar föddes i en viss period. Exempel: `informants_birth_years=1870,1890`

- **topics=[topics]**
Hämtar documenter som innehåller specifika topic terms (en eller flera). Exempel: `topics=natt,jul`

- **title_topics=[topics]**
Hämtar documenter med titlar som innehåller specifika topic terms (en eller flera). Exempel: `title_topics=gast`

- **similar=[dokument id]**
Hämtar documenter som liknar ett annat dokument (more_like_this). Exempel: `similar=1`

- **geo_box=[top_left_lat,top_left_lon,bottom_right_lat,bottom_right_lon]**
Hämtar documenter samlat in på ett specific rectangular område. Exempel: `geo_box=59.6875,12.6576,58.33,17.14`

### esQuery
`def esQuery(request, query)`

Tar inn request object från Django och Elasticsearch dickionary och leverar respons från Elasticserach.

Exempel:
```python
# Endpoint /urls/?[params]
# url(r'^types/', views.getTypes, name='getTypes')
# Aggregate types (arkiv, tryckt, register, inspelning, ...)

def getTypes(request):
	# Elasticsearch aggregation query
	# createQuery bygger upp själva query dictionary baserad på URL paramsträng
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

	# Hämtar respons från Elasticsearch
	esQueryResponse = esQuery(request, query)
	
	# Leverar ES respons som JSON
	return esQueryResponse
  ```
