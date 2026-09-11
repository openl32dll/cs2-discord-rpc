"""
Unit tests for the pure logic in cs2_discord_rpc.py: map/mode display
names, the Rich Presence field builder, and the language (i18n) system.
No Discord connection or GSI server is involved — these test the data
transformation only.
"""

import importlib

import pytest

import cs2_discord_rpc as rpc


def reload_with_language(monkeypatch, lang):
    """Reloads the module with RPC_LANGUAGE set (or unset), returning the
    freshly-reloaded module object. Needed because the display language
    is resolved once, at import time.
    """
    if lang is None:
        monkeypatch.delenv("RPC_LANGUAGE", raising=False)
    else:
        monkeypatch.setenv("RPC_LANGUAGE", lang)
    return importlib.reload(rpc)


@pytest.fixture(autouse=True)
def _reset_to_english(monkeypatch):
    """Every test starts from a known state: English, no leftover env."""
    reload_with_language(monkeypatch, None)
    yield


class TestMapNames:
    def test_known_map(self):
        assert rpc.display_map_name("de_mirage") == "Mirage"

    def test_unknown_map_strips_known_prefix(self):
        assert rpc.display_map_name("de_newmap") == "Newmap"

    def test_unknown_map_without_prefix(self):
        assert rpc.display_map_name("somemap") == "Somemap"

    def test_none_map_name(self):
        assert rpc.display_map_name(None) == "Unknown Map"


class TestModeLabels:
    def test_known_modes(self):
        assert rpc.mode_label("competitive") == "Competitive"
        assert rpc.mode_label("scrimcomp5v5") == "Premier"
        assert rpc.mode_label("scrimcomp2v2") == "Wingman"
        assert rpc.mode_label("deathmatch") == "Deathmatch"

    def test_unknown_mode(self):
        assert rpc.mode_label("some_new_mode") == "Unknown Mode"

    def test_none_mode(self):
        assert rpc.mode_label(None) == "Unknown Mode"


class TestMapImageKey:
    def test_known_map_uses_its_own_key(self):
        assert rpc.map_image_key("de_dust2") == "de_dust2"

    def test_unknown_map_falls_back_to_logo(self):
        assert rpc.map_image_key("de_brandnew") == "cs2_logo"

    def test_none_falls_back_to_logo(self):
        assert rpc.map_image_key(None) == "cs2_logo"


class TestLanguage:
    def test_default_is_english(self, monkeypatch):
        m = reload_with_language(monkeypatch, None)
        assert m.LANGUAGE == "en"

    def test_turkish_can_be_selected(self, monkeypatch):
        m = reload_with_language(monkeypatch, "tr")
        assert m.LANGUAGE == "tr"
        assert m.mode_label("competitive") == "Rekabetçi"
        assert m.display_map_name(None) == "Bilinmeyen Harita"

    def test_unknown_language_falls_back_to_english(self, monkeypatch):
        m = reload_with_language(monkeypatch, "xx")
        assert m.LANGUAGE == "en"

    def test_language_is_case_insensitive(self, monkeypatch):
        m = reload_with_language(monkeypatch, "TR")
        assert m.LANGUAGE == "tr"


class TestBuildPresenceFields:
    def test_main_menu_has_no_small_badge(self):
        fields = rpc.build_presence_fields({"player": {"activity": "menu"}})
        assert fields["details"] == "Browsing main menu"
        assert fields["large_image"] == "cs2_logo"
        assert "small_image" not in fields

    def test_warmup_phase(self):
        payload = {
            "player": {"activity": "playing"},
            "map": {"name": "de_dust2", "mode": "competitive", "phase": "warmup"},
        }
        fields = rpc.build_presence_fields(payload)
        assert fields["state"] == "Warmup"
        assert "Dust II" in fields["details"]
        assert "Competitive" in fields["details"]

    def test_gameover_phase(self):
        payload = {
            "player": {"activity": "playing"},
            "map": {"name": "de_mirage", "mode": "competitive", "phase": "gameover"},
        }
        fields = rpc.build_presence_fields(payload)
        assert fields["state"] == "Match over"

    def test_live_round_based_mode_shows_round_and_score(self):
        payload = {
            "player": {"activity": "playing"},
            "map": {
                "name": "de_inferno",
                "mode": "competitive",
                "phase": "live",
                "round": 4,  # GSI rounds are 0-indexed
                "team_ct": {"score": 3},
                "team_t": {"score": 2},
            },
        }
        fields = rpc.build_presence_fields(payload)
        assert fields["state"] == "Round 5/24 · CT 3 - 2 T"
        assert fields["large_image"] == "de_inferno"

    def test_live_roundless_mode_shows_kills_and_deaths(self):
        payload = {
            "player": {"activity": "playing", "match_stats": {"kills": 10, "deaths": 4}},
            "map": {"name": "de_nuke", "mode": "deathmatch", "phase": "live"},
        }
        fields = rpc.build_presence_fields(payload)
        assert fields["state"] == "10 kills / 4 deaths"

    def test_bomb_planted_is_appended_to_state(self):
        payload = {
            "player": {"activity": "playing"},
            "map": {
                "name": "de_overpass",
                "mode": "competitive",
                "phase": "live",
                "round": 0,
                "team_ct": {"score": 0},
                "team_t": {"score": 0},
            },
            "round": {"bomb": "planted"},
        }
        fields = rpc.build_presence_fields(payload)
        assert "Bomb planted" in fields["state"]

    def test_unlisted_map_falls_back_to_logo_image(self):
        payload = {
            "player": {"activity": "playing"},
            "map": {"name": "de_brandnew", "mode": "custom", "phase": "live", "round": 0},
        }
        fields = rpc.build_presence_fields(payload)
        assert fields["large_image"] == "cs2_logo"

    def test_wingman_uses_16_round_cap(self):
        payload = {
            "player": {"activity": "playing"},
            "map": {
                "name": "de_shortdust",
                "mode": "scrimcomp2v2",
                "phase": "live",
                "round": 0,
                "team_ct": {"score": 0},
                "team_t": {"score": 0},
            },
        }
        fields = rpc.build_presence_fields(payload)
        assert fields["state"].startswith("Round 1/16")


class TestStateKey:
    def test_none_fields_is_empty_tuple(self):
        assert rpc.state_key(None) == ()

    def test_only_tracked_fields_are_compared(self):
        fields = {
            "details": "a",
            "state": "b",
            "large_image": "c",
            "small_image": "d",
            "large_text": "ignored",
        }
        assert rpc.state_key(fields) == ("a", "b", "c", "d")
