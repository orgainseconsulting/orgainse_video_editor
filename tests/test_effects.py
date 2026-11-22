import unittest

from core import ROOT
from edit_guides import GUIDE_FILES
from effects import CAPTIONS, CATALOG, EDITABLE, EFFECTS, GRAPHICS, caption_words, layers
from keep_edit import keep_list
from studio import validate


class EffectsTests(unittest.TestCase):
    def test_manifest_matches_pinned_sources_and_preview_files(self):
        from motion.catalogue import build
        self.assertEqual(CATALOG, build())
        self.assertEqual((len(GRAPHICS-EDITABLE),len(EDITABLE),len(EFFECTS),len(CAPTIONS)),(150,3,51,7))
        for row in CATALOG:
            preview = ROOT/"web/previews"/(row["id"]+".webp")
            self.assertGreater(preview.stat().st_size,200)
        self.assertTrue(all(f.is_file() for f in GUIDE_FILES.values()))

    def test_effect_windows_and_types(self):
        self.assertEqual(layers([{"id":"orbit","from":0.25,"to":1}],2)[0]["to"],1)
        for invalid in [{"id":"invalid"},{"id":"orbit","from":3},{"id":"orbit","to":float("nan")},
                        {"id":"orbit","from":1,"to":1},{"id":"orbit","look":"bento"},
                        {"id":"orbit","cards":["../../photo.jpg"]}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                layers([invalid],2)
        self.assertEqual(layers([{"id":"cover-star","look":"editorial"}])[0]["look"],"editorial")

    def test_storyboard_and_project_layers_round_trip(self):
        req = validate(dict(effects=[{"id":"moody"}],scenes=[dict(visual="graphic",graphic="StudioTypeReveal",
            seconds=2,subhead="Product launch",effects=[{"id":"tape-label","text":"Hello"}])]))
        self.assertEqual(validate(req),req)
        with self.assertRaises(ValueError):
            validate(dict(brief="test",effects=[{"id":"moody","from":1}]))

    def test_keep_ranges_and_caption_word_timing(self):
        self.assertEqual(keep_list([[0,1],[2,3]]),[[0,1],[2,3]])
        for invalid in ([[2,3],[1,2]],[[0,0]],[[0,float("inf")]]):
            with self.assertRaises(ValueError):
                keep_list(invalid)
        words=caption_words([(0,.2,"One"),(.4,1,"word"),(1.2,1.8,"at once.")])
        self.assertEqual([(w["s"],w["e"]) for w in words[:2]],[(0,.2),(.4,1)])
        self.assertFalse(words[0]["br"])
        self.assertTrue(words[-1]["br"])
