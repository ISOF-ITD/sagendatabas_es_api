"""Exercise the socken response formatter without Django or a live ES server.

The endpoint is compiled from views.py; only its infrastructure dependencies
are replaced. This checkout does not include the deployment's es_config.py.
Run with: python -m unittest discover -s tests -p test_socken_response.py
"""
import ast
import importlib.util
import json
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("geohash", ROOT / "geohash.py")
geohash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geohash)


class JsonResponse(dict):
    def __init__(self, data):
        super().__init__()
        self.content = json.dumps(data)


def socken_bucket(identifier, coordinates):
    return {
        "key": identifier,
        "data": {"buckets": [{"key": "Alnö sn"}]},
        "harad": {"buckets": []},
        "landskap": {"buckets": [{"key": "Medelpad"}]},
        "lan": {"buckets": []},
        "lm_id": {"buckets": []},
        "location": {"buckets": coordinates},
        "parent_doc_count": {"doc_count": 7},
        "page_count": {"pages": {"value": 15}},
        "relation_type": {"buckets": []},
    }


class SockenResponseTests(unittest.TestCase):
    def get_response(self, buckets):
        source = ast.parse((ROOT / "views.py").read_text(encoding="utf-8-sig"))
        endpoint = next(node for node in source.body
                        if isinstance(node, ast.FunctionDef) and node.name == "getSocken")

        def es_query(request, query, formatter, *args):
            return {"data": formatter({
                "aggregations": {"data": {"data": {"buckets": buckets}}},
            })}

        namespace = {
            "geohash": geohash,
            "createQuery": lambda request: {},
            "esQuery": es_query,
            "JsonResponse": JsonResponse,
            "logger": logging.getLogger(__name__),
        }
        exec(compile(ast.Module(body=[endpoint], type_ignores=[]), "views.py", "exec"), namespace)
        response = namespace["getSocken"](SimpleNamespace(GET={}))
        return json.loads(response.content)

    def test_missing_coordinates_preserve_socken_and_hit_count(self):
        response = self.get_response([socken_bucket("559", [])])
        point = response["data"][0]
        self.assertEqual(point["id"], "559")
        self.assertEqual(point["name"], "Alnö sn")
        self.assertEqual(point["landskap"], "Medelpad")
        self.assertEqual(point["doc_count"], 7)
        self.assertIsNone(point["location"])

    def test_mixed_response_preserves_existing_coordinate_format(self):
        encoded = geohash.encode(62.4, 17.4, 12)
        response = self.get_response([
            socken_bucket("559", [{"key": encoded}]),
            socken_bucket("672", []),
        ])
        self.assertEqual(len(response["data"]), 2)
        located, unlocated = response["data"]
        self.assertIsInstance(located["location"], list)
        self.assertEqual(len(located["location"]), 2)
        self.assertAlmostEqual(located["location"][0], 62.4, places=5)
        self.assertAlmostEqual(located["location"][1], 17.4, places=5)
        self.assertEqual(located["doc_count"], unlocated["doc_count"])
        self.assertIsNone(unlocated["location"])


if __name__ == "__main__":
    unittest.main()
