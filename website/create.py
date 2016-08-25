from parliament.models import PoliticalParty

from document.models import Document
from document.models import Dossier
from document.models import Kamerstuk
from document.models import Voting
from document.models import Vote

import scraper.documents
import scraper.votings


def create_or_update_dossier(dossier_id):
    # TODO: do not create new documents if they already exist; update!
    print('create or update dossier')
    dossiers = Dossier.objects.filter(dossier_id=dossier_id)
    if dossiers:
        dossier = dossiers[0]
    else:
        dossier = Dossier.objects.create(dossier_id=dossier_id)
    search_results = scraper.documents.search_politieknl_dossier(dossier_id)
    for result in search_results:
        print('create document for results:')

        # skip documents of some types and/or sources, no models implemente yet
        # TODO: handle all document types
        if 'Agenda' in result['type'].split(' ')[0]:
            print('WARNING: Agenda, skip for now')
            continue
        if 'Staatscourant' in result['type']:
            print('WARNING: Staatscourant, skip for now')
            continue

        document_id, content_html = scraper.documents.get_document_id_and_content(result['page_url'])
        if not document_id:
            print('WARNING: No document id found, will not create document')
            continue

        metadata = scraper.documents.get_metadata(document_id)

        if metadata['date_published']:
            date_published = metadata['date_published']
        else:
            date_published = result['date_published']

        if 'submitter' not in metadata:
            metadata['submitter'] = 'undefined'

        document = Document.objects.create(
            dossier=dossier,
            document_id=document_id,
            title_full=metadata['title_full'],
            title_short=metadata['title_short'],
            publication_type=metadata['publication_type'],
            submitter=metadata['submitter'],
            category=metadata['category'],
            publisher=metadata['publisher'],
            date_published=date_published,
            content_html=content_html,
        )

        if metadata['is_kamerstuk']:
            print('create kamerstuk')
            # print(items)
            title_parts = metadata['title_full'].split(';')
            type_short = ''
            type_long = ''
            if len(title_parts) > 2:
                type_short = title_parts[1].strip()
                type_long = title_parts[2].strip()
            if "Bijlage" in result['type']:
                print('BIJLAGE')
                type_short = 'Bijlage'
                type_long = 'Bijlage'
            Kamerstuk.objects.create(
                document=document,
                id_main=dossier_id,
                id_sub=metadata['id_sub'].zfill(2),
                type_short=type_short,
                type_long=type_long,
            )
    create_votings(dossier_id)
    return dossier


def create_votings(dossier_id):
    voting_results = scraper.votings.get_votings_for_dossier(dossier_id)
    for voting_result in voting_results:
        result = get_result_choice(voting_result.get_result())
        if result is None:
            print('ERROR: Could not interpret vote result: ' + voting_result.get_result())
            assert False
        document_id = voting_result.get_document_id()
        id_main = document_id.split('-')[0]
        dossiers = Dossier.objects.filter(dossier_id=id_main)
        voting_obj = Voting(dossier=dossiers[0], date=voting_result.date, result=result)
        assert dossiers.count() == 1
        if len(document_id.split('-')) == 2:
            id_sub = document_id.split('-')[1]
            kamerstukken = Kamerstuk.objects.filter(id_main=id_main, id_sub=id_sub)
            voting_obj.kamerstuk = kamerstukken[0]
        voting_obj.save()
        for vote in voting_result.votes:
            party = PoliticalParty.find_party(vote.party_name)
            assert party
            Vote.objects.create(voting=voting_obj, party=party, number_of_seats=vote.number_of_seats,
                                              decision=get_decision(vote.decision), details=vote.details)


def get_result_choice(result_string):
    if 'aangenomen' in result_string.lower():
        return Voting.AANGENOMEN
    elif 'verworpen' in result_string.lower():
        return Voting.VERWORPEN
    elif 'ingetrokken' in result_string.lower():
        return Voting.INGETROKKEN
    elif 'aangehouden' in result_string.lower():
        return Voting.AANGEHOUDEN
    return None


def get_decision(decision_string):
    if 'for' in decision_string.lower():
        return Vote.FOR
    elif 'against' in decision_string.lower():
        return Vote.AGAINST
    return None