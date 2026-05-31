from pathlib import Path

from fastapi.testclient import TestClient


class FakeConverter:
    def __init__(self):
        self.calls = []

    def probe(self, _source_path):
        return {"duration": 12.5, "width": 640, "height": 360}

    def convert(self, source_path, output_dir, settings):
        from gif_toolkit.services.gif_converter import GifConversionResult

        self.calls.append((source_path, output_dir, settings))
        output_path = Path(output_dir) / "result.gif"
        output_path.write_bytes(b"gif")
        return GifConversionResult(
            output_path=output_path,
            file_size=3,
            duration=settings.duration,
            width=settings.width,
            fps=settings.fps,
            colors=128,
            attempts=1,
        )


def build_client(tmp_path):
    from gif_toolkit.app import create_app
    from gif_toolkit.services.gif_tasks import GifTaskStore

    converter = FakeConverter()
    output_dir = tmp_path / "outputs"
    temp_dir = tmp_path / "tmp"
    store = GifTaskStore(tmp_path / "tasks.json", now_ms=lambda: 123456)
    app = create_app(
        output_dir=output_dir,
        temp_dir=temp_dir,
        task_store=store,
        converter=converter,
        uuid_hex=lambda: "fixedtask",
    )
    return TestClient(app), converter, store, output_dir, temp_dir


def test_create_gif_task_writes_output_and_exposes_result(tmp_path):
    client, converter, _store, output_dir, temp_dir = build_client(tmp_path)

    response = client.post(
        "/api/gif/create",
        data={
            "start_time": "1",
            "duration": "3",
            "width": "320",
            "fps": "8",
            "speed": "1",
            "target_size": "1048576",
            "quality_mode": "standard",
            "crop_mode": "custom",
            "crop_x": "0.1",
            "crop_y": "0.2",
            "crop_w": "0.5",
            "crop_h": "0.6",
        },
        files={"file": ("clip.mp4", b"video-bytes", "video/mp4")},
    )

    assert response.status_code == 200
    assert response.json() == {"task_id": "fixedtask", "status": "processing"}
    task = client.get("/api/gif/tasks/fixedtask")
    assert task.status_code == 200
    body = task.json()
    assert body["status"] == "success"
    assert body["gif_url"] == "/outputs/video_gif_fixedtask.gif"
    assert body["download_url"] == "/outputs/video_gif_fixedtask.gif"
    assert body["file_size"] == 3
    assert body["crop_mode"] == "custom"
    assert body["crop"] == {"mode": "custom", "x": 0.1, "y": 0.2, "w": 0.5, "h": 0.6}
    assert converter.calls[0][2].duration == 3
    assert converter.calls[0][2].crop_mode == "custom"
    assert not (temp_dir / "gif_tmp_fixedtask").exists()
    assert (output_dir / "video_gif_fixedtask.gif").read_bytes() == b"gif"


def test_create_gif_task_rejects_invalid_upload_and_clip_overflow(tmp_path):
    client, converter, _store, _output_dir, _temp_dir = build_client(tmp_path)

    bad_suffix = client.post(
        "/api/gif/create",
        data={"duration": "3"},
        files={"file": ("clip.txt", b"x", "text/plain")},
    )
    assert bad_suffix.status_code == 400

    bad_duration = client.post(
        "/api/gif/create",
        data={"duration": "6"},
        files={"file": ("clip.mp4", b"x", "video/mp4")},
    )
    assert bad_duration.status_code == 400

    converter.probe = lambda _path: {"duration": 3.2, "width": 640, "height": 360}
    overflow = client.post(
        "/api/gif/create",
        data={"start_time": "2", "duration": "3"},
        files={"file": ("clip.mp4", b"x", "video/mp4")},
    )
    assert overflow.status_code == 400
