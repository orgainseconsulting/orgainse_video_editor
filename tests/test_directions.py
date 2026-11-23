import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from edit_directions import apply_layers, caption_choice, caption_layout, plan_graphics, read_directions
from planner import make_plan
from studio import validate


class ScriptedEditingTests(unittest.TestCase):
    def setUp(self):
        self.shots = [
            dict(visual="footage", voice="Meet the team.", headline="Meet the team", seconds=3, outputStart=0),
            dict(visual="website", voice="Review risks in one workspace.", headline="Meet the team", seconds=4, outputStart=3),
        ]

    def test_absolute_window_and_caption_selection(self):
        directions = read_directions('Add the Tape label effect reading "Review. Next!" from 2.5 to 4 seconds. Use Retro Typer captions.')
        apply_layers(self.shots, directions)
        first, second = (s["effects"][0] for s in self.shots)
        self.assertEqual((first["from"], first["to"], second["from"], second["to"]), (2.5, 3, 0, 1))
        self.assertEqual(first["text"], "Review. Next!")
        self.assertEqual(caption_choice(directions, "boxed"), "retro-typer")
        self.assertEqual(caption_layout("Use small Retro Typer captions near the bottom."), {"size": .55, "y": 86})

    def test_order_scoping_and_quoted_labels(self):
        directions = read_directions('In scene 2 use the moody filter and the tape label effect reading "Orbit".')
        apply_layers(self.shots, directions)
        self.assertEqual(self.shots[0].get("effects", []), [])
        self.assertEqual([e["id"] for e in self.shots[1]["effects"]], ["moody", "tape-label"])
        self.assertEqual(self.shots[1]["effects"][-1]["text"], "Orbit")

    def test_scene_time_and_exclusions(self):
        directions = read_directions("Use moody filter throughout. In scene 2 skip the moody filter. In scene 2 add Tape label from 0.2 to 0.8 seconds.")
        apply_layers(self.shots, directions)
        self.assertEqual(self.shots[0]["effects"], [{"id": "moody"}])
        self.assertEqual(self.shots[1]["effects"], [{"id": "tape-label", "from": 0.2, "to": 0.8}])
        for brief in ("In scene 3 add the moody filter.", "Add Tape label from 8 to 9 seconds."):
            with self.assertRaises(ValueError):
                apply_layers(self.shots, read_directions(brief))

    def test_scene_graphic_copy_and_matching_screen(self):
        self.shots[0].update(visual="graphic", graphic="StudioProductFocus")
        pages = [dict(heading="Home", summary="", image="home.png"),
                 dict(heading="Review risks", summary="Workspace view", image="risks.png")]
        plan_graphics(self.shots, read_directions("Use Product focus in scene 2 with the review risks section."), True, "Demo", pages)
        self.assertNotIn("graphic", self.shots[0])
        self.assertEqual(self.shots[1]["graphic"], "StudioProductFocus")
        self.assertEqual(self.shots[1]["image"], "risks.png")
        self.assertEqual(self.shots[1]["headline"], "Review risks in one workspace.")

    def test_numbered_directions_can_divide_one_script_paragraph(self):
        request = validate(dict(script="See the work. Manage risks. Request a pilot.", brief="Use Brand close in scene 3.", planner="template"))
        shots = make_plan(request, ["title"], 0, None)
        self.assertEqual([s["voice"] for s in shots], ["See the work.", "Manage risks.", "Request a pilot."])
        self.assertFalse(validate(dict(script="Play this.", brief="Render without captions."))["captions"])

    def test_script_fallback_and_auto_export_formats(self):
        request = validate(dict(script="First line.\nSecond line.", brief="Export 9:16 and landscape."))
        self.assertEqual(request["ratio"], "9:16")
        self.assertEqual(request["ratios"], ["9:16", "16:9"])
        self.assertEqual(request["title"], "First line.")
        with tempfile.TemporaryDirectory() as td, patch("planner.planner_ready", return_value=False):
            log = Path(td)/"planner.log"
            shots = make_plan(request, ["footage", "title"], 8, log)
            self.assertEqual([s["voice"] for s in shots], ["First line.", "Second line."])
            self.assertEqual(json.loads(log.read_text())["planner"], "script template")
