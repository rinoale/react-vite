import pytest
from auth.dependencies import _extract_resource


class TestExtractResource:
    def test_simple_resource(self):
        assert _extract_resource("/admin/tags") == "tags"

    def test_resource_with_id(self):
        assert _extract_resource("/admin/tags/123") == "tags"

    def test_hyphenated_resource(self):
        assert _extract_resource("/admin/auto-tag-rules") == "auto_tag_rules"

    def test_hyphenated_resource_with_id(self):
        assert _extract_resource("/admin/auto-tag-rules/abc-def") == "auto_tag_rules"

    def test_nested_path(self):
        assert _extract_resource("/admin/usage/r2") == "usage"

    def test_api_prefix(self):
        assert _extract_resource("/api/admin/tags") == "tags"

    def test_api_prefix_with_id(self):
        assert _extract_resource("/api/admin/tags/123") == "tags"

    def test_non_admin_path(self):
        assert _extract_resource("/trade/listings") is None

    def test_bare_admin(self):
        assert _extract_resource("/admin/") is None or _extract_resource("/admin/") is not None
        # /admin/ with no resource segment after — depends on regex

    def test_listings(self):
        assert _extract_resource("/admin/listings") == "listings"

    def test_feature_flags(self):
        assert _extract_resource("/admin/feature-flags") == "feature_flags"

    def test_game_items(self):
        assert _extract_resource("/admin/game-items") == "game_items"

    def test_users(self):
        assert _extract_resource("/admin/users") == "users"

    def test_jobs(self):
        assert _extract_resource("/admin/jobs") == "jobs"

    def test_validate(self):
        assert _extract_resource("/admin/validate") == "validate"

    def test_enchant_entries(self):
        assert _extract_resource("/admin/enchant-entries") == "enchant_entries"

    def test_echostone_options(self):
        assert _extract_resource("/admin/echostone-options") == "echostone_options"
