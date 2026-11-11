"""Fast checks; the CI Odoo installation is authoritative for ORM/view behavior."""
import ast
from pathlib import Path
from lxml import etree

root = Path(__file__).resolve().parents[1]
addon = root / 'popspec_optical'
manifest = ast.literal_eval((addon / '__manifest__.py').read_text())
assert manifest['version'].startswith('19.0.')
for file in addon.rglob('*.py'):
    ast.parse(file.read_text(), filename=str(file))
ids = set()
for name in manifest['data']:
    file = addon / name
    assert file.is_file(), name
    if file.suffix == '.xml':
        tree = etree.parse(str(file))
        assert tree.getroot().tag == 'odoo'
        assert not tree.xpath('//*[@attrs or @states]'), 'Use Odoo 19 view modifiers'
        for node in tree.xpath('//*[@id]'):
            external_id = node.get('id')
            assert external_id not in ids, external_id
            ids.add(external_id)
assert not list(addon.glob('controllers/*')), 'Clinical records are not exposed through custom public routes'
assert 'popspec_website' not in manifest['depends'], 'Operations must remain independently installable'
print('Python/XML/manifest checks passed.')
