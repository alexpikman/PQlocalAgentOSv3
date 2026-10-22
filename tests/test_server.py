import json, os, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
import server

class StorageTests(unittest.TestCase):
    def test_default_settings_have_header_and_appearance(self):
        self.assertIn('appearance', server.DEFAULT_SETTINGS)
        self.assertIn('header', server.DEFAULT_SETTINGS)
    def test_default_pages_include_core_sections(self):
        ids={p['id'] for p in server.DEFAULT_PAGES}
        self.assertTrue({'dashboard','interface-settings','pages','github','system-log','menu-builder','modules','diagnostics','models','agents','projects','tasks'}.issubset(ids))
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


class ModuleRuntimeTests(unittest.TestCase):
    def test_graph_executes_builtin_transform_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            modules=[
                {'id':'source','name':'Источник','manifest':{'runtime':{'kind':'input'}}},
                {'id':'upper','name':'В верхний регистр','manifest':{'runtime':{'kind':'transform','operation':'uppercase'}}},
                {'id':'finish','name':'Выход','manifest':{'runtime':{'kind':'output'}}}
            ]
            registry={'modules':modules,'connections':[{'from':'source','to':'upper','label':'text'},{'from':'upper','to':'finish','label':'text'}]}
            with patch.object(server,'DATA',root), patch.object(server,'MODULES',root/'modules'):
                (root/'modules').mkdir()
                server.write_json(root/'modules.json',registry)
                result=server.execute_module_graph({'start_id':'source','input':'hello pqlocal'})
            self.assertTrue(result['ok'])
            self.assertEqual(result['executed'],3)
            self.assertEqual(result['result'],'HELLO PQLOCAL')
            self.assertEqual(result['order'],['source','upper','finish'])

    def test_graph_rejects_unconfigured_external_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            registry={'modules':[{'id':'external','name':'Внешний','manifest':{'api_version':'1.0'}}],'connections':[]}
            with patch.object(server,'DATA',root), patch.object(server,'MODULES',root/'modules'):
                server.write_json(root/'modules.json',registry)
                with self.assertRaisesRegex(ValueError,'не имеет разрешённого встроенного типа'):
                    server.execute_module_graph({'start_id':'external','input':'test'})

if __name__=='__main__': unittest.main()

