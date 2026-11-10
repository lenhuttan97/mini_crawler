"""Import-layout regression for the project-structure refactor.

These assertions only check that the planned package namespaces resolve.
They intentionally do not exercise feature behavior; they exist so a stale
module path cannot survive unnoticed after modules move.
"""

from __future__ import annotations

import importlib

EXPECTED_IMPORTS = [
    ("app.bootstrap.settings", "Settings"),
    ("app.platform.network_policy.policy", "PolicyGate"),
    ("app.features.web_crawl.application.service", "CrawlService"),
    ("app.features.search.application.service", "SearchService"),
    ("app.features.image_download.application.service", "MediaService"),
    ("app.features.video_download.application.service", "VideoDiscoveryService"),
    ("app.entrypoints.celery_worker", "create_celery_app"),
    ("app.legacy_api.main", "create_app"),
]


def test_planned_namespaces_import():
    for module, symbol in EXPECTED_IMPORTS:
        mod = importlib.import_module(module)
        assert hasattr(mod, symbol), f"{module} exposes no {symbol}"
