import json

fixture_path = 'web_app/rostering/fixtures/datos_iniciales.json'

with open(fixture_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for item in data:
    if item.get('model') == 'rostering.reglademandasemanal':
        if 'es_excepcion' not in item['fields']:
            item['fields']['es_excepcion'] = False

with open(fixture_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Fixture actualizada con es_excepcion=False para todas las reglas")
