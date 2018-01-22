#!/usr/bin/env python3

import requests
from urllib.parse import quote
from os import path as pathlib
from string import Template

query_template = Template('''
#defaultView:MapRegions
#4
SELECT
  ?id
$outputs
WHERE {
  # List of regions, whose sub-regions we want.
  VALUES ?entity { $entities }

  # P150 = "contains administrative territorial entity"
  # but must not have a P582 (end date) qualifier
  ?entity p:P150 ?statement .
  ?statement ps:P150 ?id .
  FILTER NOT EXISTS { ?statement pq:P582 ?x }

$labels
$fields

}
# remove possible ID duplicates
GROUP BY ?id
''')

label_query_template = Template('  OPTIONAL { ?id rdfs:label ?label_$lang . FILTER(LANG(?label_$lang) = "$lang") }')
field_query_template = Template('  OPTIONAL { ?id wdt:$prop ?$var }')
var_out_template = Template('  (SAMPLE(?$var) as ?$var)')

def query(filetype, name, entities, labels, fields):
  '''
  entities: list|string, each value as a Qnnn: 'Q16'
  labels: list of lang codes
  fields: dict, e.g. {'iso_3166_2': 'P300', ...}
  '''

  if type(entities) == type(''): entities = [entities]

  sparql = query_template.substitute(
    entities=' '.join(['wd:' + e for e in entities]),
    labels='\n'.join([label_query_template.substitute({'lang': l}) for l in labels]),
    fields='\n'.join([field_query_template.substitute({'var': k, 'prop': v}) for k,v in fields.items()]),
    outputs='\n'.join(
      [var_out_template.substitute({'var': v}) for v in fields.keys()] +
      [var_out_template.substitute({'var': 'label_' + v}) for v in labels]
    ),
  )

  url = 'https://sophox.org/regions/{0}.json?sparql={1}'.format(filetype, quote(sparql))

  response = requests.get(url)
  response.raise_for_status()

  path = pathlib.join(pathlib.dirname(pathlib.realpath(__file__)), filetype, name + '.' + filetype)
  with open(path, 'w', encoding='utf-8') as file:
    file.write(response.text)

  print('Downloaded {0} ({1:,}) => {2}'.format(','.join(entities), len(response.text), path))


if __name__ == "__main__":
  names = {
    'canada': ('Q16', ['en','fr'], {'iso_3166_2':'P300'}),
    'germany': ('Q183', ['en','de'], {'iso_3166_2':'P300'}),
  }

  for name, vals in names.items():
    query('topojson', name, *vals)
    query('geojson', name, *vals)
