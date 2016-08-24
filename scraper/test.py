from django.test import TestCase

import scraper.documents
from scraper import votings

# metadata = scraper.documents.get_metadata(document_id='kst-33885-7')
# print(metadata)

# page_url = 'https://zoek.officielebekendmakingen.nl/kst-33885-7.html?zoekcriteria=%3fzkt%3dEenvoudig%26pst%3d%26vrt%3d33885%26zkd%3dInDeGeheleText%26dpr%3dAfgelopenDag%26spd%3d20160522%26epd%3d20160523%26sdt%3dDatumBrief%26ap%3d%26pnr%3d1%26rpp%3d10%26_page%3d4%26sorttype%3d1%26sortorder%3d4&resultIndex=34&sorttype=1&sortorder=4'
# scraper.documents.get_document_id(page_url)

# scraper.documents.search_politieknl_dossier(33885)


class TestExample(TestCase):
    """ Example test case """
    dossier_nr = 33885

    def test_get_votings_for_dossier(self):
        """ Example test """
        expected_urls = [
            'https://www.tweedekamer.nl/kamerstukken/stemmingsuitslagen/detail?id=2016P10154',
            'https://www.tweedekamer.nl/kamerstukken/stemmingsuitslagen/detail?id=2016P10153'
        ]
        voting_urls = votings.get_voting_urls_for_dossier(self.dossier_nr)
        self.assertEqual(len(expected_urls), len(voting_urls))
        for i in range(len(voting_urls)):
            self.assertEqual(voting_urls[i], expected_urls[i])

