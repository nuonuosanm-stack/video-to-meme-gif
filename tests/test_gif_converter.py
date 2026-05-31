from pathlib import Path


def test_parse_gif_settings_accepts_expected_ranges():
    from gif_toolkit.services.gif_converter import parse_gif_settings

    settings = parse_gif_settings(
        start_time="1.5",
        duration="3",
        width="320",
        fps="8",
        speed="1.25",
        target_size="1048576",
        quality_mode="standard",
        crop_mode="custom",
        crop_x="0.1",
        crop_y="0.2",
        crop_w="0.5",
        crop_h="0.6",
    )

    assert settings.start_time == 1.5
    assert settings.duration == 3
    assert settings.width == 320
    assert settings.fps == 8
    assert settings.speed == 1.25
    assert settings.target_size == 1048576
    assert settings.quality_mode == "standard"
    assert settings.crop_mode == "custom"
    assert settings.crop_x == 0.1
    assert settings.crop_y == 0.2
    assert settings.crop_w == 0.5
    assert settings.crop_h == 0.6


def test_parse_gif_settings_rejects_invalid_values():
    from gif_toolkit.services.gif_converter import GifConversionError, parse_gif_settings

    base = {
        "start_time": "0",
        "duration": "3",
        "width": "320",
        "fps": "8",
        "speed": "1",
        "target_size": "1048576",
        "quality_mode": "standard",
    }
    invalid_cases = [
        {"duration": "5.1"},
        {"width": "120"},
        {"fps": "30"},
        {"speed": "3"},
        {"quality_mode": "huge"},
        {"crop_mode": "custom", "crop_x": "0.8", "crop_w": "0.3"},
    ]

    for override in invalid_cases:
        values = dict(base)
        values.update(override)
        try:
            parse_gif_settings(**values)
        except GifConversionError:
            pass
        else:
            raise AssertionError(f"settings should fail: {override}")


def test_build_ffmpeg_commands_are_argument_arrays(tmp_path):
    from gif_toolkit.services.gif_converter import GifSettings, build_ffmpeg_commands

    input_path = tmp_path / "input.mp4"
    palette_path = tmp_path / "palette.png"
    output_path = tmp_path / "output.gif"
    settings = GifSettings(
        start_time=1,
        duration=3,
        width=320,
        fps=8,
        speed=1.25,
        target_size=1024 * 1024,
        quality_mode="standard",
        crop_mode="custom",
        crop_x=0.1,
        crop_y=0.2,
        crop_w=0.5,
        crop_h=0.6,
    )

    palette_cmd, gif_cmd = build_ffmpeg_commands(input_path, palette_path, output_path, settings, colors=96)

    assert palette_cmd[:8] == ["ffmpeg", "-y", "-ss", "1", "-t", "3", "-i", str(input_path)]
    assert gif_cmd[:10] == ["ffmpeg", "-y", "-ss", "1", "-t", "3", "-i", str(input_path), "-i", str(palette_path)]
    assert any("crop=iw*0.5:ih*0.6:iw*0.1:ih*0.2" in part for part in palette_cmd + gif_cmd)
    assert any("palettegen=max_colors=96" in part for part in palette_cmd)
    assert any("paletteuse=dither=bayer" in part for part in gif_cmd)
    assert all(isinstance(part, str) for part in palette_cmd + gif_cmd)
    assert "&&" not in " ".join(palette_cmd + gif_cmd)


def test_converter_tries_requested_quality_then_fallback(tmp_path):
    from gif_toolkit.services.gif_converter import GifConverter, GifSettings

    sizes = [2 * 1024 * 1024, 800 * 1024]
    commands = []

    def fake_runner(command, **_kwargs):
        commands.append(command)
        target = Path(command[-1])
        if target.suffix == ".gif":
            target.write_bytes(b"x" * sizes.pop(0))
        else:
            target.write_bytes(b"palette")

    converter = GifConverter(run_command=fake_runner, timeout_seconds=5)
    source = tmp_path / "source.mp4"
    source.write_bytes(b"video")
    settings = GifSettings(
        start_time=0,
        duration=3,
        width=480,
        fps=12,
        speed=1,
        target_size=1024 * 1024,
        quality_mode="standard",
    )

    result = converter.convert(source, tmp_path / "out", settings)

    assert result.file_size == 800 * 1024
    assert result.width == 360
    assert result.fps == 10
    assert result.colors == 96
    assert result.attempts == 2
    assert len([command for command in commands if command[-1].endswith(".gif")]) == 2
