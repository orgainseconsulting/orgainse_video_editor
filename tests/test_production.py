import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from figma_source import local_fig_preview
from planner import make_plan
from site_sections import save_capture
from speech import read_cues, srt
from studio import validate
from timeline import cached_scene, formats, scenes


class ProductionTests(unittest.TestCase):
    def test_worker_can_reuse_hero_already_saved_by_section_capture(self):
        with tempfile.TemporaryDirectory() as d, patch("site_sections.DATA", Path(d)):
            root = Path(d)
            (root / "assets").mkdir()
            image = root / "website.png"
            image.write_bytes(b"captured image")
            asset = save_capture(image)
            self.assertEqual(save_capture(image), asset)
            self.assertEqual((root / "assets" / asset).read_bytes(), image.read_bytes())

    def test_format_fanout_is_ordered_and_unique(self):
        self.assertEqual(formats("9:16", ["16:9","9:16","1:1"]), ["9:16","16:9","1:1"])
        with self.assertRaises(ValueError):
            formats("9:16",["3:2"])

    def test_storyboard_rejects_unavailable_media_and_invalid_time(self):
        with self.assertRaises(ValueError):
            scenes([{"visual":"footage","seconds":2}], ["title"])
        with self.assertRaises(ValueError):
            scenes([{"visual":"title","seconds":float("inf")}], ["title"])
        r=validate({"scenes":[{"visual":"title","headline":"First cut","seconds":1}]})
        self.assertEqual(r["scenes"][0]["headline"],"First cut")

    def test_section_templates_and_vtt_cues(self):
        r=validate({"brief":"Product screens","planner":"template"})
        r["siteSections"]=[{"heading":"Plan projects","summary":"", "image":"a.png"},{"heading":"Review risks","summary":"","image":"b.png"}]
        self.assertEqual([s["image"] for s in make_plan(r,["website","title"],0,None)],["a.png","b.png"])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"captions.vtt"
            path.write_text(srt([(0,1.55,"One sentence.")],webvtt=True))
            self.assertTrue(path.read_text().startswith("WEBVTT\n\n"))
            self.assertEqual(read_cues(path),[(0,1.55,"One sentence.")])

    def test_fig_preview_is_a_bounded_named_member(self):
        with tempfile.TemporaryDirectory() as d:
            design=Path(d)/"sample.fig"
            with zipfile.ZipFile(design,"w") as z:
                z.writestr("canvas.fig",b"fig-kiwi")
            with self.assertRaisesRegex(ValueError,"preview"):
                local_fig_preview(design,Path(d)/"out.png")
            with zipfile.ZipFile(design,"a") as z:
                z.writestr("thumbnail.png",b"\x89PNG\r\n\x1a\nfixture")
            self.assertEqual(local_fig_preview(design,Path(d)/"out.png").read_bytes(),b"\x89PNG\r\n\x1a\nfixture")

    def test_unchanged_scene_reused_and_damaged_cache_rebuilt(self):
        with tempfile.TemporaryDirectory() as d,patch("timeline.DATA",Path(d)):
            root=Path(d);calls=[]
            def encode(where):
                calls.append(True);(where/"scene.mp4").write_bytes(b"verified")
                return {"brand":"test"}
            def verify(path):
                if path.read_bytes()!=b"verified":raise ValueError("Incomplete")
            for expected in [False,True]:
                self.assertEqual(cached_scene(root,"scene",["same"],encode,verify)[1],expected)
            next((root/"scene-cache").glob("*/clip.mp4")).write_bytes(b"partial")
            self.assertFalse(cached_scene(root,"scene",["same"],encode,verify)[1])
            self.assertFalse(cached_scene(root,"scene",["changed"],encode,verify)[1])
            self.assertEqual(len(calls),3)
