#!/usr/bin/env python3
"""Minimal ComfyUI HTTP client (standard library only).

Why not the comfyui python package: the skill only needs submit / poll / download /
inspect, all of which are plain JSON over HTTP. Keeping this dependency-free means the
workspace venv never has to import torch (the RTX 5090 needs the ComfyUI embedded Python).

Usage as a library:
  from comfy_client import ComfyClient, load_workflow, collect_files
  c = ComfyClient()                              # http://127.0.0.1:8188 or $COMFY_URL
  pid = c.submit(load_workflow('workflows/smoke_empty_image.json'))
  entry = c.wait(pid)
  for f in collect_files(entry): print(f['filename'])

CLI (handy for exploring a running server):
  python comfy_client.py stats
  python comfy_client.py models diffusion_models
  python comfy_client.py nodes Hunyuan
  python comfy_client.py queue
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

DEFAULT_URL = os.environ.get('COMFY_URL', 'http://127.0.0.1:8188')
MEDIA_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.mp4', '.webm', '.mov',
             '.mp3', '.wav', '.flac', '.ogg', '.glb', '.gltf', '.obj', '.fbx', '.ply', '.splat')
MODEL_EXT = ('.safetensors', '.ckpt', '.pt', '.pth', '.bin', '.gguf', '.sft')


class ComfyError(RuntimeError):
    """Raised when the server rejects a prompt or a job ends in error."""


class ComfyClient:
    def __init__(self, url=None, client_id=None, timeout=30.0):
        self.url = (url or DEFAULT_URL).rstrip('/')
        self.client_id = client_id or uuid.uuid4().hex
        self.timeout = timeout

    # ---------- low level ----------
    def _request(self, path, data=None, method=None, raw=False):
        url = self.url + path
        body = None
        headers = {}
        if data is not None:
            body = json.dumps(data).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                payload = r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', 'replace')[:2000]
            raise ComfyError(f'{method or "GET"} {path} -> HTTP {e.code}: {detail}') from None
        except urllib.error.URLError as e:
            raise ComfyError(f'cannot reach ComfyUI at {self.url} ({e.reason}). Is it running?') from None
        if raw:
            return payload
        return json.loads(payload.decode('utf-8'))

    def get(self, path):
        return self._request(path)

    def post(self, path, data):
        return self._request(path, data=data, method='POST')

    # ---------- server introspection ----------
    def system_stats(self):
        return self.get('/system_stats')

    def queue(self):
        return self.get('/queue')

    def model_folders(self):
        return self.get('/models')

    def models(self, folder):
        return self.get(f'/models/{urllib.parse.quote(folder)}')

    def object_info(self, cls=None):
        if cls:
            return self.get('/object_info/' + urllib.parse.quote(cls))
        return self.get('/object_info')

    def node_classes(self):
        return sorted(self.object_info().keys())

    # ---------- jobs ----------
    def submit(self, workflow, extra_data=None):
        """Queue an API-format workflow; returns the prompt_id."""
        if not isinstance(workflow, dict) or not workflow:
            raise ComfyError('workflow must be a non-empty API-format dict')
        resp = self.post('/prompt', {'prompt': workflow, 'client_id': self.client_id,
                                     'extra_data': extra_data or {}})
        if resp.get('node_errors'):
            raise ComfyError('node errors: ' + json.dumps(resp['node_errors'])[:2000])
        if 'prompt_id' not in resp:
            raise ComfyError('unexpected /prompt response: ' + json.dumps(resp)[:2000])
        return resp['prompt_id']

    def history(self, prompt_id):
        return self.get(f'/history/{urllib.parse.quote(prompt_id)}')

    def wait(self, prompt_id, timeout=1800.0, poll=1.0, on_poll=None):
        """Block until the job finishes; returns its history entry (outputs + status)."""
        t0 = time.time()
        while True:
            entry = self.history(prompt_id).get(prompt_id)
            if entry:
                status = entry.get('status') or {}
                if status.get('completed') or status.get('status_str') in ('success', 'error'):
                    if status.get('status_str') == 'error':
                        raise ComfyError('job failed: ' + json.dumps(status.get('messages', []))[:2000])
                    return entry
            if timeout and time.time() - t0 > timeout:
                raise ComfyError(f'job {prompt_id} still running after {timeout:.0f}s')
            if on_poll:
                on_poll(time.time() - t0)
            time.sleep(poll)

    def view(self, filename, subfolder='', type_='output'):
        q = urllib.parse.urlencode({'filename': filename, 'subfolder': subfolder, 'type': type_})
        return self._request('/view?' + q, raw=True)

    def interrupt(self):
        return self.post('/interrupt', {})

    def free(self, unload_models=True, free_memory=True):
        return self.post('/free', {'unload_models': unload_models, 'free_memory': free_memory})


# ---------- workflow helpers (no server needed) ----------

def load_workflow(path):
    """Load an API-format workflow. The GUI format (with 'nodes'/'links') is rejected."""
    with open(path, encoding='utf-8') as f:
        wf = json.load(f)
    if isinstance(wf, dict) and ('nodes' in wf or 'links' in wf) and not _looks_api(wf):
        raise ComfyError(f'{path}: this is the UI format. In ComfyUI use Workflow -> Export (API).')
    if not _looks_api(wf):
        raise ComfyError(f'{path}: not an API-format workflow (expected {{node_id: {{class_type, inputs}}}})')
    return wf


def _looks_api(wf):
    return isinstance(wf, dict) and bool(wf) and all(
        isinstance(v, dict) and 'class_type' in v for v in wf.values())


def find_nodes(workflow, class_type=None, input_name=None):
    """Node ids matching a class (exact or substring) and/or owning an input key."""
    out = []
    for nid, node in workflow.items():
        if class_type and class_type not in str(node.get('class_type', '')):
            continue
        if input_name and input_name not in (node.get('inputs') or {}):
            continue
        out.append(nid)
    return out


def set_input(workflow, target, value):
    """Set an input. target is 'input' (all nodes owning it) or 'node_id.input'.

    Returns the list of (node_id, input) pairs actually changed, so callers can report
    how many nodes a bare key touched instead of silently editing half the graph.
    """
    if '.' in target:
        nid, name = target.split('.', 1)
        if nid not in workflow:
            raise ComfyError(f'no node {nid!r} in this workflow')
        workflow[nid].setdefault('inputs', {})[name] = value
        return [(nid, name)]
    hits = []
    for nid, node in workflow.items():
        if target in (node.get('inputs') or {}):
            node['inputs'][target] = value
            hits.append((nid, target))
    if not hits:
        # Help the caller pick the right input name instead of guessing at the graph.
        near = sorted({key for node in workflow.values()
                       for key in (node.get('inputs') or {}) if target.lower() in key.lower()})
        hint = f'; similar inputs: {", ".join(near[:8])}' if near else ''
        raise ComfyError(f'no node has an input named {target!r}{hint}. Use --dry-run to read the graph.')
    return hits


def set_seed(workflow, seed):
    """Set every seed / noise_seed input in the graph."""
    hits = []
    for nid, node in workflow.items():
        for key in ('seed', 'noise_seed'):
            if key in (node.get('inputs') or {}):
                node['inputs'][key] = seed
                hits.append((nid, key))
    return hits


def models_used(workflow):
    """Model files referenced by the graph, grouped by input key (best effort)."""
    used = {}
    for nid, node in workflow.items():
        for key, val in (node.get('inputs') or {}).items():
            if isinstance(val, str) and val.lower().endswith(MODEL_EXT):
                used.setdefault(key, []).append(val)
    return used


def collect_files(entry):
    """Every downloadable file in a history entry (images, video, audio, meshes).

    Custom nodes report outputs in several shapes: dicts with filename/subfolder/type,
    or bare filenames inside a list under keys like 'gifs', '3d', 'audio', 'result'.
    Both are handled; anything unknown is ignored rather than guessed.
    """
    found = []
    for nid, out in (entry.get('outputs') or {}).items():
        for key, val in (out or {}).items():
            for item in (val if isinstance(val, list) else [val]):
                if isinstance(item, dict) and item.get('filename'):
                    found.append({'node': nid, 'key': key, 'filename': item['filename'],
                                  'subfolder': item.get('subfolder', ''),
                                  'type': item.get('type', 'output')})
                elif isinstance(item, str) and item.lower().endswith(MEDIA_EXT):
                    # some 3D/audio nodes only return a path relative to the output dir
                    name = item.replace('\\', '/').split('/')[-1]
                    sub = os.path.dirname(item.replace('\\', '/'))
                    found.append({'node': nid, 'key': key, 'filename': name,
                                  'subfolder': sub, 'type': 'output'})
    return found


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['stats', 'models', 'nodes', 'queue'])
    ap.add_argument('arg', nargs='?')
    ap.add_argument('--url', default=None)
    a = ap.parse_args()
    c = ComfyClient(a.url)
    if a.command == 'stats':
        stats = c.system_stats()
        print(json.dumps(stats, indent=2)[:4000])
    elif a.command == 'models':
        folders = [a.arg] if a.arg else c.model_folders()
        for folder in folders:
            files = c.models(folder)
            print(f'{folder}: {len(files)}')
            for f in files[:40]:
                print('  ' + f)
    elif a.command == 'nodes':
        classes = c.node_classes()
        hits = [k for k in classes if not a.arg or a.arg.lower() in k.lower()]
        print(f'{len(hits)} / {len(classes)} node classes')
        for k in hits[:200]:
            print('  ' + k)
    elif a.command == 'queue':
        print(json.dumps(c.queue(), indent=2)[:2000])


if __name__ == '__main__':
    main()