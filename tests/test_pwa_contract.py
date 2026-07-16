import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PwaContractTests(unittest.TestCase):
    def test_manifest_is_valid_and_installable_shape(self):
        manifest = json.loads((ROOT / "static/pwa/manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["start_url"], "/?source=pwa")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)

    def test_service_worker_avoids_sensitive_api_cache(self):
        source = (ROOT / "static/pwa/service-worker.js").read_text(encoding="utf-8")
        self.assertIn("url.pathname.startsWith('/api/')", source)
        self.assertIn("url.pathname.startsWith('/admin')", source)
        self.assertIn("fetch(request).catch(() => caches.match(OFFLINE_URL))", source)

    def test_pwa_route_module_parses(self):
        ast.parse((ROOT / "pwa.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
