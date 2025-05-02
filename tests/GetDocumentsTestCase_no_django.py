import unittest
from datetime import datetime

import requests
import json

import logging
logger = logging.getLogger(__name__)

class GetDocumentsTestCase(unittest.TestCase):
    """
    API test cases for updating data in the database.
    This test case is independent of Django and can be executed in the shell.

    See also kibana queries:
    https://git.its.uu.se/isof-devs/databaskod/src/master/elasticsearch/kartplattformen/test/*.txt

    Run in shell:
    Run in shell:
    1. Kör API-server
        cd /home/per/dev/server/folkeservice/sagendatabas_es_api/
        source ../current_venv/bin/activate
        folkeservice runserver
    2. Start test
    python3 tests/GetDocumentsTestCase_no_django.py 2> GetDocumentsTestCase_no_django1.html
    python3 tests/GetDocumentsTestCase_no_django.py > GetDocumentsTestCase_no_django_$(date +"%Y-%m-%d:%H%M")-log.txt 2> GetDocumentsTestCase_no_django_$(date +"%Y-%m-%d:%H%M")-results.txt
    4. Validate tests
    Check output files: *-result.txt and if error *-log.txt
    Example *-result.txt:
        Ran 2 tests in 5.034s
        OK
    Check data in for example folke:
        https://sok.folke-test.isof.se/search/rompedrag?s=rompedrag
        https://garm-test.isof.se/folkeservice/api/es/document/bd00614:b_231626_a/
        https://garm-test.isof.se/folkeservice/api/es/document/bd00615_52211_a
    """

    base_url = "http://localhost:8000/api/es/"
    search_text_audio_and_text = "search=rompedrag"
    use_slash = "/"
    #use_slash = ""

    """
    count requests all, audio, image:
    https://garm-test.isof.se/folkeservice/api/es/count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&search=rompedrag&transcriptionstatus=published,accession    
    https://garm-test.isof.se/folkeservice/api/es/count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&search=rompedrag&category=contentG5&transcriptionstatus=published,accession
    https://garm-test.isof.se/folkeservice/api/es/count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&search=rompedrag&category=contentG2&transcriptionstatus=published,accession
    """
    socken = "socken/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&transcriptionstatus=published,accession"
    documents = "documents/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&size=100&transcriptionstatus=published,accession&sort=archive.archive_id_row.keyword&order=asc"
    # No setup needed yet
    # @classmethod
    # def setUpClass(cls):

    @classmethod
    def log_response(cls, response, prefix):
        if response is None:
            print(prefix + " " + str(response))
        else:
            print(prefix + " " + str(response.status_code))
            print(prefix + " " + str(response.headers))
            print(prefix + " " + str(response.content))
            # print(prefix + " " + str(response.json()))
            # print(prefix + " " + str(response.text))

    # No tear down needed yet
    # @classmethod
    # def tearDownClass(cls):

    def test_10_socken_search_text(self):
        logid = "test_10_socken_search_text"
        url = f"{self.base_url}" + self.socken + '&' + self.search_text_audio_and_text
        print(logid + ' ' + str(url))
        # print(logid + ' ' + str(files))
        response = requests.get(url)
        self.log_response(response, logid)
        self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
        # self.assertIn("success", response.json(), f"Unexpected response: {response.json()}")


    def test_20_documents_search_text(self):
        logid = "test_20_documents_search_text"
        url = f"{self.base_url}" + self.documents + '&' + self.search_text_audio_and_text
        print(logid + ' ' + str(url))
        # print(logid + ' ' + str(files))
        response = requests.get(url)
        self.log_response(response, logid)
        self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
        # self.assertIn("success", response.json(), f"Unexpected response: {response.json()}")


if __name__ == "__main__":
    unittest.main()