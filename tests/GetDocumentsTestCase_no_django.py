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

    # base_url = "http://localhost:8000/api/es/"
    base_url = "https://garm-test.isof.se/folkeservice/api/es/"
    # 3 hits in text, 1 in audio:
    search_text_with_hits_in_audio_and_text = "search=rompedrag"
    use_slash = "/"
    #use_slash = ""

    """
    count requests all, audio, image:
    https://garm-test.isof.se/folkeservice/api/es/count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&search=rompedrag&transcriptionstatus=published,accession    
    https://garm-test.isof.se/folkeservice/api/es/count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&search=rompedrag&category=contentG5&transcriptionstatus=published,accession
    https://garm-test.isof.se/folkeservice/api/es/count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&search=rompedrag&category=contentG2&transcriptionstatus=published,accession
    
    socken:
    https://garm-test.isof.se/folkeservice/api/es/socken/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false
    
    documents:
    http://localhost:8000/api/es/documents/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&size=100&search=kommuniststaterna&transcriptionstatus=published,accession,readytocontribute&sort=archive.archive_id_row.keyword&order=asc
    https://garm-test.isof.se/folkeservice/api/es/documents/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&size=100&search=kommuniststaterna&transcriptionstatus=published,accession,readytocontribute&sort=archive.archive_id_row.keyword&order=asc
    """
    #transcriptionstatus = "published,accession"
    transcriptionstatus = "transcriptionstatus=published,accession,readytocontribute"
    socken = "socken/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false"
    documents = "documents/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&size=100&sort=archive.archive_id_row.keyword&order=asc"
    count_all = "count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false"
    count_all_mininum = 4
    # contentG5 = ljud
    count_audio = "count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&category=contentG5"
    count_audio_mininum = 1
    # contentG2 = bild
    count_image = "count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&category=contentG2"
    count_image_mininum = 0

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

    def test_01_documents_search_count(self):
        logid = "test_01_documents_search_count"
        url = f"{self.base_url}" + self.count_all + '&' + self.transcriptionstatus + '&' + self.search_text_with_hits_in_audio_and_text
        print(logid + ' ' + str(url))
        # print(logid + ' ' + str(files))
        response = requests.get(url)
        self.log_response(response, logid)
        self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
        # self.assertIn("success", response.json(), f"Unexpected response: {response.json()}")
        self.assertGreaterEqual(response.json().get("data", {}).get("value", 0), self.count_all_mininum, f"Unexpected value: {response.json()}")

        url = f"{self.base_url}" + self.count_audio + '&' + self.transcriptionstatus + '&' + self.search_text_with_hits_in_audio_and_text
        print(logid + ' ' + str(url))
        # print(logid + ' ' + str(files))
        response = requests.get(url)
        self.log_response(response, logid)
        self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
        # self.assertIn("success", response.json(), f"Unexpected response: {response.json()}")
        self.assertGreaterEqual(response.json().get("data", {}).get("value", 0), self.count_audio_mininum, f"Unexpected value: {response.json()}")

        url = f"{self.base_url}" + self.count_image + '&' + self.transcriptionstatus + '&' + self.search_text_with_hits_in_audio_and_text
        print(logid + ' ' + str(url))
        # print(logid + ' ' + str(files))
        response = requests.get(url)
        self.log_response(response, logid)
        self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
        # self.assertIn("success", response.json(), f"Unexpected response: {response.json()}")
        self.assertGreaterEqual(response.json().get("data", {}).get("value", 0), self.count_image_mininum, f"Unexpected value: {response.json()}")

    def test_10_socken_search_text(self):
        logid = "test_10_socken_search_text"
        url = f"{self.base_url}" + self.socken + '&' + self.transcriptionstatus + '&' + self.search_text_with_hits_in_audio_and_text
        print(logid + ' ' + str(url))
        # print(logid + ' ' + str(files))
        response = requests.get(url)
        self.log_response(response, logid)
        self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
        # self.assertIn("success", response.json(), f"Unexpected response: {response.json()}")

    def test_20_documents_search_text(self):
        logid = "test_20_documents_search_text"
        url = f"{self.base_url}" + self.documents + '&' + self.transcriptionstatus + '&' + self.search_text_with_hits_in_audio_and_text
        print(logid + ' ' + str(url))
        # print(logid + ' ' + str(files))
        response = requests.get(url)
        self.log_response(response, logid)
        self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
        # self.assertIn("success", response.json(), f"Unexpected response: {response.json()}")

        data = response.json().get("data", [])

        for index, item in enumerate(data):
            condition_met = False

            # Condition 1: Check inner_hits.media_with_description.media.description._source.text
            inner_hits = item.get("inner_hits", {})
            media_desc_hits = (
                inner_hits.get("media_with_description", {})
                .get("hits", {})
                .get("hits", [])
            )

            for media_hit in media_desc_hits:
                desc_hits = (
                    media_hit.get("inner_hits", {})
                    .get("media.description", {})
                    .get("hits", {})
                    .get("hits", [])
                )

                for desc in desc_hits:
                    desc_text = desc.get("_source", {}).get("text", "")
                    if "rompedrag" in desc_text.lower():
                        condition_met = True
                        break
                if condition_met:
                    break

            # Condition 2: Check highlight.text contains "rompedrag"
            if not condition_met:
                highlights = item.get("highlight", {}).get("text", [])
                # Remove newlines:
                if any("rompedrag" in h.lower().replace('-\n','') for h in highlights):
                    condition_met = True

            # Assert that the current item meets at least one condition
            self.assertTrue(
                condition_met,
                f"Item at index {index} with ID {item.get('_id')} does not meet any condition."
            )

if __name__ == "__main__":
    unittest.main()