import tempfile
import unittest
from pathlib import Path

from agent_tools import effective_tools, execute_tool

class AgentToolPermissionTests(unittest.TestCase):
    def test_local_file_tools_require_both_global_and_agent_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            target=root/'note.txt'
            target.write_text('private note',encoding='utf-8')
            agent={'id':'reader','permissions':{'file_loading':True,'file_saving':False}}
            config={'local_files':False,'roots':[str(root)]}
            self.assertEqual(effective_tools(agent,config),[])
            config['local_files']=True
            result=execute_tool('read_file',{'path':str(target)},agent,config)
            self.assertEqual(result['content'],'private note')
            denied=execute_tool('write_file',{'path':str(root/'new.txt'),'content':'no'},agent,config)
            self.assertIn('error',denied)

    def test_file_tools_cannot_escape_allowlisted_root(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root=Path(tmp); external=Path(outside)/'secret.txt'
            external.write_text('secret',encoding='utf-8')
            agent={'id':'reader','permissions':{'file_loading':True}}
            config={'local_files':True,'roots':[str(root)]}
            result=execute_tool('read_file',{'path':str(external)},agent,config)
            self.assertIn('error',result)
            self.assertNotIn('secret',str(result))

    def test_move_file_requires_explicit_permission_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'a.txt'; target=root/'b.txt'
            source.write_text('a',encoding='utf-8'); target.write_text('b',encoding='utf-8')
            config={'local_files':True,'roots':[str(root)]}
            denied=execute_tool('move_file',{'source':str(source),'destination':str(root/'c.txt')},{'permissions':{}},config)
            self.assertIn('error',denied)
            allowed=execute_tool('move_file',{'source':str(source),'destination':str(target)},{'permissions':{'file_moving':True}},config)
            self.assertIn('error',allowed)
            self.assertEqual(target.read_text(encoding='utf-8'),'b')
            moved=execute_tool('move_file',{'source':str(source),'destination':str(root/'c.txt')},{'permissions':{'file_moving':True}},config)
            self.assertIn('message',moved)
            self.assertFalse(source.exists())

    def test_shell_and_process_execution_are_not_exposed(self):
        names={item['function']['name'] for item in __import__('agent_tools').TOOL_DEFINITIONS}
        self.assertFalse({'powershell','ssh','shell','run_command','execute_python'} & names)

if __name__=='__main__':
    unittest.main()
