import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_ui_prepare', HERE / 'prepare.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
compiler_spec = importlib.util.spec_from_file_location('native_ui_compiler_policy', HERE / 'compiler_policy.py')
compiler_policy = importlib.util.module_from_spec(compiler_spec)
compiler_spec.loader.exec_module(compiler_policy)
candidate_spec = importlib.util.spec_from_file_location('native_ui_candidate', HERE / 'apply_candidate.py')
candidate = importlib.util.module_from_spec(candidate_spec)
candidate_spec.loader.exec_module(candidate)


class PreparationTests(unittest.TestCase):
    def manifest(self):
        return json.loads((HERE / 'manifest.json').read_text())

    def test_reviewed_manifest_and_proof_match(self):
        manifest = self.manifest()
        prepare.validate_manifest(manifest)
        self.assertEqual(prepare.source_list_sha256(HERE / 'upstream-files.json'), manifest['upstream']['files_manifest_sha256'])
        proof = json.loads((HERE / 'upstream-files.json').read_text())
        self.assertEqual(proof['commit'], manifest['upstream']['commit'])
        self.assertEqual(len(proof['files']), 109)

    def test_source_list_identity_survives_git_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'proof.json'
            path.write_bytes(b'{\n  "files": {}\n}\n')
            expected = prepare.source_list_sha256(path)
            path.write_bytes(b'{\r\n  "files": {}\r\n}\r\n')
            self.assertEqual(prepare.source_list_sha256(path), expected)

    def test_floating_unreviewed_and_unresolved_inputs_rejected(self):
        changes = [('upstream', 'commit', 'main'), ('upstream', 'archive_url', 'https://example.com/source.zip'),
                   ('vcpkg', 'tool_sha256', None), ('vcpkg', 'tool_url', 'https://example.com/tool.exe'),
                   ('vcpkg', 'triplet', 'x86-windows')]
        for section, key, value in changes:
            manifest = self.manifest()
            manifest[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                prepare.validate_manifest(manifest)
        manifest = self.manifest()
        manifest['reviewed_patches'] = ['unreviewed.patch']
        with self.assertRaises(ValueError):
            prepare.validate_manifest(manifest)

    def test_download_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'tool.exe'
            with patch.object(prepare.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
                with self.assertRaises(ValueError):
                    prepare.download('https://example.com', target, '0' * 64)

    def make_zip(self, root, entries):
        archive = root / 'source.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            for name, data in entries:
                output.writestr(name, data)
        return archive

    def test_safe_archive_extracts_inside_expected_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self.make_zip(root, [('expected/', ''), ('expected/src/a.cpp', 'hello')])
            prepare.extract(archive, root / 'out', 'expected')
            self.assertEqual((root / 'out/src/a.cpp').read_text(), 'hello')

    def test_archive_traversal_links_and_case_collisions_rejected_before_write(self):
        link = zipfile.ZipInfo('expected/link')
        link.external_attr = 0o120777 << 16
        for entries in [ [('expected/../escape', 'x')], [('other/a', 'x')],
                         [('expected/C:escape', 'x')], [('expected\\..\\escape', 'x')],
                         [('expected/a', 'x'), ('expected/A', 'y')], [(link, 'target')] ]:
            with self.subTest(entries=str(entries)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = self.make_zip(root, entries)
                with self.assertRaises(ValueError):
                    prepare.extract(archive, root / 'out', 'expected')
                self.assertFalse((root / 'out').exists())

    def test_source_mutation_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'a.cpp').write_bytes(b'original')
            expected = hashlib.sha1(b'blob 8\0original').hexdigest()
            proof = {'files': {'a.cpp': expected}}
            self.assertEqual(len(prepare.verify_source(root, proof)), 1)
            (root / 'a.cpp').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                prepare.verify_source(root, proof)

    def test_dependency_repair_original_single_matches_and_result_required(self):
        original = b'url=old-url\nhash=old-hash\n'
        result = b'url=new-url\nhash=new-hash\n'
        repair = {'original_sha256': hashlib.sha256(original).hexdigest(),
                  'result_sha256': hashlib.sha256(result).hexdigest(),
                  'replacements': [{'old': 'old-url', 'new': 'new-url'}, {'old': 'old-hash', 'new': 'new-hash'}]}
        self.assertEqual(prepare.repair_bytes(original, repair), result)
        with self.assertRaises(ValueError):
            prepare.repair_bytes(original + b'mutated', repair)
        with self.assertRaises(ValueError):
            prepare.repair_bytes(original, {**repair, 'result_sha256': '0' * 64})
        for data in [b'old-url old-url old-hash', b'missing-url old-hash']:
            with self.subTest(data=data), self.assertRaises(ValueError):
                prepare.repair_bytes(data, {**repair, 'original_sha256': hashlib.sha256(data).hexdigest()})

    def test_dependency_repair_is_not_an_arbitrary_file_patch(self):
        manifest = self.manifest()
        manifest['dependency_helper_repairs'][0]['path'] = '../../upstream/src/main.cpp'
        with self.assertRaises(ValueError):
            prepare.validate_manifest(manifest)
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            prepare.apply_dependency_repairs(Path(directory), manifest['dependency_helper_repairs'])

    def test_dependency_repairs_cannot_be_missing_duplicated_or_expanded(self):
        for change in ['missing', 'duplicate', 'extra_literal']:
            manifest = self.manifest()
            repairs = manifest['dependency_helper_repairs']
            if change == 'missing':
                repairs.pop()
            elif change == 'duplicate':
                repairs[1] = repairs[0]
            else:
                repairs[1]['replacements'].append({'old': 'unreviewed', 'new': 'unreviewed'})
            with self.subTest(change=change), self.assertRaises(ValueError):
                prepare.validate_manifest(manifest)

    def test_registry_and_engine_are_separately_pinned(self):
        manifest = self.manifest()
        self.assertEqual(manifest['vcpkg']['registry_tool_release'], '2023-10-18')
        self.assertEqual(manifest['vcpkg']['tool_release'], '2024-10-18')
        manifest['vcpkg']['registry_tool_release'] = '2024-10-18'
        with self.assertRaises(ValueError):
            prepare.validate_manifest(manifest)

    def test_generated_triplets_preserve_registry_and_select_exact_v143(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'upstream').mkdir()
            (root / 'vcpkg/triplets').mkdir(parents=True)
            for name in ['x64-windows-static', 'x64-windows']:
                (root / f'vcpkg/triplets/{name}.cmake').write_bytes(b'baseline-triplet')
            rows = compiler_policy.write_triplets(root, '14.44.35207')
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertIn('set(VCPKG_PLATFORM_TOOLSET "v143")', row['contents'])
                self.assertIn('set(VCPKG_PLATFORM_TOOLSET_VERSION "14.44.35207")', row['contents'])
                self.assertEqual((root / f"vcpkg/triplets/{row['triplet']}.cmake").read_bytes(), b'baseline-triplet')
            with self.assertRaises(ValueError):
                compiler_policy.write_triplets(root, '14.44.35207')

    def compiler_fixture(self, directory):
        root = Path(directory)
        compiler = root / 'VS/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/cl.exe'
        compiler.parent.mkdir(parents=True)
        compiler.write_bytes(b'fixture-not-executable')
        caches = []
        for triplet in ['x64-windows-static', 'x64-windows']:
            cache = root / f'vcpkg/buildtrees/detect_compiler/{triplet}-rel/CMakeCache.txt'
            cache.parent.mkdir(parents=True)
            cache.write_text(f'CMAKE_CXX_COMPILER:FILEPATH={compiler.as_posix()}\nVCPKG_PLATFORM_TOOLSET:UNINITIALIZED=v143\nVCPKG_PLATFORM_TOOLSET_VERSION:STRING=14.44.35207\n')
            caches.append(cache)
        return root, compiler, caches

    def test_effective_compiler_audit_accepts_exact_target_and_host(self):
        with tempfile.TemporaryDirectory() as directory:
            root, compiler, _ = self.compiler_fixture(directory)
            result = compiler_policy.audit(root, str(compiler), '14.44.35207')
            self.assertTrue(result['verified'])
            self.assertTrue(result['accepted'])
            self.assertEqual(len(result['observed_caches']), 2)

    def test_effective_compiler_audit_rejects_v142_fallback_or_missing_host(self):
        for mode in ['version', 'toolset', 'missing_host']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root, compiler, caches = self.compiler_fixture(directory)
                if mode == 'missing_host':
                    caches[1].unlink()
                elif mode == 'toolset':
                    caches[1].write_text(caches[1].read_text().replace('v143', 'v142'))
                else:
                    caches[0].write_text(caches[0].read_text().replace('14.44.35207', '14.29.30133'))
                result = compiler_policy.audit(root, str(compiler), '14.44.35207')
                self.assertFalse(result['accepted'])
                self.assertFalse(result['verified'])

    def test_old_or_injected_toolset_version_is_rejected(self):
        for version in ['14.29.30133', 'latest', '14.44.35207\nset(UNREVIEWED ON)']:
            with self.subTest(version=version), self.assertRaises(ValueError):
                compiler_policy.version_checked(version)

    def test_candidate_sources_and_review_diff_match_manifest(self):
        manifest = json.loads((HERE / 'input-candidate/candidate.json').read_text())
        candidate.validate(manifest)
        self.assertEqual(manifest['default_mode'], 'native')
        self.assertFalse(manifest['qualified'])

    def test_candidate_rejects_unreviewed_scope_or_default(self):
        for change in ['path', 'default', 'qualified', 'template_hash']:
            manifest = json.loads((HERE / 'input-candidate/candidate.json').read_text())
            if change == 'path': manifest['edits'][0]['path'] = '../../game/NirnLabUIPlatform.dll'
            elif change == 'default': manifest['default_mode'] = 'win32-mouse'
            elif change == 'qualified': manifest['qualified'] = True
            else: manifest['additions'][0]['sha256'] = '0' * 64
            with self.subTest(change=change), self.assertRaises(ValueError):
                candidate.validate(manifest)

    def test_candidate_source_edits_fail_on_changed_base_or_duplicate_context(self):
        original, result = b'before', b'after'
        spec = {'original_sha256': candidate.digest(original), 'result_sha256': candidate.digest(result),
                'replacements': [{'old': 'before', 'new': 'after'}]}
        self.assertEqual(candidate.apply_edit(original, spec), result)
        with self.assertRaises(ValueError): candidate.apply_edit(b'changed', spec)
        with self.assertRaises(ValueError): candidate.apply_edit(original, {**spec, 'result_sha256': '0' * 64})
        duplicate = b'before before'
        with self.assertRaises(ValueError):
            candidate.apply_edit(duplicate, {**spec, 'original_sha256': candidate.digest(duplicate)})

    def test_cached_focus_fix_is_bound_to_the_upstream_condition(self):
        manifest = json.loads((HERE / 'input-candidate/candidate.json').read_text())
        source = next(row for row in manifest['edits'] if row['path'].endswith('/DefaultBrowser.cpp'))
        focus = [row for row in source['replacements'] if row['old'].strip() == 'if (m_isFocused == a_value)']
        self.assertEqual(len(focus), 1)
        self.assertIn('ShouldApplyFocus(m_isFocused, a_value, m_isFocusedCached)', focus[0]['new'])

    def test_candidate_close_hook_detaches_without_browser_calls(self):
        manifest = json.loads((HERE / 'input-candidate/candidate.json').read_text())
        source = next(row for row in manifest['edits'] if row['path'].endswith('/DefaultBrowser.cpp'))
        close = [row for row in source['replacements'] if 'onBeforeBrowserClose.connect' in row['new']]
        self.assertEqual(len(close), 1)
        self.assertIn('[route = m_inputRoute](CefRefPtr<CefBrowser>) { route->Detach(); }', close[0]['new'])
        destructor = next(row for row in source['replacements'] if 'DefaultBrowser::~DefaultBrowser()' in row['old'])
        self.assertIn('m_inputRoute->Detach();', destructor['new'])
        route = (HERE / 'input-candidate/WhiterunMouseRoute.cpp').read_text()
        detach = route.split('void WhiterunMouseRoute::Detach()', 1)[1].split('void WhiterunMouseRoute::PollDrag()', 1)[0]
        self.assertIn('std::lock_guard lock(m_mutex)', detach)
        for required in ['m_browser = nullptr;', 'm_render = nullptr;', 'm_buttons.ReleaseAll();', 'compare_exchange_strong']:
            self.assertIn(required, detach)
        self.assertNotIn('GetHost()', detach)
        self.assertNotIn('ReleaseAll();', detach.replace('m_buttons.ReleaseAll();', ''))

    def test_candidate_does_not_change_hwnd_capture_and_polls_only_mouse(self):
        route = (HERE / 'input-candidate/WhiterunMouseRoute.cpp').read_text()
        for forbidden in ['SetCapture(', 'ReleaseCapture(', 'PostMessage', 'GetAsyncKeyState(VK_SHIFT)', 'GetAsyncKeyState(VK_CONTROL)']:
            self.assertNotIn(forbidden, route)
        self.assertEqual(route.count('GetAsyncKeyState('), 3)
        poll = route.split('void WhiterunMouseRoute::PollDrag()', 1)[1].split('void WhiterunMouseRoute::SetFocused', 1)[0]
        self.assertIn('if (!Active() || !m_buttons.held) return;', poll)
        self.assertIn('MissingReleases(m_buttons.held, LogicalButtons(physical, GetSystemMetrics(SM_SWAPBUTTON) != 0))', poll)
        self.assertIn('!m_buttons.Up(bit)', poll)

    def test_candidate_new_browser_defers_requested_focus_until_its_page_loads(self):
        manifest = json.loads((HERE / 'input-candidate/candidate.json').read_text())
        source = next(row for row in manifest['edits'] if row['path'].endswith('/DefaultBrowser.cpp'))
        created = next(row['new'] for row in source['replacements'] if 'm_onAfterBrowserCreated_Connection =' in row['old'])
        self.assertIn('CacheFocusOnAttach(m_isFocused, m_isFocusedCached)', created)
        self.assertLess(created.index('std::lock_guard locker(m_urlMutex)'), created.index('m_inputRoute->Attach'))
        self.assertLess(created.index('LoadBrowserURL('), created.index('m_isPageLoaded = false;'))

    def test_candidate_native_mouse_suppression_includes_focused_non_owner(self):
        route = (HERE / 'input-candidate/WhiterunMouseRoute.cpp').read_text()
        suppression = route.split('bool WhiterunMouseRoute::SuppressNativeMouse()', 1)[1].split('std::optional<Point>', 1)[0]
        self.assertIn('m_window && m_browser && m_render', suppression)
        self.assertIn('s_owner.load() != nullptr', suppression)
        self.assertNotIn('s_owner.load() == this', suppression)
        self.assertIn('RouteActive(m_mode, m_focused, m_visible, GetForegroundWindow() == m_window', suppression)


if __name__ == '__main__':
    unittest.main()
