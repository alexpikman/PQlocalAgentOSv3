import json, os, tempfile, unittest
from pathlib import Path
import server

class StorageTests(unittest.TestCase):
    def test_default_settings_have_header_and_appearance(self):
        self.assertIn('appearance', server.DEFAULT_SETTINGS)
        self.assertIn('header', server.DEFAULT_SETTINGS)
    def test_default_pages_include_core_sections(self):
        ids={p['id'] for p in server.DEFAULT_PAGES}
        self.assertTrue({'dashboard','interface-settings','pages','github','system-log','menu-builder','modules'}.issubset(ids))
    def test_header_spacing_defaults_exist(self):
        self.assertEqual(server.DEFAULT_SETTINGS['header']['paddingTop'], 24)
        self.assertEqual(server.DEFAULT_SETTINGS['header']['paddingRight'], 22)
        self.assertEqual(server.DEFAULT_SETTINGS['header']['paddingBottom'], 24)
    def test_module_contract_schema_is_tracked(self):
        self.assertTrue((server.ROOT / 'module-contract.schema.json').exists())
    def test_module_directory_is_defined(self):
        self.assertEqual(server.MODULES, server.ROOT / 'modules')
    def test_slug_is_safe(self):
        import re
        slug=re.sub(r'[^a-z0-9-]+','-','my page / hello').strip('-')
        self.assertEqual(slug,'my-page-hello')

if __name__=='__main__': unittest.main()
