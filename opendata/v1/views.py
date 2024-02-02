from rest_framework.views import APIView
from rest_framework.response import Response

from sagendatabas_es_api.views import getDocuments, createQuery, esQuery

# urllib3.disable_warnings()
def documents(request):
    """ Get documents with filter so always opendata is returned

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
                    # item['_source'].pop(key)
                    returnItem['_source'][key] = item['_source'][key]

            return returnItem
        else:
            return item

    # jsonFormat, säger till hur esQuery resultatet skulle formateras och vilkan del skulle användas (hits eller aggregation buckets)
    def jsonFormat(json):
        return list(map(itemFormat, json['hits']['hits']))

    textField = 'text.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'text'
    titleField = 'title.raw' if 'search_raw' in request.GET and request.GET['search_raw'] != 'false' else 'title'
    contentsField = 'contents.raw' if 'search_raw' in request.GET and request.GET[
        'search_raw'] != 'false' else 'contents'
    headwordsField = 'headwords.raw' if 'search_raw' in request.GET and request.GET[
        'search_raw'] != 'false' else 'headwords'
    query = {
        'query': createQuery(request, data_restriction='opendata'),
        'size': request.GET['size'] if 'size' in request.GET else 100,
        'from': request.GET['from'] if 'from' in request.GET else 0,
        'highlight': {
            'pre_tags': [
                '<span class="highlight">'
            ],
            'post_tags': [
                '</span>'
            ],
            'fields': [
                {
                    textField: {
                        # The maximum number of fragments to return. If the number
                        # of fragments is set to 0, no fragments are returned. Instead,
                        # the entire field contents are highlighted and returned.
                        # https://www.elastic.co/guide/en/elasticsearch/reference/current/highlighting.html
                        'number_of_fragments': 0
                    }
                },
                {
                    titleField: {
                        'number_of_fragments': 0
                    }
                },
                {
                    contentsField: {
                        'number_of_fragments': 0
                    }
                },
                {
                    headwordsField: {
                        'number_of_fragments': 0
                    }
                }
            ]

        }
    }

    if ('aggregation' in request.GET):
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

    if ('id' in request.GET):
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

"""
Test DRF API without serializer:
https://stackoverflow.com/questions/53001034/django-rest-framework-send-data-to-view-without-serializer

"""
class Documents(APIView):
    def get(self, request):
        return Response(documents(request))
