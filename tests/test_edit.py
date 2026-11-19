import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from figma_source import frame_ref
from planner import make_plan
from render import dimensions
from speech import captions, choose_shorts, clipped, read_cues, srt
from studio import validate


class EditTests(unittest.TestCase):
    def test_independent_highlights_and_source_offsets(self):
        cues = [
            (3, 9, "Pricing makes sense."),
            (14, 21, "Pricing makes sense."),
            (904, 912, "Track the camera carefully."),
            (1701, 1709, "Customers can export reports."),
        ]
        selected = choose_shorts(cues, 1800, 8, 5, "pricing camera reports")
        self.assertEqual(len(selected), 3)
        self.assertEqual([x["start"] for x in selected[1:]], [904, 1701])
        self.assertEqual(clipped(cues, 905, 911), [(0, 6, "Track the camera carefully.")])

    def test_sidecar_roundtrip_and_clip_bounds(self):
        entries = [(0.12, 4.85, "Keep the beginning and the end of this sentence.")]
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "sample.srt"
            chunks = captions(entries)
            file.write_text(srt(chunks), encoding="utf-8")
            parsed = read_cues(file)
            self.assertAlmostEqual(parsed[0][0], 0.12, places=3)
            self.assertAlmostEqual(parsed[-1][1], 4.85, places=3)
            self.assertEqual(" ".join(x[2] for x in parsed), entries[0][2])

    def test_script_template_respects_paragraphs(self):
        req = validate({"title": "Test", "script": "First idea.\nSecond idea.", "planner": "template"})
        shots = make_plan(req, ["title"], 0, None)
        self.assertEqual([s["voice"] for s in shots], ["First idea.", "Second idea."])

    def test_brief_is_not_used_as_template_screen_copy(self):
        req = validate(
            {"title": "Product demo", "brief": "Don't show the edit instructions.", "planner": "template"}
        )
        self.assertEqual(make_plan(req, ["title"], 0, None)[0]["headline"], "Product demo")

    def test_local_failure_has_no_cloud_fallback(self):
        req = validate({"title": "Test", "brief": "Two scenes."})
        with patch("planner.planner_ready", return_value=False), patch("planner.ollama") as client:
            with self.assertRaisesRegex(ValueError, "unavailable"):
                make_plan(req, ["title"], 0, None)
            client.assert_not_called()

    def test_exact_title_copy_survives_a_repetitive_model_response(self):
        req = validate(
            {
                "title": "Demo",
                "brief": "Open with the words One recording. Finish on a title card reading Three stories.",
            }
        )
        shot = {"visual": "title", "headline": "Demo", "start": 0, "seconds": 2, "motion": "still"}
        message = {"message": {"content": json.dumps({"shots": [shot] * 4})}}
        with tempfile.TemporaryDirectory() as td, patch("planner.planner_ready", return_value=True), patch(
            "planner.ollama", return_value=message
        ):
            shots = make_plan(req, ["title"], 0, Path(td) / "planner.log")
        self.assertEqual([x["headline"] for x in shots], ["One recording", "Three stories"])

    def test_ratio_presets(self):
        self.assertEqual(dimensions("4:5", False), (1080, 1350))
        for ratio in ["16:9", "9:16", "4:5", "1:1"]:
            w, h = dimensions(ratio, True)
            self.assertEqual((w % 2, h % 2, max(w, h)), (0, 0, 640))

    def test_figma_frame_link_requires_selected_node(self):
        self.assertEqual(
            frame_ref("https://www.figma.com/design/ABC1/brand?node-id=12-34"), ("ABC1", "12:34")
        )
        with self.assertRaisesRegex(ValueError, "specific Figma frame"):
            frame_ref("https://www.figma.com/design/ABC1/brand")

    def test_unsaved_inputs_and_invalid_ranges_are_rejected(self):
        with self.assertRaises(ValueError):
            validate({"mode": "shorts", "media": "../../source.mp4"})
        with self.assertRaises(ValueError):
            validate({"brief": "hello", "trim": [0, float("nan")]})
