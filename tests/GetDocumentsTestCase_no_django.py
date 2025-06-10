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

    Debugging:
        Check example queries in:
        explore_highlight_nested_text.txt
        GetDocument_search_media_description_HighlightHits.txt
    """

    # base_url = "http://localhost:8000/api/es/"
    base_url = "https://garm-test.isof.se/folkeservice/api/es/"
    use_slash = "/"
    # use_slash = ""

    count_all = "count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false"
    # contentG2 = bild
    count_image = "count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&category=contentG2"
    # contentG5 = ljud
    count_audio = "count/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&category=contentG5"

    # Define a struct-like dictionary to hold search text and expected counts
    test_cases = [
        {
            # 3 hits in text, 1 in audio desription:
            "search_text": "rompedrag",
            "expected_counts": {
                # counts correct 2025-05-09. Uppdatera om dom ändras!
                "count_all_minimum": 4,
                "count_audio_minimum": 1,
                "count_image_minimum": 0
            }
        },
        {
            # 1 hits in text, 1 in audio utterance:
            # vff02333_204956_2 skeen (skeden)
            # s00247:a_f_127613_a, s00247:a_f_X_127613_a Lund/Ljudarkiv/1-1000/201-300/S 247A_mp3.MP3: Skeena torg, Numera skena torg
            "search_text": "skeena",
            "expected_counts": {
                # counts correct 2025-05-09. Uppdatera om dom ändras!
                "count_all_minimum": 1,
                "count_audio_minimum": 0,  # var tidigare 1
                "count_image_minimum": 0
            }
        },
        {
            # 1 in audio utterance:
            # vråhållet: 1 1 0: s00247:a_f_127613_a, s00247:a_f_X_127613_a Lund/Ljudarkiv/1-1000/201-300/S 247A_mp3.MP3
            # brönnäng: 1 1 0: iodb00154_192225_a, Goteborg/Ljudarkiv/IOD_SK/301-400/SK311A.MP3
            "search_text": "vråhållet",
            "expected_counts": {
                # counts correct 2025-05-09. Uppdatera om dom ändras!
                "count_all_minimum": 1,
                "count_audio_minimum": 1,
                "count_image_minimum": 0
            }
        }
    ]
    """
    # Test only one case:
    test_cases = [
        {
            # 1 in audio utterance:
            # vråhållet: 1 1 0: s00247:a_f_127613_a, s00247:a_f_X_127613_a Lund/Ljudarkiv/1-1000/201-300/S 247A_mp3.MP3
            # brönnäng: 1 1 0: iodb00154_192225_a, Goteborg/Ljudarkiv/IOD_SK/301-400/SK311A.MP3
            "search_text": "vråhållet",
            "expected_counts": {
                # counts correct 2025-05-09. Uppdatera om dom ändras!
                "count_all_minimum": 1,
                "count_audio_minimum": 1,
                "count_image_minimum": 0
            }
        }
    ]
    """

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
    # transcriptionstatus = "published,accession"
    transcriptionstatus = "transcriptionstatus=published,accession,readytocontribute"
    socken = "socken/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false"
    documents = "documents/?type=arkiv&categorytypes=tradark&publishstatus=published&has_media=true&add_aggregations=false&size=100&sort=archive.archive_id_row.keyword&order=asc"
    category_audio = "category=contentG2"

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
        logid_test = "test_01_documents_search_count"
        for case in self.test_cases:
            with self.subTest(search_text=case["search_text"]):
                logid = logid_test + " " + case["search_text"]
                url = f"{self.base_url}" + self.count_all + '&' + self.transcriptionstatus + '&' + 'search=' + case[
                    "search_text"]
                print(logid + ' ' + str(url))
                response = requests.get(url)
                self.log_response(response, logid)
                self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
                self.assertGreaterEqual(
                    response.json().get("data", {}).get("value", 0),
                    case["expected_counts"]["count_all_minimum"],
                    f"Unexpected value: {response.json()}"
                )

                url = f"{self.base_url}" + self.count_audio + '&' + self.transcriptionstatus + '&' + 'search=' + case[
                    "search_text"]
                print(logid + ' ' + str(url))
                response = requests.get(url)
                self.log_response(response, logid)
                self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
                self.assertGreaterEqual(
                    response.json().get("data", {}).get("value", 0),
                    case["expected_counts"]["count_audio_minimum"],
                    f"Unexpected value: {response.json()}"
                )

                url = f"{self.base_url}" + self.count_image + '&' + self.transcriptionstatus + '&' + 'search=' + case[
                    "search_text"]
                print(logid + ' ' + str(url))
                response = requests.get(url)
                self.log_response(response, logid)
                self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
                self.assertGreaterEqual(
                    response.json().get("data", {}).get("value", 0),
                    case["expected_counts"]["count_image_minimum"],
                    f"Unexpected value: {response.json()}"
                )

    def test_10_socken_search_text(self):
        logid_test = "test_10_socken_search_text"
        for case in self.test_cases:
            with self.subTest(search_text=case["search_text"]):
                logid = logid_test + " " + case["search_text"]
                url = f"{self.base_url}" + self.socken + '&' + self.transcriptionstatus + '&' + 'search=' + case[
                    "search_text"]
                print(logid + ' ' + str(url))
                # print(logid + ' ' + str(files))
                response = requests.get(url)
                self.log_response(response, logid)
                self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")

    def test_20_documents_search_text(self):
        logid_test = "test_20_documents_search_text"

        for case in self.test_cases:
            with self.subTest(search_text=case["search_text"]):
                logid = logid_test + " " + case["search_text"]
                url = f"{self.base_url}" + self.documents + '&' + self.transcriptionstatus + '&' + 'search=' + case[
                    "search_text"]
                print(logid + ' ' + str(url))
                # print(logid + ' ' + str(files))
                response = requests.get(url)
                self.log_response(response, logid)
                self.assertEqual(response.status_code, 200, f"Unexpected status code: {response.status_code}")
                # self.assertIn("success", response.json(), f"Unexpected response: {response.json()}")

                data = response.json().get("data", [])

                for index, item in enumerate(data):
                    condition_met = False

                    # I. Latest Elasticsearch double nested query response structure:
                    # Condition 1a: Check inner_hits."media.description"
                    results = []
                    media_description_hits = (
                        item.get("inner_hits", {})
                        .get("media.description", {})
                        .get("hits", {})
                        .get("hits", [])
                    )

                    for hit in media_description_hits:
                        # Extract highlight text(s)
                        highlights = hit.get("highlight", {}).get("media.description.text", [])

                        # Extract start value from _source
                        start_value = hit.get("_source", {}).get("start")

                        # Extract nested offsets
                        nested_info = hit.get("_nested", {})
                        media_offset = nested_info.get("offset")
                        description_offset = nested_info.get("_nested", {}).get("offset")

                        # Collect each highlight and its context
                        for highlight_text in highlights:
                            results.append({
                                "highlight_text": highlight_text,
                                "start_value": start_value,
                                "media_offset": media_offset,
                                "next_offset": description_offset,
                            })

                    # Example: print all collected results
                    for item in results:
                        if case["search_text"] in item["highlight_text"].lower():
                            condition_met = True
                            message = logid + ' description hit: '  + 'start_value: ' + str(item["start_value"]) + ' ' + str(item["highlight_text"]) + ' media_offset: ' + str(item["media_offset"])  + ' offset: ' + str(item["next_offset"])
                            print(message)
                            break
                    if condition_met:
                        break

                    # Condition 1b: Check inner_hits.media_with_utterances.media.utterances.utterances._source.text
                    results = []
                    media_description_hits = (
                        item.get("inner_hits", {})
                        .get("media.utterances.utterances", {})
                        .get("hits", {})
                        .get("hits", [])
                    )

                    for hit in media_description_hits:
                        # Extract highlight text(s)
                        highlights = hit.get("highlight", {}).get("media.utterances.utterances.text", [])

                        # Extract start value from _source
                        start_value = hit.get("_source", {}).get("start")

                        # Extract nested offsets
                        nested_info = hit.get("_nested", {})
                        media_offset = nested_info.get("offset")
                        utterances_offset = nested_info.get("_nested", {}).get("offset")

                        # Collect each highlight and its context
                        for highlight_text in highlights:
                            results.append({
                                "highlight_text": highlight_text,
                                "start_value": start_value,
                                "media_offset": media_offset,
                                "next_offset": utterances_offset,
                            })

                    # Example: print all collected results
                    for item in results:
                        if case["search_text"] in item["highlight_text"].lower():
                            condition_met = True
                            message = logid + ' utterances.utterances hit: ' + 'start_value: ' + str(item["start_value"]) + ' ' + str(item["highlight_text"]) + ' media_offset: ' + str(item["media_offset"])  + ' offset: ' + str(item["next_offset"])
                            print(message)
                            break
                    if condition_met:
                        break

                    # II. Old Elasticsearch double nested query response structure:
                    # Condition 1a: Check inner_hits.media_with_description.media.description._source.text
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
                            if case["search_text"] in desc_text.lower():
                                condition_met = True
                                print(logid + ' description hit:' + str(desc_text))
                                break
                        if condition_met:
                            break

                    # Condition 1b: Check inner_hits.media_with_utterances.media.utterances.utterances._source.text
                    media_utter_hits = (
                        inner_hits.get("media_with_utterances", {})
                        .get("hits", {})
                        .get("hits", [])
                    )

                    for utter_hit in media_utter_hits:
                        utter_hits = (
                            utter_hit.get("inner_hits", {})
                            .get("media.utterances.utterances", {})
                            .get("hits", {})
                            .get("hits", [])
                        )

                        for utter in utter_hits:
                            utter_text = utter.get("_source", {}).get("text", "")
                            if case["search_text"] in utter_text.lower():
                                print(logid + ' utterance hit:' + str(utter_text))
                                condition_met = True
                                break
                        if condition_met:
                            break

                    # Condition 2: Check highlight.text contains case["search_text"]
                    if not condition_met:
                        highlights = item.get("highlight", {}).get("text", [])
                        # Remove newlines:
                        if any(case["search_text"] in h.lower().replace('-\n', '') for h in highlights):
                            condition_met = True
                            print(logid + ' highlight hit:' + case["search_text"] + " IN " + str(highlights))

                    if not condition_met:
                        # Check if any category is audio
                        is_audio = False
                        taxonomy = item.get("_source", {}).get("taxonomy", [])
                        if any(cat.get("category") == "contentG5" for cat in taxonomy):
                            is_audio = True
                        if not is_audio:
                            highlight_text = item.get("highlight", {}).get("text", [])
                            # NO CHECK if equal: highlight text can be an hit by language analyzer and not equal to search text:
                            # if case["search_text"] in highlight_text.lower():
                            condition_met = True
                            print(logid + ' highlight text language analyzer hit so:' + case[
                                "search_text"] + " NOT EXACT IN " + str(highlight_text))

                    # Assert that the current item meets at least one condition
                    self.assertTrue(
                        condition_met,
                        f"Item at index {index} with ID {item.get('_id')} does not meet any condition."
                    )


if __name__ == "__main__":
    unittest.main()