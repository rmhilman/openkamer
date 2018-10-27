import datetime
import logging
import time
import multiprocessing as mp

from requests.exceptions import ConnectionError, ConnectTimeout

from django.db import transaction

from tkapi import Api
from tkapi.zaak import Zaak

import scraper.documents
import scraper.dossiers

from document.models import CategoryDocument
from document.models import CategoryDossier
from document.models import Document
from document.models import Dossier
from document.models import Kamerstuk

from openkamer.agenda import create_agenda
from openkamer.document import update_document_html_links
from openkamer.document import create_submitter
from openkamer.document import get_categories
from openkamer.kamerstuk import create_kamerstuk
from openkamer.voting import VotingFactory

logger = logging.getLogger(__name__)


def create_dossier_retry_on_error(dossier_id, max_tries=3):
    dossier_id = str(dossier_id)
    tries = 0
    while True:
        try:
            tries += 1
            create_or_update_dossier(dossier_id)
        except (ConnectionError, ConnectTimeout) as error:
            logger.exception(error)
            time.sleep(5)  # wait 5 seconds for external servers to relax
            if tries < max_tries:
                logger.error('trying again!')
                continue
            logger.error('max tries reached, skipping dossier: ' + dossier_id)
        break


@transaction.atomic
def create_or_update_dossier(dossier_id):
    logger.info('BEGIN - dossier id: ' + str(dossier_id))
    Dossier.objects.filter(dossier_id=dossier_id).delete()
    dossier_url = scraper.dossiers.search_dossier_url(dossier_id)
    last_besluit = get_besluit_last(dossier_id)
    decision = 'Onbekend'
    if last_besluit:
        decision = last_besluit.slottekst.replace('.', '')
    dossier_new = Dossier.objects.create(
        dossier_id=dossier_id,
        url=dossier_url,
        decision=decision
    )
    create_dossier_documents(dossier_new, dossier_id)
    voting_factory = VotingFactory()
    voting_factory.create_votings(dossier_id)
    dossier_new.set_derived_fields()
    logger.info('END - dossier id: ' + str(dossier_id))
    return dossier_new


class DocumentDataPolitiekNL(object):

    def __init__(self, search_result, document_id, title, metadata, content_html):
        self.search_result = search_result
        self.document_id = document_id
        self.title = title
        self.metadata = metadata
        self.content_html = content_html


def get_document_data_mp(search_result, outputs):
    # skip eerste kamer documents, first focus on the tweede kamer
    # TODO: handle eerste kamer documents
    if 'eerste kamer' in search_result['publisher'].lower():
        logger.info('skipping Eerste Kamer document')
        return
    # skip documents of some types and/or sources, no models implemented yet
    # TODO: handle all document types
    if 'Staatscourant' in search_result['type']:
        logger.info('Staatscourant, skip for now')
        return

    if 'Agenda' in search_result['type']:
        logger.info('Agenda, skip for now')
        return

    document_id, content_html, title = scraper.documents.get_document_id_and_content(search_result['page_url'])
    if not document_id:
        logger.error('No document id found for url: ' + search_result['page_url'] + ' - will not create document')
        return

    metadata = scraper.documents.get_metadata(document_id)
    document_data = DocumentDataPolitiekNL(
        search_result=search_result,
        document_id=document_id,
        title=title,
        metadata=metadata,
        content_html=content_html
    )
    outputs.append(document_data)


@transaction.atomic
def create_dossier_documents(dossier, dossier_id):
    manager = mp.Manager()
    pool = mp.Pool(processes=4)
    outputs = manager.list()
    search_results = scraper.documents.search_politieknl_dossier(dossier_id)
    for search_result in search_results:
        pool.apply_async(get_document_data_mp, args=(search_result, outputs))
    pool.close()
    pool.join()

    for data in outputs:
        if data.metadata['date_published']:
            date_published = data.metadata['date_published']
        else:
            date_published = data.search_result['date_published']

        if 'submitter' not in data.metadata:
            data.metadata['submitter'] = 'undefined'

        dossier_for_document = dossier
        if 'dossier_id' in data.metadata:
            main_dossier_id = data.metadata['dossier_id'].split(';')[0].strip()
            main_dossier_id = main_dossier_id.split('-')[0]  # remove rijkswetdossier id, for example 34158-(R2048)
            if main_dossier_id != '' and str(main_dossier_id) != str(dossier_id):
                dossier_for_document, created = Dossier.objects.get_or_create(dossier_id=main_dossier_id)
                data.content_html = update_document_html_links(data.content_html)

        properties = {
            'dossier': dossier_for_document,
            'title_full': data.metadata['title_full'],
            'title_short': data.metadata['title_short'],
            'publication_type': data.metadata['publication_type'],
            'types': data.metadata['types'],
            'publisher': data.metadata['publisher'],
            'date_published': date_published,
            'source_url': data.search_result['page_url'],
            'content_html': data.content_html,
        }
        document, created = Document.objects.update_or_create(
            document_id=data.document_id,
            defaults=properties
        )

        category_list = get_categories(
            text=data.metadata['category'],
            category_class=CategoryDocument,
            sep_char='|'
        )
        document.categories.add(*category_list)

        submitters = data.metadata['submitter'].split('|')
        for submitter in submitters:
            create_submitter(document, submitter, date_published)

        if data.metadata['is_kamerstuk']:
            is_attachement = "Bijlage" in data.search_result['type']
            if not Kamerstuk.objects.filter(id_main=dossier_id, id_sub=data.metadata['id_sub']).exists():
                create_kamerstuk(document, dossier_for_document.dossier_id, data.title, data.metadata, is_attachement)
                category_list = get_categories(text=data.metadata['category'], category_class=CategoryDossier, sep_char='|')
                dossier_for_document.categories.add(*category_list)

        # TODO BR: enable
        # if metadata['is_agenda']:
        #     create_agenda(document, metadata)


def get_inactive_dossier_ids():
    return list(Dossier.objects.filter(status__in=[
        Dossier.VERWORPEN, Dossier.AANGENOMEN, Dossier.INGETROKKEN, Dossier.CONTROVERSIEEL
    ]).values_list('dossier_id', flat=True))


def create_wetsvoorstellen_active(skip_existing=False, max_tries=3):
    logger.info('BEGIN')
    dossier_ids = Dossier.get_dossier_ids()
    dossier_ids_inactive = get_inactive_dossier_ids()
    dossier_ids_active = []
    for dossier_id in dossier_ids:
        if dossier_id not in dossier_ids_inactive:
            dossier_ids_active.append(dossier_id)
    dossier_ids_active.reverse()
    failed_dossiers = create_wetsvoorstellen(dossier_ids_active, skip_existing=skip_existing, max_tries=max_tries)
    logger.info('END')
    return failed_dossiers


def create_wetsvoorstellen_inactive(skip_existing=False, max_tries=3):
    logger.info('BEGIN')
    dossier_ids_inactive = get_inactive_dossier_ids()
    failed_dossiers = create_wetsvoorstellen(dossier_ids_inactive, skip_existing=skip_existing, max_tries=max_tries)
    logger.info('END')
    return failed_dossiers


def create_wetsvoorstellen_all(skip_existing=False, max_tries=3):
    logger.info('BEGIN')
    dossier_ids = Dossier.get_dossier_ids()
    failed_dossiers = create_wetsvoorstellen(dossier_ids, skip_existing=skip_existing, max_tries=max_tries)
    logger.info('END')
    return failed_dossiers


def create_wetsvoorstellen(dossier_ids, skip_existing=False, max_tries=3):
    logger.info('BEGIN')
    failed_dossiers = []
    for dossier_id in dossier_ids:
        dossiers = Dossier.objects.filter(dossier_id=dossier_id)
        if skip_existing and dossiers.exists():
            logger.info('dossier already exists, skip')
            continue
        try:
            create_dossier_retry_on_error(dossier_id=dossier_id, max_tries=max_tries)
        except Exception as error:
            failed_dossiers.append(dossier_id)
            logger.error('error for dossier id: ' + str(dossier_id))
            logger.error(error)
    logger.info('END')
    return failed_dossiers


def get_besluit_last(dossier_id):
    zaak = get_zaak_dossier_main(dossier_id)
    if zaak is None:
        return None
    last_besluit = None
    for besluit in zaak.besluiten:
        print(besluit.soort, besluit.slottekst, besluit.agendapunt.activiteit.begin)
        if last_besluit is None or besluit.agendapunt.activiteit.begin > last_besluit.agendapunt.activiteit.begin:
            last_besluit = besluit
    # if last_besluit:
    #     print(last_besluit.soort, last_besluit.slottekst, last_besluit.agendapunt.activiteit.begin)
    return last_besluit


def get_zaak_dossier_main(dossier_id):
    # TODO BR: filter by Wetgeving OR Initiatiefwetgeving if tkapi make that possible
    filter = Zaak.create_filter()
    filter.filter_kamerstukdossier(vetnummer=dossier_id)
    filter.filter_soort('Wetgeving')
    zaken = Api().get_zaken(filter=filter)
    if not zaken:
        filter = Zaak.create_filter()
        filter.filter_kamerstukdossier(vetnummer=dossier_id)
        filter.filter_soort('Initiatiefwetgeving')
        zaken = Api().get_zaken(filter=filter)
    if zaken:
        return zaken[0]
    return None
