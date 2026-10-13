"""Tests for FFmpegCompressor.

Command-construction tests do not need the FFmpeg binary. The VFR regression
test runs the real binary and is skipped when FFmpeg is not installed.
"""

import subprocess  # nosec B404
from pathlib import Path

import pytest

from compressors.ffmpeg_compress import FFmpegCompressor


requires_ffmpeg = pytest.mark.skipif(
    not FFmpegCompressor.can_register(),
    reason="The ffmpeg binary is not installed.",
)


def _make_compressor(tmp_path, media_type):
    return FFmpegCompressor(
        input_file=str(tmp_path / f"in.{media_type}"),
        output_dir=str(tmp_path),
        media_type=media_type,
    )


def _make_vfr_gap_mov(path: Path) -> None:
    """Write a small VFR .mov shaped like a macOS screen recording.

    Two 10 s bursts of frames separated by a ~120 s gap with no frames. The
    jittered timestamps and the prime source timescale give an odd
    avg_frame_rate (600001800/140132087) with r_frame_rate=240/1, so FFmpeg
    guesses a huge output track timescale and the gap overflows the 32-bit
    sample duration in the MP4/MOV muxer unless the timescale is pinned.
    """
    subprocess.run(  # nosec B603
        [
            FFmpegCompressor.ffmpeg_path,
            '-v', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=30,trim=end_frame=600',
            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=145',
            '-filter_complex',
            "[0:v]settb=1/2400,"
            "setpts='((N*8 + mod(N*N,7))/240 + gte(N,300)*120.123457)/TB'[v]",
            '-map', '[v]', '-map', '1:a',
            '-fps_mode', 'passthrough',
            '-enc_time_base:v', '1/2400',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-bf', '0',
            '-c:a', 'aac',
            '-video_track_timescale', '1000003',
            '-t', '145',
            str(path),
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


@pytest.mark.parametrize("media_type", ["mp4", "mov", "m4v"])
def test_mp4_family_output_uses_fixed_video_track_timescale(tmp_path, media_type):
    args = _make_compressor(tmp_path, media_type)._build_codec_args('balanced')

    assert '-video_track_timescale' in args
    assert args[args.index('-video_track_timescale') + 1] == '90000'


@pytest.mark.parametrize("media_type", ["mkv", "avi", "webm", "flv"])
def test_non_mp4_family_output_keeps_default_timescale(tmp_path, media_type):
    args = _make_compressor(tmp_path, media_type)._build_codec_args('balanced')

    assert '-video_track_timescale' not in args


@requires_ffmpeg
def test_compress_vfr_mov_with_long_frame_gap(monkeypatch, safe_path_test_settings):
    """Regression for #315: a VFR .mov with a long frame gap must compress."""
    monkeypatch.setattr(
        'compressors.ffmpeg_compress.get_settings', lambda: safe_path_test_settings
    )
    input_file = safe_path_test_settings.upload_dir / f"{'e' * 32}.mov"
    _make_vfr_gap_mov(input_file)

    compressor = FFmpegCompressor(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        media_type='mov',
    )
    output_files = compressor.compress(compression_level='max')

    output = Path(output_files[0])
    assert output.exists()
    # Smaller than the source means the re-encoded file was kept rather than
    # the original bytes being copied through.
    assert output.stat().st_size < input_file.stat().st_size
