"""Read-only release discovery. Never execute downloaded code or overwrite the app."""
import json
import re
import urllib.request

URL = 'https://api.github.com/repos/ArN-LaB/Spoolscribe-/releases/latest'

def parse_release(data, current):
    tag = data.get('tag_name', '')
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag) or data.get('draft') or data.get('prerelease'):
        raise ValueError('La réponse GitHub ne décrit pas une version stable valide.')
    expected = 'https://github.com/ArN-LaB/Spoolscribe-/releases/tag/' + tag
    if data.get('html_url') != expected:
        raise ValueError('Adresse de publication inattendue.')
    version = tag[1:]
    newer = tuple(map(int, version.split('.'))) > version_tuple(current)
    return dict(version=version, newer=newer, url=expected)


def version_tuple(text):
    """'0.3.1-dev' or '0.3.1rc1' compare as 0.3.1; anything else is invalid."""
    match = re.match(r'(\d+)\.(\d+)\.(\d+)', str(text))
    if not match:
        raise ValueError(f'Version locale illisible : {text!r}')
    return tuple(int(part) for part in match.groups())


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirection de mise à jour refusée')


def check_release(current):
    request=urllib.request.Request(URL, headers={'Accept':'application/vnd.github+json', 'User-Agent':'SpoolScribe'})
    with urllib.request.build_opener(_NoRedirect()).open(request,timeout=20) as response:
        if response.url != URL: raise ValueError('Redirection de mise à jour inattendue')
        raw=response.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('Réponse GitHub trop volumineuse')
    return parse_release(json.loads(raw),current)
