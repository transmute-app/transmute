import asyncio
import hashlib
from pathlib import Path

import pytest
import yt_dlp
from yt_dlp.utils import RetryManager

from downloaders import DownloadError, YtDlpDownloader


URL = "https://www.youtube.com/watch?v=video"
ERROR = "unable to download video data: HTTP Error 403: Forbidden"


@pytest.mark.parametrize("key, expected_retries", [
    ("retries", 10),
    ("extractor_retries", 3),
    ("fragment_retries", 10),
])
def test_download_retries_transient_failures(monkeypatch, tmp_path, key, expected_retries):
    attempts = []

    def extract_info(ydl, url, download):
        for retry in RetryManager(ydl.params.get(key), lambda *args: None):
            attempts.append(retry.attempt)
            retry.error = OSError("temporary failure")
        ydl.report_error(ERROR)

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)

    with pytest.raises(DownloadError, match="HTTP Error 403: Forbidden"):
        asyncio.run(YtDlpDownloader().download(URL, tmp_path, "test"))

    assert len(attempts) == expected_retries + 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("info, fallback", [
    (None, "yt-dlp returned no info for the given URL"),
    ({"_type": "playlist", "entries": [None]}, "yt-dlp completed but no files were downloaded"),
    ({"id": "video"}, "yt-dlp completed but no valid output files were found"),
])
@pytest.mark.parametrize("report_error", [True, False])
def test_failed_download_preserves_error_or_fallback(monkeypatch, tmp_path, info, fallback, report_error):
    def extract_info(ydl, url, download):
        if report_error:
            ydl.report_error(ERROR)
        return info

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)

    with pytest.raises(DownloadError) as exc:
        asyncio.run(YtDlpDownloader().download(URL, tmp_path, "test"))

    expected = f"Failed to download from supported site: ERROR: {ERROR}" if report_error else fallback
    assert str(exc.value) == expected
    assert not list(tmp_path.iterdir())


def test_playlist_keeps_successful_entries_after_error(monkeypatch, tmp_path):
    def extract_info(ydl, url, download):
        assert ydl.params["noplaylist"] is False
        ydl.report_error(ERROR)
        staging_dir = Path(ydl.params["outtmpl"]["default"]).parent
        (staging_dir / "2_video.mp4").write_bytes(b"video content")
        return {"_type": "playlist", "entries": [None, {"id": "video", "title": "Video"}]}

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
    results = asyncio.run(YtDlpDownloader().download(
        "https://www.youtube.com/playlist?list=test", tmp_path, "test",
    ))

    assert len(results) == 1
    assert results[0].file_path == tmp_path / "test.mp4"
    assert results[0].file_path.read_bytes() == b"video content"
    assert results[0].sha256_checksum == hashlib.sha256(b"video content").hexdigest()
    assert not (tmp_path / ".ytdlp_test").exists()


def test_errors_do_not_leak_between_downloads(monkeypatch, tmp_path):
    def extract_info(ydl, url, download):
        if url == URL:
            ydl.report_error(ERROR)
        return None

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
    downloader = YtDlpDownloader()
    with pytest.raises(DownloadError, match="HTTP Error 403"):
        asyncio.run(downloader.download(URL, tmp_path, "first"))
    with pytest.raises(DownloadError, match="^yt-dlp returned no info for the given URL$"):
        asyncio.run(downloader.download("https://vimeo.com/123", tmp_path, "second"))
    assert not list(tmp_path.iterdir())


def test_raised_download_error_is_preserved(monkeypatch, tmp_path):
    def extract_info(ydl, url, download):
        raise yt_dlp.utils.DownloadError(ERROR)

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", extract_info)
    with pytest.raises(DownloadError, match="HTTP Error 403: Forbidden"):
        asyncio.run(YtDlpDownloader().download(URL, tmp_path, "test"))
    assert not list(tmp_path.iterdir())
