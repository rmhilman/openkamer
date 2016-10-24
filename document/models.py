import logging

from itertools import chain
from django.db import models

from person.models import Person

from parliament.models import PoliticalParty
from parliament.models import ParliamentMember

logger = logging.getLogger(__name__)


class Dossier(models.Model):
    dossier_id = models.CharField(max_length=100, blank=True, unique=True)

    def __str__(self):
        return str(self.dossier_id)

    def documents(self):
        return Document.objects.filter(dossier=self)

    def kamerstukken(self):
        return Kamerstuk.objects.filter(document__dossier=self)

    def voting(self):
        votings = Voting.objects.filter(dossier=self, is_dossier_voting=True)
        if votings.exists():
            return votings[0]
        return None

    def title(self):
        kamerstukken = self.kamerstukken()
        titles = {}
        for stuk in kamerstukken:
            title = stuk.document.title()
            if title in titles:
                titles[title] += 1
            else:
                titles[title] = 1
        max_titles = 0
        title = 'undefined'
        for key, value in titles.items():
            if value > max_titles:
                title = key
                max_titles = value
        return title


class Document(models.Model):
    dossier = models.ForeignKey(Dossier, blank=True, null=True)
    document_id = models.CharField(max_length=200, blank=True)
    title_full = models.CharField(max_length=500)
    title_short = models.CharField(max_length=200)
    publication_type = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=200, blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    date_published = models.DateField(blank=True, null=True)
    content_html = models.CharField(max_length=200000, blank=True)

    def submitters(self):
        return Submitter.objects.filter(document=self).exclude(person__surname='')

    def title(self):
        return self.title_full.split(';')[0]

    def document_url(self):
        return 'https://zoek.officielebekendmakingen.nl/' + str(self.document_id) + '.html'

    def __str__(self):
        return self.title_short

    class Meta:
        ordering = ['-date_published']


class Submitter(models.Model):
    person = models.ForeignKey(Person)
    document = models.ForeignKey(Document)

    def __str__(self):
        return self.person.fullname()


class Kamerstuk(models.Model):
    document = models.ForeignKey(Document)
    id_main = models.CharField(max_length=40, blank=True)
    id_sub = models.CharField(max_length=40, blank=True)
    type_short = models.CharField(max_length=40, blank=True)
    type_long = models.CharField(max_length=100, blank=True)
    original_id = models.CharField(max_length=40, blank=True)  # format: 33885.22

    MOTIE = 'Motie'
    AMENDEMENT = 'Amendement'
    WETSVOORSTEL = 'Wetsvoorstel'
    VERSLAG = 'Verslag'
    NOTA = 'Nota'

    def __str__(self):
        return str(self.id_main) + '.' + str(self.id_sub) + ': ' + str(self.type_long)

    def type(self):
        if 'nota' in self.type_short.lower():
            return Kamerstuk.NOTA
        elif 'motie' in self.type_short.lower():
            return Kamerstuk.MOTIE
        elif 'amendement' in self.type_short.lower():
            return Kamerstuk.AMENDEMENT
        elif self.voorstelwet():
            return Kamerstuk.WETSVOORSTEL
        elif 'verslag' in self.type_short.lower():
            return Kamerstuk.VERSLAG
        return None

    def id_full(self):
        return str(self.id_main) + '.' + str(self.id_sub)

    def voting(self):
        votings = Voting.objects.filter(kamerstuk=self)
        if votings.exists():
            return votings[0]
        return None

    def visible(self):
        if self.type_short == 'Koninklijke boodschap':
            return False
        return True

    def voorstelwet(self):
        if 'voorstel van wet' in self.type_short.lower():
            return True
        return False


    def original(self):
        if not self.original_id:
            return None
        ids = self.original_id.split('.')
        if ids[1] == 'voorstel_van_wet':
            kamerstukken = Kamerstuk.objects.filter(id_main=ids[0])
            for stuk in kamerstukken:
                if 'voorstel van wet' in stuk.type_short.lower() and 'gewijzigd' not in stuk.type_short.lower():
                    return stuk
        kamerstukken = Kamerstuk.objects.filter(id_main=ids[0], id_sub=ids[1])
        if kamerstukken.exists():
            return kamerstukken[0]
        return None

    def modifications(self):
        if self.voorstelwet():
            stukken = Kamerstuk.objects.filter(original_id=self.id_main+'.voorstel_van_wet')
        else:
            stukken = Kamerstuk.objects.filter(original_id=self.id_full())
        return stukken

    class Meta:
        verbose_name_plural = 'Kamerstukken'
        ordering = ['document__date_published', 'id_sub',]


class Agenda(models.Model):
    document = models.ForeignKey(Document)
    agenda_id = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return str(self.document)


class AgendaItem(models.Model):
    agenda = models.ForeignKey(Agenda)
    dossier = models.ForeignKey(Dossier, null=True)
    item_text = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return str(self.agenda)

    
class Voting(models.Model):
    AANGENOMEN = 'AAN'
    VERWORPEN = 'VER'
    INGETROKKEN = 'ING'
    AANGEHOUDEN = 'AGH'
    CHOICES = (
        (AANGENOMEN, 'Aangenomen'), (VERWORPEN, 'Verworpen'), (INGETROKKEN, 'Ingetrokken'), (AANGEHOUDEN, 'Aangehouden')
    )
    dossier = models.ForeignKey(Dossier)
    kamerstuk = models.ForeignKey(Kamerstuk, blank=True, null=True)
    is_dossier_voting = models.BooleanField(default=False)
    result = models.CharField(max_length=3, choices=CHOICES)
    date = models.DateField(auto_now=False, blank=True)

    def votes(self):
        return list(chain(self.votes_party(), self.votes_individual()))

    def votes_party(self):
        return VoteParty.objects.filter(voting=self)

    def votes_individual(self):
        return VoteIndividual.objects.filter(voting=self)

    def has_result_details(self):
        return len(self.votes()) > 0

    def entities_for_string(self):
        entities_str = ''
        for vote in self.votes():
            if vote.decision == Vote.FOR:
                entities_str += vote.get_name() + ', '
        return entities_str

    def entities_against_string(self):
        entities_str = ''
        for vote in self.votes():
            if vote.decision == Vote.AGAINST:
                entities_str += vote.get_name() + ', '
        return entities_str

    def entities_none_string(self):
        entities_str = ''
        for vote in self.votes():
            if vote.decision == Vote.NONE:
                entities_str += vote.get_name() + ', '
        return entities_str

    def result_percent(self):
        n_votes = 0
        vote_for = 0
        vote_against = 0
        vote_none = 0
        for vote in self.votes():
            n_votes += vote.number_of_seats
            if vote.decision == Vote.FOR:
                vote_for += vote.number_of_seats
            elif vote.decision == Vote.AGAINST:
                vote_against += vote.number_of_seats
            elif vote.decision == Vote.NONE:
                vote_none += vote.number_of_seats
        if n_votes == 0:
            return None
        for_percent = vote_for/n_votes * 100.0
        against_percent = vote_against/n_votes * 100.0
        no_vote_percent = vote_none/n_votes * 100.0
        return {'for': for_percent, 'against': against_percent, 'no_vote': no_vote_percent}

    def __str__(self):
        return 'Dossier: ' + self.dossier.dossier_id + ', result: ' + self.result


class Vote(models.Model):
    FOR = 'FO'
    AGAINST = 'AG'
    NONE = 'NO'
    MISTAKE = 'MI'
    CHOICES = (
        (FOR, 'For'), (AGAINST, 'Against'), (NONE, 'None'), (MISTAKE, 'Mistake')
    )

    voting = models.ForeignKey(Voting)
    number_of_seats = models.IntegerField()
    decision = models.CharField(max_length=2, choices=CHOICES)
    details = models.CharField(max_length=2000, blank=True, null=False, default='')

    def get_name(self):
        raise NotImplementedError

    def __str__(self):
        return str(self.voting) + ' - ' + str(self.decision)


class VoteParty(Vote):
    party = models.ForeignKey(PoliticalParty)

    def get_name(self):
        return self.party.name


class VoteIndividual(Vote):
    parliament_member = models.ForeignKey(ParliamentMember, blank=True, null=True)

    def get_name(self):
        return str(self.parliament_member)
