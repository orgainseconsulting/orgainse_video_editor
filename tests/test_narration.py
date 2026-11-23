import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from core import load
from speech import narration_status, proofread_shots, tts
from studio import validate


class BritishNarrationTests(unittest.TestCase):
    def test_new_and_explicit_voice_settings(self):
        request = validate({"script": "Meet ORQYNE."})
        self.assertEqual((request["voice"], request["scriptStyle"]), ("bf_emma", "oxford"))
        exact = validate(dict(request, voice="bm_george", scriptStyle="verbatim"))
        self.assertEqual((exact["voice"], exact["scriptStyle"]), ("bm_george", "verbatim"))
        with self.assertRaises(ValueError):
            validate(dict(request, voice="unknown"))

    def test_brand_name_uses_approved_british_phonemes(self):
        from narration.synthesise import spoken_input
        from unittest.mock import Mock
        tokenizer = Mock()
        tokenizer.phonemize.return_value = "miːt"
        self.assertEqual(spoken_input("Meet ORQYNE.", tokenizer), ("miːt ˈɔːkaɪn.", True))
        tokenizer.phonemize.assert_called_once_with("Meet", lang="en-gb")
        self.assertEqual(spoken_input("ORQYNE’s", tokenizer), ("ˈɔːkaɪnz", True))
        self.assertEqual(spoken_input("In the workspace.", tokenizer), ("In the workspace.", False))

    def test_missing_neural_engine_reports_setup(self):
        with tempfile.TemporaryDirectory() as tmp, patch("speech.narration_status", return_value={"britishVoice": False}):
            with self.assertRaisesRegex(ValueError, "setup-narration"):
                tts([{"voice": "Meet ORQYNE."}], Path(tmp), "bf_emma")

    @unittest.skipUnless(narration_status()["proofreading"], "Local proofreading dependency is not installed")
    def test_local_grammar_oxford_spelling_and_protected_copy(self):
        shots = [dict(voice="She have a example of the the color chart. We organise the centre. ORQYNE will analyze it.",
                      headline="A center", subhead="See the colors."),
                 dict(voice="They call it “Color Center”. Visit https://color.example/organise. 📍 We organise here.")]
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            proofread_shots(shots, folder, 'Keep the title “A center”.', False)
            self.assertEqual(shots[0]["voice"], "She has an example of the colour chart. We organize the centre. ORQYNE will analyse it.")
            self.assertEqual(shots[0]["headline"], "A center")
            self.assertEqual(shots[0]["subhead"], "See the colours.")
            self.assertEqual(shots[1]["voice"], "They call it “Color Center”. Visit https://color.example/organise. 📍 We organize here.")
            self.assertTrue(load(folder / "copy-edits.json"))
