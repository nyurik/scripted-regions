#!/usr/bin/env python3

import requests
from urllib.parse import quote
from os import path as pathlib, remove
from string import Template

query_template = Template('''
#defaultView:MapRegions
# version 6
SELECT
  (if(bound(?id2),?id2,?id) as ?id)
  $outputVars
WHERE {
# Using nested query to ensure there is only one ?id2 value
{SELECT
  ?id
  (SAMPLE(?id2) as ?id2)
$outputs
WHERE {
  # List of regions, whose sub-regions we want.
  VALUES ?entity { $entities }

  # P150 = "contains administrative territorial entity"
  ?entity $depth ?id .

$use_id2
$condition
$labels
$fields
}
# remove possible ID duplicates
GROUP BY ?id}
}
''')

label_query_template = Template('  OPTIONAL { ?id rdfs:label ?label_$lang . FILTER(LANG(?label_$lang) = "$lang") }')
field_query_template = Template('  OPTIONAL { ?id wdt:$prop ?$var }')
var_out_template = Template('  (SAMPLE(?$var) as ?$var)')
condition_template = Template('  FILTER($cond)')

def filepath(*values):
  return pathlib.join(pathlib.dirname(pathlib.realpath(__file__)), *values)


def sparql(entities, labels, fields, depth=1, condition=False, use_coextensive=False):
  '''
  entities: list|string, each value as a Qnnn: 'Q16'
  labels: list of lang codes
  fields: dict, e.g. {'iso_3166_2': 'P300', ...}
  depth: how many levels of P150 to use. 1 - immediate, 2 - two levels down,...
  condition: any additional SPARQL condition
  '''

  if type(entities) == type(''): entities = [entities]

  outputVars = list(fields.keys()) + ['label_' + v for v in labels]

  if use_coextensive:
    # There are some combined city-counties, like New York boroughs.
    # In WD they are represented as two different entities, but OSM uses one.
    # WD marks them with P3403 (coextensive with):
    #   "this item has the same boundary as the target item"
    # If P3403 exists, use that for the ?id, otherwise use the original.
    # Technically, OSM should list both WD IDs separating by semicolon,
    # But Sophox cannot handle that at the moment.
    use_id2 = '  OPTIONAL { ?id wdt:P3403 ?id2 . }'
  else:
    use_id2 = ''

  return query_template.substitute(
    entities=' '.join(['wd:' + e for e in entities]),
    depth='/'.join(['wdt:P150' for i in range(depth)]),
    labels='\n'.join([label_query_template.substitute({'lang': l}) for l in labels]),
    fields='\n'.join([field_query_template.substitute({'var': k, 'prop': v}) for k,v in fields.items()]),
    outputs='\n'.join([var_out_template.substitute({'var': v}) for v in outputVars]),
    outputVars=' '.join(['?' + v for v in outputVars]),
    condition='' if not condition else condition_template.substitute({'cond': condition}),
    use_id2=use_id2,
  )

def run_query(filetype, name, query):
  url = 'https://sophox.org/regions/{0}.json?sparql={1}'.format(filetype, quote(query))

  response = requests.get(url)
  response.raise_for_status()

  path = filepath(filetype, name + '.' + filetype)
  with open(path, 'w', encoding='utf-8') as file:
    file.write(response.text)

  print('Downloaded {0} {1:,}B => {2}'.format(name, len(response.text), path))

def append_queries_md(text):
  # Document the query we used
  with open(filepath('QUERIES.md'), 'a', encoding='utf-8') as file:
    file.write(text)

def gen(name, query):
  append_queries_md('* [{}](https://sophox.org/sophox/#{})\n'.format(name, quote(query)))
  run_query('topojson', name, query)
  run_query('geojson', name, query)


if __name__ == "__main__":
  try:
    remove(filepath('QUERIES.md'))
  except:
    raise
  append_queries_md('# Auto-generated list of queries\n\n')

  # sparql params:
  # <region Wikidata ID (str or list)>,
  # <depth level - 1 for immediate sub-regions, e.g. states for US, 2 - counties>
  # <list of label language codes>,
  # <dict of additional IDs:  <field_name>: <wikidata property ID>>

  gen('canada', sparql('Q16', ['en','fr'], {'iso_3166_2':'P300'}))
  gen('germany', sparql('Q183', ['en','de'], {'iso_3166_2':'P300'}))
  gen('china', sparql('Q148', ['en','zh'], {'iso_3166_2':'P300'}))
  gen('united_kingdom', sparql('Q145', ['en'], {'iso_3166_2':'P300'}))
  gen('france', sparql('Q142', ['en', 'fr'], {'iso_3166_2':'P300'}))

  # P883 stores both string and number for US states. E.g. MI and 26. Get string only.
  gen('us_states', sparql('Q30', ['en'], {'iso_3166_2':'P300', 'fips_5_2_alpha':'P883'},
        condition='!BOUND(?fips_5_2_alpha) || REGEX(?fips_5_2_alpha, "[A-Z]{2}")'))

  gen('us_counties', sparql('Q30', ['en'],
        {'fips_6_4_alpha': 'P882', 'gnis': 'P590', 'viaf': 'P214'},
        depth=2, use_coextensive=True))
