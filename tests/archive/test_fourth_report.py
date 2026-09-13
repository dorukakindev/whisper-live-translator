"""Profil dosyasi korumasi; yalniz gecici ve sentetik veri kullanir."""
import os
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
import buyedektir as b


class ProfileProtectionTests(unittest.TestCase):
    def profile(self, path):
        obj = b.SpeakerDiarizer.__new__(b.SpeakerDiarizer)
        obj.profile_file = str(path)
        obj._profile_lock = threading.RLock()
        obj._profile_load_failed = False
        obj.speaker_names = {}
        obj.hf_token = None
        return obj

    def test_invalid_profiles_are_not_overwritten(self):
        for raw in ('{"names":', '[]', '{"names":[]}',
                    '{"names":{"1":42}}'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'profiles.json'
                path.write_text(raw, encoding='utf-8')
                obj = self.profile(path)
                obj.load_profiles()
                self.assertTrue(obj._profile_load_failed)
                obj.speaker_names['1'] = 'Test'
                obj.save_profiles()
                self.assertEqual(path.read_text(encoding='utf-8'), raw)
                self.assertEqual(len(list(Path(folder).iterdir())), 1)

    def test_read_denied_does_not_enable_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profiles.json'
            path.write_text('{"names":{"1":"Eski"}}', encoding='utf-8')
            obj = self.profile(path)
            with patch('builtins.open', side_effect=PermissionError):
                obj.load_profiles()
            obj.save_profiles()
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['names']['1'], 'Eski')

    def test_valid_reload_restores_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profiles.json'
            obj = self.profile(path)
            obj._profile_load_failed = True
            path.write_text('{"names":{"1":"Eski"},"hf_token":"fake"}', encoding='utf-8')
            obj.load_profiles()
            self.assertFalse(obj._profile_load_failed)
            self.assertIsNone(obj.hf_token)
            obj.speaker_names['1'] = 'Yeni'
            obj.save_profiles()
            self.assertEqual(
                json.loads(path.read_text(encoding='utf-8')),
                {'names': {'1': 'Yeni'}}
            )

    def test_legacy_token_field_is_removed_without_loading_value(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profiles.json'
            path.write_text('{"names":{"1":"Eski"},"hf_token":42}', encoding='utf-8')
            obj = self.profile(path)
            obj.load_profiles()
            self.assertFalse(obj._profile_load_failed)
            self.assertIsNone(obj.hf_token)
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'names': {'1': 'Eski'}})

    def test_new_profile_can_be_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profiles.json'
            obj = self.profile(path)
            obj.load_profiles()
            obj.save_profiles()
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['names'], {})


class TranslationSequenceTests(unittest.TestCase):
    def test_ptt_id_gaps_do_not_drop_live_translation(self):
        t = b.transcriber
        with patch.object(t, '_latest_translate_submit_id', 100), patch.object(t, '_latest_translate_sequence', 2), patch.object(t.translator, 'translate', return_value=None) as translate:
            t._translate_async(1, 'Test', {}, t._session_id, t._result_generation, 1)
            translate.assert_called_once()

    def test_real_live_backlog_is_skipped(self):
        t = b.transcriber
        with patch.object(t, '_latest_translate_sequence', 20), patch.object(t.translator, 'translate') as translate:
            t._translate_async(1, 'Test', {}, t._session_id, t._result_generation, 1)
            translate.assert_not_called()

    def test_slow_result_checks_sequence_again(self):
        t = b.transcriber
        def slow(*args, **kwargs):
            t._latest_translate_sequence = 20
            return 'Gec sonuc'
        entry = {'id': 1, 'text': 'Test'}
        with patch.object(t, '_latest_translate_sequence', 1), patch.object(t, 'transcriptions', [entry]), patch.object(t.translator, 'translate', side_effect=slow), patch.object(b.socketio, 'emit', Mock()) as emit:
            t._translate_async(1, 'Test', {}, t._session_id, t._result_generation, 1)
            self.assertNotIn('translation', entry)
            emit.assert_not_called()


class TextBoundaryTests(unittest.TestCase):
    def test_portuguese_hard_g_is_not_softened_in_same_pass(self):
        self.assertEqual(b._normalize_turkish_pronunciation('guerra guia', 'pt'), 'gerra gia')
        self.assertEqual(b._normalize_turkish_pronunciation('gelo girar', 'pt'), 'jelu jirar')

    def test_engine_tags_only_match_whole_output(self):
        for tag in ('<music>', '<silence>', '<nospeech>', '<|nospeech|>'):
            self.assertTrue(b.transcriber._is_likely_hallucination(' ' + tag.upper() + ' '))
            self.assertFalse(b.transcriber._is_likely_hallucination('The tag is ' + tag + ' in this file'))


if __name__ == '__main__':
    unittest.main()
