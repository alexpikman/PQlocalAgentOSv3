import json
from pathlib import Path

DATA = Path('C:/PROJECT/PQlocalAgentOSv3/data')
providers = json.loads((DATA/'providers.json').read_text())

print(f"Количество провайдеров: {len(providers)}")
print()

for p in providers:
    print(f"ID: {p.get('id')}")
    print(f"Kind: {p.get('kind')}")
    print(f"Format: {p.get('format')}")
    base_url = p.get('base_url', 'НЕТ')[:60] if isinstance(p.get('base_url'), str) else 'НЕ СТРИНГ'
    print(f"Base URL: {base_url}")
    print("-" * 60)
