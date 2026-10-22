"""Permission-gated, bounded tools for the local PQlocalAgentOSv3 agent runtime.

No shell, PowerShell, SSH, process execution, or arbitrary Python execution is exposed.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

MAX_TEXT_BYTES = 1_000_000
MAX_SEARCH_FILES = 200
BLOCKED_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', '.idea'}
TEXT_EXTENSIONS = {'.txt','.md','.py','.js','.mjs','.cjs','.ts','.json','.yaml','.yml','.toml','.html','.css','.scss','.xml','.svg','.sql','.sh','.bat','.ps1','.go','.rs','.java','.c','.h','.cpp','.ini','.cfg','.log'}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {'type':'function','function':{'name':'list_files','description':'List files and folders within a user-authorized local root. Use an absolute path.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'read_file','description':'Read a UTF-8 text file up to 1 MB inside a user-authorized root.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'search_files','description':'Search text in bounded text files inside a user-authorized root.','parameters':{'type':'object','properties':{'path':{'type':'string'},'query':{'type':'string'}},'required':['path','query']}}},
    {'type':'function','function':{'name':'write_file','description':'Create or update a UTF-8 text file inside an authorized root. Content is limited to 1 MB.','parameters':{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content']}}},
    {'type':'function','function':{'name':'move_file','description':'Move or rename a file or folder within authorized roots. Destination must not exist.','parameters':{'type':'object','properties':{'source':{'type':'string'},'destination':{'type':'string'}},'required':['source','destination']}}},
    {'type':'function','function':{'name':'delete_file','description':'Delete one file. Requires explicit file_deletion permission.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'create_directory','description':'Create a directory within an authorized root.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'delete_directory','description':'Delete an empty directory within an authorized root.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'github_list_files','description':'List files in the configured GitHub repository. Path is repository-relative; use an empty string for root. Requires github_access.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'github_read_file','description':'Read a UTF-8 text file from the configured GitHub repository using a repository-relative path. Requires github_access.','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}},
    {'type':'function','function':{'name':'github_search_code','description':'Search code in the configured GitHub repository for a symbol or distinctive text. Requires github_access.','parameters':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}},
]

PERMISSION_FOR_TOOL = {
    'list_files':('file_loading',), 'read_file':('file_loading',),
    'search_files':('file_loading',), 'write_file':('file_saving',),
    'move_file':('file_moving',), 'delete_file':('file_deletion',),
    'create_directory':('directory_creation',), 'delete_directory':('directory_deletion',),
    'github_list_files':('github_access',), 'github_read_file':('github_access',),
    'github_search_code':('github_access',),
}

def effective_tools(agent: dict[str, Any], permission_config: dict[str, Any]) -> list[dict[str, Any]]:
    permissions = agent.get('permissions') if isinstance(agent.get('permissions'),dict) else {}
    global_files = bool(permission_config.get('local_files')) and bool(permission_config.get('roots'))
    allowed = []
    for item in TOOL_DEFINITIONS:
        name=item['function']['name']
        if name.startswith('github_'):
            if permissions.get('github_access') and os.environ.get('GITHUB_TOKEN'):
                allowed.append(item)
        elif global_files and permissions.get(PERMISSION_FOR_TOOL[name][0]):
            allowed.append(item)
    return allowed

def _reparse(path: Path) -> bool:
    try:
        if path.is_symlink(): return True
        if os.name == 'nt':
            import stat
            return bool(path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (OSError, AttributeError):
        return False
    return False

def _contains_reparse(path: Path) -> bool:
    absolute=Path(path).absolute()
    current=Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current=current/part
        if current.exists() and _reparse(current): return True
    return False

def resolve_authorized_path(raw: str, permission_config: dict[str, Any], *, must_exist: bool=False) -> Path:
    if not permission_config.get('local_files') or not permission_config.get('roots'):
        raise PermissionError('Глобальный доступ к файлам выключен или не заданы разрешённые папки.')
    candidate=Path(str(raw)).expanduser()
    if not candidate.is_absolute(): raise PermissionError('Используйте абсолютный путь внутри разрешённой папки.')
    if _contains_reparse(candidate): raise PermissionError('Символические ссылки и junction запрещены.')
    try: resolved=candidate.resolve(strict=must_exist)
    except (OSError, RuntimeError) as exc: raise ValueError('Путь не существует или недоступен.') from exc
    for raw_root in permission_config.get('roots',[]):
        try:
            root=Path(raw_root).resolve(strict=True)
            if not root.is_dir() or _contains_reparse(root): continue
            resolved.relative_to(root)
            return resolved
        except (ValueError,OSError,RuntimeError):
            continue
    raise PermissionError('Путь находится вне разрешённых папок.')

def _github_request(path: str) -> dict[str, Any]:
    token=os.environ.get('GITHUB_TOKEN')
    if not token: raise PermissionError('Для GitHub-инструментов задайте GITHUB_TOKEN.')
    repo=os.environ.get('GITHUB_REPOSITORY','alexpikman/PQlocalAgentOSv3')
    url='https://api.github.com'+path if path.startswith('/search/') else 'https://api.github.com/repos/'+repo+path
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'PQlocalAgentOSv3'})
    try:
        with urllib.request.urlopen(req,timeout=12) as response: return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        raise RuntimeError('GitHub API вернул HTTP '+str(exc.code)) from exc

def execute_tool(name: str, args: dict[str, Any], agent: dict[str, Any], permission_config: dict[str, Any]) -> dict[str, Any]:
    permissions=agent.get('permissions') if isinstance(agent.get('permissions'),dict) else {}
    required=PERMISSION_FOR_TOOL.get(name)
    if name=='move_file':
        if not (permissions.get('file_moving') or permissions.get('directory_moving')): return {'error':'У агента нет разрешения на перемещение файлов или папок.'}
        if Path(str(args.get('source',''))).is_dir(): required=('directory_moving',)
    if not required: return {'error':'Инструмент не поддерживается.'}
    if not all(permissions.get(key,False) for key in required): return {'error':'У агента нет необходимого разрешения: '+', '.join(required)}
    try:
        if name.startswith('github_'):
            if not os.environ.get('GITHUB_TOKEN'): return {'error':'GITHUB_TOKEN не задан.'}
            if name=='github_list_files':
                rel=str(args.get('path','')).strip().strip('/')
                if '..' in Path(rel).parts: return {'error':'Некорректный путь репозитория.'}
                result=_github_request('/contents'+('/'+urllib.parse.quote(rel,safe='/') if rel else ''))
                items=result if isinstance(result,list) else [result]
                return {'items':[{'name':x.get('name'),'path':x.get('path'),'type':x.get('type'),'size':x.get('size',0)} for x in items[:200]]}
            if name=='github_read_file':
                rel=str(args.get('path','')).strip()
                if not rel or rel.startswith('/') or '..' in Path(rel).parts: return {'error':'Некорректный путь репозитория.'}
                result=_github_request('/contents/'+urllib.parse.quote(rel,safe='/'))
                import base64
                raw=base64.b64decode(result.get('content',''))
                if len(raw)>MAX_TEXT_BYTES: return {'error':'Файл превышает лимит 1 МБ.'}
                return {'path':rel,'content':raw.decode('utf-8')}
            query=str(args.get('query','')).strip()[:200]
            if len(query)<2: return {'error':'Введите минимум 2 символа.'}
            repo=os.environ.get('GITHUB_REPOSITORY','alexpikman/PQlocalAgentOSv3')
            q=urllib.parse.quote(query+' repo:'+repo)
            result=_github_request('/search/code?q='+q+'&per_page=10')
            return {'items':[{'path':x.get('path'),'url':x.get('html_url')} for x in result.get('items',[])]}
        path=None if name=='move_file' else resolve_authorized_path(str(args.get('path','')),permission_config,must_exist=name in {'list_files','read_file','search_files','delete_file','delete_directory'})
        if name=='list_files':
            if not path.is_dir(): return {'error':'Указанный путь не является папкой.'}
            items=[]
            for child in sorted(path.iterdir(),key=lambda x:(not x.is_dir(),x.name.lower()))[:200]:
                if child.name in BLOCKED_DIRS or _reparse(child): continue
                items.append({'name':child.name,'path':str(child),'type':'directory' if child.is_dir() else 'file','size':child.stat().st_size if child.is_file() else None})
            return {'path':str(path),'items':items}
        if name=='read_file':
            if not path.is_file(): return {'error':'Файл не найден.'}
            if path.suffix.lower() not in TEXT_EXTENSIONS and path.suffix: return {'error':'Чтение этого типа файла не разрешено.'}
            raw=path.read_bytes()
            if len(raw)>MAX_TEXT_BYTES: return {'error':'Файл превышает лимит 1 МБ.'}
            return {'path':str(path),'content':raw.decode('utf-8')}
        if name=='search_files':
            query=str(args.get('query','')).strip()
            if not query: return {'error':'Укажите поисковую строку.'}
            if not path.is_dir(): return {'error':'Указанный путь не является папкой.'}
            results=[]; scanned=0
            for file in path.rglob('*'):
                if not file.is_file() or _contains_reparse(file) or file.suffix.lower() not in TEXT_EXTENSIONS or any(part in BLOCKED_DIRS for part in file.parts): continue
                try: resolve_authorized_path(str(file),permission_config,must_exist=True)
                except (PermissionError,ValueError): continue
                scanned+=1
                if scanned>MAX_SEARCH_FILES: break
                try:
                    if file.stat().st_size>200_000: continue
                    lines=file.read_text(encoding='utf-8').splitlines()
                except (OSError,UnicodeError): continue
                for number,line in enumerate(lines,1):
                    if query.casefold() in line.casefold():
                        results.append({'path':str(file),'line':number,'text':line[:400]})
                        if len(results)>=100: return {'results':results,'scanned_files':scanned}
            return {'results':results,'scanned_files':scanned}
        if name=='write_file':
            content=args.get('content','')
            if not isinstance(content,str) or len(content.encode('utf-8'))>MAX_TEXT_BYTES: return {'error':'Содержимое должно быть текстом до 1 МБ.'}
            if not path.parent.is_dir(): return {'error':'Родительская папка не существует; сначала создай её отдельным разрешённым инструментом.'}
            if path.exists() and not path.is_file(): return {'error':'Целевой путь не является файлом.'}
            path.write_text(content,encoding='utf-8')
            return {'path':str(path),'bytes':len(content.encode('utf-8')),'message':'Файл сохранён.'}
        if name=='move_file':
            src=resolve_authorized_path(str(args.get('source','')),permission_config,must_exist=True)
            dst=resolve_authorized_path(str(args.get('destination','')),permission_config,must_exist=False)
            if not src.exists(): return {'error':'Источник не найден.'}
            if dst.exists(): return {'error':'Назначение уже существует; перезапись запрещена.'}
            if not dst.parent.is_dir(): return {'error':'Папка назначения не существует.'}
            src.rename(dst)
            return {'source':str(src),'destination':str(dst),'message':'Перемещение выполнено.'}
        if name=='delete_file':
            if not path.is_file(): return {'error':'Целевой файл не найден.'}
            path.unlink()
            return {'path':str(path),'message':'Файл удалён.'}
        if name=='create_directory':
            path.mkdir(parents=False,exist_ok=False)
            return {'path':str(path),'message':'Папка создана.'}
        if name=='delete_directory':
            if not path.is_dir(): return {'error':'Целевая папка не найдена.'}
            path.rmdir()
            return {'path':str(path),'message':'Пустая папка удалена.'}
        return {'error':'Инструмент не поддерживается.'}
    except PermissionError as exc: return {'error':str(exc)}
    except (ValueError,OSError,UnicodeError,RuntimeError) as exc: return {'error':str(exc)[:300]}
