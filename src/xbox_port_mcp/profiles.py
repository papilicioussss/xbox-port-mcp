import json
from importlib.resources import files

def all_profiles() -> list[dict]:
    return [json.loads(p.read_text(encoding='utf-8')) for p in files('xbox_port_mcp').joinpath('profiles').iterdir() if p.name.endswith('.json')]

def profile(identifier: str) -> dict:
    for item in all_profiles():
        if item['id'] == identifier: return item
    raise ValueError('Unknown game profile; add and review a profile in the package first')

def matches(identity: dict | None) -> list[dict]:
    if not identity: return []
    return [{'id': p['id'], 'evidence': p['known_xbe_sha1'][identity['sha1']]}
            for p in all_profiles() if identity['title_id'] == p['title_id'] and identity['sha1'] in p['known_xbe_sha1']]

def require_match(item: dict, identity: dict) -> None:
    if identity['title_id'] != item['title_id'] or identity['sha1'] not in item['known_xbe_sha1']:
        raise ValueError('Unsupported XBE for this profile; no game-specific address patches will be applied')
