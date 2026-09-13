from unittest.mock import MagicMock, patch

from src.youtube import (
    fetch_all_trusted_videos,
    fetch_playlist_videos,
    get_uploads_playlist_id,
    load_trusted_channels,
    resolve_all_channel_ids,
    search_trusted_videos,
)


def _fake_response(json_data, status_ok=True):
    resp = MagicMock()
    resp.json.return_value = json_data
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = Exception("boom")
    return resp


def test_trusted_channels_schema():
    channels = load_trusted_channels()
    assert len(channels) > 0
    for channel in channels:
        assert channel["handle"].startswith("@")
        assert channel["name"]


def test_resolve_all_channel_ids_uses_cached_id_without_api_call():
    channels = [{"handle": "@already-resolved", "channel_id": "UC123", "name": "x"}]
    with patch("src.youtube.requests.get") as mock_get:
        resolved = resolve_all_channel_ids(channels, api_key="fake")
    mock_get.assert_not_called()
    assert resolved == {"@already-resolved": "UC123"}


def test_resolve_all_channel_ids_skips_handle_that_fails_to_resolve():
    channels = [
        {"handle": "@good", "channel_id": None, "name": "Good"},
        {"handle": "@typo-does-not-exist", "channel_id": None, "name": "Typo"},
    ]
    with patch("src.youtube.requests.get") as mock_get:
        mock_get.side_effect = [
            _fake_response({"items": [{"id": "UCgood"}]}),
            _fake_response({"items": []}),
        ]
        resolved = resolve_all_channel_ids(channels, api_key="fake")
    assert resolved == {"@good": "UCgood"}
    assert "@typo-does-not-exist" not in resolved


def test_search_trusted_videos_tags_results_with_source_handle_and_respects_max_total():
    channel_id_map = {"@a": "UCA", "@b": "UCB"}
    with patch("src.youtube.requests.get") as mock_get:
        mock_get.side_effect = [
            _fake_response(
                {
                    "items": [
                        {
                            "id": {"videoId": "vid1"},
                            "snippet": {
                                "title": "Video 1",
                                "channelTitle": "Channel A",
                                "channelId": "UCA",
                                "thumbnails": {"medium": {"url": "http://x/1.jpg"}},
                                "publishedAt": "2024-01-01T00:00:00Z",
                            },
                        }
                    ]
                }
            ),
            _fake_response(
                {
                    "items": [
                        {
                            "id": {"videoId": "vid2"},
                            "snippet": {
                                "title": "Video 2",
                                "channelTitle": "Channel B",
                                "channelId": "UCB",
                                "thumbnails": {},
                                "publishedAt": "2024-01-02T00:00:00Z",
                            },
                        }
                    ]
                }
            ),
        ]
        results = search_trusted_videos("anxiety", channel_id_map, api_key="fake", per_channel=1, max_total=6)

    assert len(results) == 2
    handles = {r["source_handle"] for r in results}
    assert handles == {"@a", "@b"}
    assert results[0]["url"] == "https://www.youtube.com/watch?v=vid1"


def test_search_trusted_videos_skips_channel_on_request_failure():
    channel_id_map = {"@a": "UCA", "@b": "UCB"}
    with patch("src.youtube.requests.get") as mock_get:
        mock_get.side_effect = [
            Exception("network down"),
            _fake_response(
                {
                    "items": [
                        {
                            "id": {"videoId": "vid2"},
                            "snippet": {
                                "title": "Video 2",
                                "channelTitle": "Channel B",
                                "channelId": "UCB",
                                "thumbnails": {},
                                "publishedAt": "2024-01-02T00:00:00Z",
                            },
                        }
                    ]
                }
            ),
        ]
        results = search_trusted_videos("anxiety", channel_id_map, api_key="fake", per_channel=1, max_total=6)

    assert len(results) == 1
    assert results[0]["source_handle"] == "@b"


def test_get_uploads_playlist_id_returns_playlist_id():
    with patch("src.youtube.requests.get") as mock_get:
        mock_get.return_value = _fake_response(
            {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUplaylist123"}}}]}
        )
        playlist_id = get_uploads_playlist_id("UCsome", api_key="fake")
    assert playlist_id == "UUplaylist123"


def test_get_uploads_playlist_id_returns_none_for_unknown_channel():
    with patch("src.youtube.requests.get") as mock_get:
        mock_get.return_value = _fake_response({"items": []})
        playlist_id = get_uploads_playlist_id("UCmissing", api_key="fake")
    assert playlist_id is None


def test_fetch_playlist_videos_skips_items_without_a_video_id():
    with patch("src.youtube.requests.get") as mock_get:
        mock_get.return_value = _fake_response(
            {
                "items": [
                    {
                        "snippet": {
                            "resourceId": {"videoId": "vid1"},
                            "title": "Video 1",
                            "description": "About patience.",
                            "channelTitle": "Channel A",
                            "channelId": "UCA",
                            "thumbnails": {"medium": {"url": "http://x/1.jpg"}},
                            "publishedAt": "2024-01-01T00:00:00Z",
                        }
                    },
                    # A privated/deleted video: the playlist entry survives
                    # but has no resourceId.videoId -- must be skipped, not
                    # crash on a missing key.
                    {"snippet": {"title": "Removed video"}},
                ]
            }
        )
        videos = fetch_playlist_videos("UUsome", api_key="fake")
    assert len(videos) == 1
    assert videos[0]["video_id"] == "vid1"
    assert videos[0]["url"] == "https://www.youtube.com/watch?v=vid1"


def test_fetch_all_trusted_videos_tags_source_handle_and_skips_failing_channel():
    channel_id_map = {"@a": "UCA", "@b": "UCB"}
    with patch("src.youtube.get_uploads_playlist_id") as mock_playlist_id, patch(
        "src.youtube.fetch_playlist_videos"
    ) as mock_fetch:
        mock_playlist_id.side_effect = ["UUA", Exception("channel gone")]
        mock_fetch.return_value = [{"video_id": "vid1", "title": "Video 1"}]
        videos = fetch_all_trusted_videos(channel_id_map, api_key="fake")
    assert len(videos) == 1
    assert videos[0]["source_handle"] == "@a"
