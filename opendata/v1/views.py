import coreapi
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.filters import BaseFilterBackend

# Swagger API UI
from django.urls import path, include
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.schemas import SchemaGenerator
from rest_framework.views import APIView
from rest_framework_swagger import renderers

from sagendatabas_es_api.views import createQuery, esQuery, getDocuments

import logging
logger = logging.getLogger(__name__)

# urllib3.disable_warnings()

"""
Test call query with code copied from def documents

NOT needed anymore?
"""
def NOT_USED_documents_to_query(request):
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
Call documents directly with data_restriction as opendata
"""
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
    return getDocuments(request, data_restriction='opendata')


class DocumentsParameters(BaseFilterBackend):
    """
    Parameters for Documents filters
    """
    def get_schema_fields(self, view):
        pass
        return [coreapi.Field(
            name='type',
            location='query',
            required=False,
            type='string',
            description=r'Main type of material.'
                        r' Possible values: '
                        r' arkiv: Material stored in the archive.'
                        r' tryckt: Published material registered in the archive.'
                        ' No error is triggered if the parameter has an unknown value.',
            ),
        coreapi.Field(
            name='recordtype',
            location='query',
            required=False,
            type='string',
            description='Type of record. '
                        ' Possible values: '
                        '   one_accession_row: Container for data when registered. Usually information gathered at one time in one place.'
                        '   one_record: One "story". One record is always part of one accession row.'
                        ' No error is triggered if the parameter has an unknown value.',
        ),
        coreapi.Field(
            name='category',
            location='query',
            required=False,
            type='string',
            description='Category of record. '
                        ' No error is triggered if the parameter has an unknown value.',
        ),
        coreapi.Field(
            name='has_transcribed_records',
            location='query',
            required=False,
            type='boolean',
            description='Get only records with transcriptions. '
                        ' No error is triggered if the parameter has an unknown value.',
        ),
        coreapi.Field(
            name='has_untranscribed_records',
            location='query',
            required=False,
            type='boolean',
            description='Get only records assigned for transcription. '
                        ' No error is triggered if the parameter has an unknown value.',
        ),
        coreapi.Field(
            name='socken_id',
            location='query',
            required=False,
            type='integer',
            description=r'Ids of socken, one or many. Valid socken ids are found in endpoint XX'
                        ' No error is triggered if the parameter has an unknown value.',
        ),
        coreapi.Field(
            name='place',
            location='query',
            required=False,
            type='integer',
            description=r'Names of places (socken), one or many. Valid place names (socken (härad, landskap or län?)) are found in endpoint XX.'
                        r' Example: place=Bolle '
                        ' No error is triggered if the parameter has an unknown value.',
        ),
        coreapi.Field(
            name='country',
            location='query',
            required=False,
            type='string',
            description=r'Country of the archive organisation. This is not the country where data is collected.'
                        r' Possible values: '
                        r' sweden: Institutet för språk och folkminnen'
                        ' No error is triggered if the parameter has an unknown value.',
        )]

class FormatParameters(BaseFilterBackend):
    """
    Parameters for format of response
    """
    def get_schema_fields(self, view):
        return [coreapi.Field(
            name='size',
            location='query',
            required=False,
            type='integer',
            description=r'Number of documents to return. Default is 100?'
                        ' No error is triggered if the parameter has an unknown value.',
        ),
        coreapi.Field(
            name='offset',
            location='query',
            required=False,
            type='integer',
            description='Offset for starting document to return. '
                        ' No error is triggered if the parameter has an unknown value.',
        ),
        coreapi.Field(
            name='order',
            location='query',
            required=False,
            type='string',
            description='Specifies how records should be sorted. '
                        ' Possible values: '
                        '   asc (default value). '
                        '   desc?',
                        #' No error is triggered if the parameter has an unknown value.',
        )]

"""
Test DRF API without serializer:
https://stackoverflow.com/questions/53001034/django-rest-framework-send-data-to-view-without-serializer

"""
class Documents(APIView):
    filter_backends = (DocumentsParameters,FormatParameters,)
    name = 'documents'

    def get(self, request):
        """
            Get documents. Documents contain the recorded information and registered metadata.

            ---
            parameters:
            -
        """
        return documents(request)
        # Object with type JSONResponse in not json ...:
        # return Response(documents(request))

class Swagger(APIView):
    """ Provides a Swagger interface in web browsers. """

    name = 'Swagger'
    permission_classes = [AllowAny]
    renderer_classes = [
        renderers.OpenAPIRenderer,
        renderers.SwaggerUIRenderer
    ]

    def get(self, request):
        base_url = '/folkeservice/opendata'
        # Local deploy:
        # base_url = '/opendata'
        url_patterns = (
                        # Seems it must be iterable so add comma if only one url
                        # url(r'^v1/', include('sagendatabas_es_api.opendata.v1.urls', namespace='folke-opendata-v1')),
                        path('/', include('sagendatabas_es_api.opendata.v1.urls', namespace='folke-opendata-v1')),
                        )
        generator = SchemaGenerator(title='Folke opendata REST-API', description="The response data is returned in the json format. License CC-BY 3.0? Description of response data is found here..", version=1.0, url=base_url, patterns=url_patterns)
        schema = generator.get_schema(request=request)
        logger.debug("Swagger.get: " + str(schema))

        return Response(schema)

