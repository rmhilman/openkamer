import json
import logging

from wikidata import wikidata

logger = logging.getLogger(__name__)


def get_government(government_wikidata_id):
    government = {}
    government['name'] = wikidata.get_label(government_wikidata_id, language='nl')
    government['inception'] = wikidata.get_inception(government_wikidata_id)
    return government


def get_government_members(government_wikidata_id):
    logger.info('BEGIN')
    parts = wikidata.get_parts(government_wikidata_id)
    members = []
    for part in parts:
        member = {}
        member['properties'] = []
        member['wikidata_id'] = part['mainsnak']['datavalue']['value']['id']
        member['wikipedia_url'] = wikidata.get_wikipedia_url(member['wikidata_id'], language='nl')
        member['name'] = wikidata.get_item(member['wikidata_id'])['labels']['nl']['value']
        for prop_id in part['qualifiers']:
            prop = part['qualifiers'][prop_id][0]
            # print(json.dumps(prop, sort_keys=True, indent=4))
            if prop['datatype'] == 'wikibase-item':
                item_id = prop['datavalue']['value']['id']
                # print(item_id)
                item_label = wikidata.get_label(item_id, language='nl')
                item_label = item_label.lower()
                member['properties'].append(item_label)
                if 'ministerie' in item_label:
                    member['ministry'] = item_label.replace('ministerie van', '').strip()
                elif 'minister voor' in item_label:
                    member['ministry'] = item_label.replace('minister voor', '').strip()
                elif 'position' not in member:
                    if 'viceminister' in item_label or 'vicepremier' in item_label:
                        member['position'] = 'viceminister-president'
                    elif 'minister-president' in item_label or 'premier' in item_label:
                        member['position'] = 'minister-president'
                    elif 'staatssecretaris' in item_label:
                        member['position'] = 'staatssecretaris'
                    elif 'minister' in item_label:
                        member['position'] = 'minister'
            if prop['property'] == 'P580':  # start time
                member['start_date'] = wikidata.get_date(prop['datavalue']['value']['time'])
            if prop['property'] == 'P582':  # end time
                member['end_date'] = wikidata.get_date(prop['datavalue']['value']['time'])
        logger.info(member)
        members.append(member)
    logger.info('END')
    return members
