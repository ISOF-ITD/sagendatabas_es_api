"""Check compact document responses without Django or a live Elasticsearch server.

Run: python -m unittest discover -s tests -p test_documents_list_profile.py
"""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DocumentsListProfileTests(unittest.TestCase):
    def get_response(self, media, profile="list", **params):
        source = ast.parse((ROOT / "views.py").read_text(encoding="utf-8-sig"))
        constants = {"LIST_RESPONSE_PROFILE", "LIST_SOURCE_INCLUDES", "LIST_HIGHLIGHT_FRAGMENT_SIZE"}
        nodes = [node for node in source.body if (
            isinstance(node, ast.FunctionDef)
            and node.name in {"getDocuments", "usesListResponseProfile"}
        ) or (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id in constants for target in node.targets)
        )]
        hit = {
            "_id": "04416:3_253674",
            "_source": {"id": "04416:3_253674", "media": media},
            "inner_hits": {"media.utterances.utterances": {"hits": {"hits": []}}},
        }
        self.original = deepcopy(hit)

        def es_query(request, query, formatter):
            self.query = query
            response = {"data": formatter({"hits": {"hits": [hit]}})}
            self.assertEqual(hit, self.original, "Formatting must not mutate the ES response")
            return response

        namespace = {"createQuery": lambda *args: {"bool": {"must": []}}, "esQuery": es_query}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "views.py", "exec"), namespace)
        if profile is not None:
            params["response_profile"] = profile
        return namespace["getDocuments"](SimpleNamespace(GET=params))["data"][0]

    def test_metadata_only_asr_like_reported_record_has_no_transcription(self):
        metadata = {"process": [{"type": "asr", "method": "faster-whisper, no conditioning"}]}
        response = self.get_response([
            {"id": 1571351, "type": "audio", "utterances": {"metadata": metadata, "utterances": []}},
        ])
        audio = response["_source"]["media"][0]
        self.assertIs(audio["has_transcription"], False)
        self.assertEqual(audio["utterances"], {"metadata": metadata})

    def test_nonempty_text_preserves_process_without_sending_segments(self):
        for process_type in ("asr", "manual", "ocr+align"):
            with self.subTest(process_type=process_type):
                metadata = {"process": [{"type": process_type, "method": "manual transcription by Anki"}]}
                text = "Transcript content that must not be sent in a list response. " * 1000
                response = self.get_response([{
                    "type": "audio",
                    "utterances": {"metadata": metadata, "utterances": [{"text": text, "start": 0}]},
                }])
                audio = response["_source"]["media"][0]
                self.assertIs(audio["has_transcription"], True)
                self.assertEqual(audio["utterances"], {"metadata": metadata})
                self.assertNotIn("Transcript content", json.dumps(response))
                self.assertLess(len(json.dumps(response)), 1000)

    def test_missing_empty_or_invalid_text_is_not_a_transcription(self):
        for utterances in (None, {}, {"metadata": {}}, [], {"utterances": []}, {
            "utterances": [None, {}, {"text": None}, {"text": 42}, {"text": ""}, {"text": " \n "}],
        }):
            with self.subTest(utterances=utterances):
                response = self.get_response([{"type": "audio", "utterances": utterances}])
                self.assertIs(response["_source"]["media"][0]["has_transcription"], False)

    def test_legacy_segment_arrays_are_supported_without_returning_text(self):
        response = self.get_response([{"type": "audio", "utterances": [{"text": "Legacy text"}]}])
        audio = response["_source"]["media"][0]
        self.assertIs(audio["has_transcription"], True)
        self.assertNotIn("utterances", audio)

    def test_each_media_item_is_classified_independently(self):
        response = self.get_response([
            {"type": "audio", "utterances": {"metadata": {"process": [{"type": "asr"}]}}},
            {"type": "audio", "utterances": {"utterances": [{"text": "Readable"}]}},
            {"type": "image"},
        ])
        self.assertEqual([audio["has_transcription"] for audio in response["_source"]["media"]],
                         [False, True, False])

    def test_query_fetches_text_for_presence_and_keeps_pagination_and_short_highlights(self):
        self.get_response([], size="10", **{"from": "20"})
        includes = self.query["_source"]["includes"]
        self.assertIn("media.utterances.metadata.process", includes)
        self.assertIn("media.utterances.utterances.text", includes)
        self.assertIn("media.utterances.text", includes)
        self.assertNotIn("media.utterances", includes)
        self.assertEqual(self.query["size"], "10")
        self.assertEqual(self.query["from"], "20")
        self.assertEqual(self.query["highlight"]["fields"]["text"]["number_of_fragments"], 1)
        self.assertEqual(self.query["highlight"]["fields"]["text"]["fragment_size"], 300)

    def test_default_and_unknown_profile_preserve_the_full_response(self):
        media = [{"type": "audio", "utterances": {
            "metadata": {"process": [{"type": "asr"}]},
            "utterances": [{"start": 12, "end": 14, "text": "Full text"}],
        }}]
        for profile in (None, "full", "unknown"):
            with self.subTest(profile=profile):
                response = self.get_response(media, profile=profile)
                self.assertEqual(response, self.original)
                self.assertNotIn("_source", self.query)


if __name__ == "__main__":
    unittest.main()
