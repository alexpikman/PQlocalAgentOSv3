import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server

class AgentRuntimeTests(unittest.TestCase):
    def test_agent_loop_executes_only_granted_tools_and_returns_final_answer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            workspace=root/'workspace'; workspace.mkdir()
            (workspace/'brief.txt').write_text('Approved project brief',encoding='utf-8')
            data=root/'data'; data.mkdir()
            server.write_json(data/'permissions.json',{'local_files':True,'roots':[str(workspace)]})
            responses=[
                {'model':'test-model','message':{'role':'assistant','content':'','tool_calls':[{'function':{'name':'read_file','arguments':{'path':str(workspace/'brief.txt')}}}]}},
                {'model':'test-model','message':{'role':'assistant','content':'Прочитал brief.txt и подготовил ответ.'}}
            ]
            with patch.object(server,'DATA',data), patch.object(server,'ollama_request',side_effect=responses) as request:
                result=server.run_agent_task('test-model',{'title':'Прочитать brief','description':'Изучи краткое описание.'},{'id':'agent1','name':'Reader','role':'ANALYST','system_prompt':'Будь точен.','permissions':{'file_loading':True}},None)
            self.assertEqual(result['tool_calls'],1)
            self.assertIn('Прочитал brief.txt',result['response'])
            self.assertEqual(request.call_count,2)
            tool_payload=request.call_args_list[0].args[1]
            self.assertIn('read_file',{x['function']['name'] for x in tool_payload['tools']})
            final_messages=request.call_args_list[1].args[1]['messages']
            self.assertTrue(any(x.get('role')=='tool' and 'Approved project brief' in x.get('content','') for x in final_messages))

    def test_agent_loop_does_not_offer_file_tools_without_global_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); data=root/'data'; data.mkdir()
            server.write_json(data/'permissions.json',{'local_files':False,'roots':[str(root)]})
            with patch.object(server,'DATA',data), patch.object(server,'ollama_request',return_value={'model':'test','response':'plain answer'}) as request:
                result=server.run_agent_task('test',{'title':'Question','description':'Answer'},{'id':'agent1','role':'ANALYST','permissions':{'file_loading':True}},None)
            self.assertEqual(result['tool_calls'],0)
            self.assertEqual(request.call_count,1)
            self.assertEqual(request.call_args.args[0],'/api/generate')
            self.assertNotIn('tools',request.call_args.args[1])

if __name__=='__main__':
    unittest.main()
