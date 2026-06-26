"""Tests for FFmpegConverter command construction.

These mirror the other converter unit tests: ``subprocess.run`` is mocked so
the FFmpeg binary is not required, and assertions are made against the command
FFmpegConverter builds.
"""

from converters.ffmpeg_convert import FFmpegConverter


def _fake_run_capturing(calls):
    """Return a ``subprocess.run`` replacement that records each command.

    The returned result has empty ``stdout``/``stderr`` so the ffprobe-based
    timeout estimation falls back gracefully and ``convert`` succeeds.
    """

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)

        class Result:
            stdout = ""
            stderr = ""

        return Result()

    return fake_run


def _vf_value(cmd):
    """Return the value passed to the (single) -vf argument, or None."""
    return cmd[cmd.index('-vf') + 1] if '-vf' in cmd else None


def test_gif_to_mp4_pads_odd_dimensions_to_even(monkeypatch, safe_path_test_settings):
    """GIF -> MP4 must pad to even dimensions so libx264/yuv420p can encode.

    libx264 with yuv420p requires both dimensions to be even and aborts with
    "height not divisible by 2" otherwise. GIFs commonly have odd dimensions,
    so the converter pads up to the next even size.
    """
    input_file = safe_path_test_settings.upload_dir / f"{'a' * 32}.gif"
    input_file.write_bytes(b"GIF89a fixture")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "converters.ffmpeg_convert.subprocess.run", _fake_run_capturing(calls)
    )

    converter = FFmpegConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type="gif",
        output_type="mp4",
    )
    converter.convert()

    ffmpeg_cmd = calls[-1]
    assert '-pix_fmt' in ffmpeg_cmd
    assert ffmpeg_cmd[ffmpeg_cmd.index('-pix_fmt') + 1] == 'yuv420p'
    assert _vf_value(ffmpeg_cmd) == 'pad=ceil(iw/2)*2:ceil(ih/2)*2'


def test_mp4_to_apng_keeps_scale_filter_without_padding(monkeypatch, safe_path_test_settings):
    """Animated-image output keeps its single -vf chain and is not padded.

    APNG natively supports transparency, so it is not forced to yuv420p and
    must not receive the even-dimension pad. This also guards that the scale
    filter and the pad filter never collide into two -vf arguments (FFmpeg
    honours only the last).
    """
    input_file = safe_path_test_settings.upload_dir / f"{'b' * 32}.mp4"
    input_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "converters.ffmpeg_convert.subprocess.run", _fake_run_capturing(calls)
    )

    converter = FFmpegConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type="mp4",
        output_type="apng",
    )
    converter.convert()

    ffmpeg_cmd = calls[-1]
    assert ffmpeg_cmd.count('-vf') == 1
    assert _vf_value(ffmpeg_cmd) == 'fps=10,scale=320:-1:flags=lanczos'
    assert '-pix_fmt' not in ffmpeg_cmd


def test_video_to_audio_has_no_padding_filter(monkeypatch, safe_path_test_settings):
    """Audio-only output strips video and adds no even-dimension pad filter."""
    input_file = safe_path_test_settings.upload_dir / f"{'c' * 32}.mp4"
    input_file.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "converters.ffmpeg_convert.subprocess.run", _fake_run_capturing(calls)
    )

    converter = FFmpegConverter(
        input_file=str(input_file),
        output_dir=str(safe_path_test_settings.output_dir),
        input_type="mp4",
        output_type="mp3",
    )
    converter.convert()

    ffmpeg_cmd = calls[-1]
    assert '-vn' in ffmpeg_cmd
    assert _vf_value(ffmpeg_cmd) is None
