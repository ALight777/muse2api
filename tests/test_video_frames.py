"""Offline API regressions. Run: python tests/test_video_frames.py (no account/browser)."""
import asyncio
import base64
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_async_images import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
home = tempfile.TemporaryDirectory(prefix="muse-video-frames-")
os.environ.update(MUSE2API_HOME=home.name, MUSE2API_PROFILE_ROOT=home.name,
                  MUSE2API_KEY="test-only", MUSE2API_PUBLIC_BASE="",
                  MUSE2API_REF_IMAGE_LOCAL_FILES="0",
                  MUSE2API_REF_IMAGE_PRIVATE_FETCH="0")
import app


def data_url(mime, data):
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


FIRST = data_url("image/png", b"\x89PNG\r\n\x1a\nfirst-fixture")
LAST = data_url("image/png", b"\x89PNG\r\n\x1a\nlast-fixture")


class FrameApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = Client(app.app, {"authorization": "Bearer test-only"})
        self.calls = []

        def generate(prompt, kind, timeout, **kwargs):
            self.calls.append((prompt, kwargs["reference_images"]))
            return {"filename": "test.mp4", "size": 16, "kind": "video"}, "test-account"

        self.generation = patch.object(app, "_run_generation", generate)
        self.generation.start()

    async def asyncTearDown(self):
        self.generation.stop()

    async def submit(self, **kwargs):
        return await self.client.post("/v1/videos", json={"prompt": "move smoothly", **kwargs})

    async def completed(self, payload):
        response = await self.submit(**payload)
        self.assertEqual(response.status_code, 200, response.json())
        task_id = response.json()["id"]
        for _ in range(100):
            task = (await self.client.get("/v1/videos/" + task_id)).json()
            if task["status"] == "completed":
                return response.json(), task
            await asyncio.sleep(.01)
        self.fail("fixture worker did not complete")

    async def test_order_roles_and_honest_task_metadata(self):
        response, task = await self.completed({"first_frame": FIRST, "last_frame": {"url": LAST}})
        prompt, refs = self.calls[0]
        self.assertEqual(refs, [FIRST, LAST])
        self.assertIn("[图1] 是视频的首帧", prompt)
        self.assertIn("[图2] 是视频的尾帧", prompt)
        self.assertNotIn("其余图片作为主体、场景与风格参考", prompt)
        self.assertEqual(response["frame_control"], task["frame_control"])
        self.assertEqual(task["frame_control"], {"method": "prompt", "first_frame": True,
                                               "last_frame": True, "exact_match_guaranteed": False})
        self.assertNotIn("base64", task["api_prompt"])

    async def test_reverse_order(self):
        await self.completed({"first_frame": LAST, "last_frame": FIRST})
        self.assertEqual(self.calls[0][1], [LAST, FIRST])

    async def test_last_only_does_not_become_first(self):
        _, task = await self.completed({"last_frame": LAST})
        prompt, refs = self.calls[0]
        self.assertEqual(refs, [LAST])
        self.assertIn("[图1] 是视频的尾帧", prompt)
        self.assertNotIn("是视频的首帧", prompt)
        self.assertFalse(task["frame_control"]["first_frame"])

    async def test_first_only(self):
        await self.completed({"first_frame": {"image_url": {"url": FIRST}}})
        self.assertEqual(self.calls[0][1], [FIRST])
        self.assertIn("[图1] 是视频的首帧", self.calls[0][0])
        self.assertNotIn("是视频的尾帧", self.calls[0][0])

    async def test_legacy_requests_keep_existing_behavior(self):
        for fields, expected, text in [
            ({}, [], "全新文生视频"),
            ({"image": FIRST}, [FIRST], "第一帧参考图"),
            ({"images": [FIRST, LAST]}, [FIRST, LAST], "其余图片作为主体、场景与风格参考"),
        ]:
            with self.subTest(fields=list(fields)):
                response, task = await self.completed(fields)
                self.assertEqual(self.calls[-1][1], expected)
                self.assertIn(text, self.calls[-1][0])
                self.assertNotIn("frame_control", response)
                self.assertNotIn("frame_control", task)

    async def test_conflicting_reference_fields_fail_before_queueing(self):
        before = len(app.store.tasks)
        for key, value in [("image", FIRST), ("image_url", FIRST), ("reference_image", FIRST),
                           ("images", [FIRST]), ("videos", [FIRST]),
                           ("audios", [FIRST]), ("files", [FIRST])]:
            with self.subTest(key=key):
                response = await self.submit(first_frame=FIRST, last_frame=LAST, **{key: value})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(len(app.store.tasks), before)
        self.assertFalse(self.calls)

    async def test_invalid_references_fail_before_queueing(self):
        before = len(app.store.tasks)
        for name in ("first_frame", "last_frame"):
            for value in ("", "  ", {}, [], 123, {"url": ""}):
                with self.subTest(name=name, value=value):
                    response = await self.submit(**{name: value})
                    self.assertEqual(response.status_code, 400)
        self.assertEqual(len(app.store.tasks), before)

    async def test_non_images_rejected_even_if_declared_as_images(self):
        before = len(app.store.tasks)
        for name in ("first_frame", "last_frame"):
            for mime in ("application/pdf", "image/png"):
                with self.subTest(name=name, mime=mime):
                    response = await self.submit(**{name: data_url(mime, b"%PDF-1.4\nfixture")})
                    self.assertEqual(response.status_code, 400)
        self.assertEqual(len(app.store.tasks), before)
        self.assertFalse(self.calls)

    async def test_local_file_safety_is_not_bypassed(self):
        response = await self.submit(last_frame=str(ROOT / "app.py"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.calls)

    async def test_openapi_describes_experimental_fields(self):
        schema = (await self.client.get("/openapi.json")).json()
        fields = schema["components"]["schemas"]["VideoRequest"]["properties"]
        self.assertIn("not a native", fields["first_frame"]["description"])
        self.assertIn("not guaranteed", fields["last_frame"]["description"])


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        home.cleanup()
