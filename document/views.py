import datetime
import logging

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django import forms
from django.http import HttpResponseRedirect
from django.http import HttpResponse
from django.views.generic.base import RedirectView
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

import django_filters
from dal import autocomplete

from person.models import Person

from document.models import Agenda, AgendaItem
from document.models import BesluitenLijst
from document.models import CategoryDossier
from document.models import Document, Kamerstuk
from document.models import Dossier
from document.models import Voting
from document import settings

# TODO: remove dependency on website
from website.create import create_or_update_dossier

logger = logging.getLogger(__name__)


class DocumentView(TemplateView):
    template_name = 'document/document.html'

    def get_context_data(self, document_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context['document'] = Document.objects.get(document_id=document_id)
        return context


class KamerstukView(TemplateView):
    template_name = 'document/kamerstuk.html'

    def get_context_data(self, dossier_id, sub_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context['kamerstuk'] = Kamerstuk.objects.get(id_main=dossier_id, id_sub=sub_id)
        return context


class KamerstukRedirectView(RedirectView):
    def get_redirect_url(self, dossier_id, sub_id):
        sub_id = sub_id.lstrip('0')  # remove leading zeros
        return reverse('kamerstuk', args=(dossier_id, sub_id), current_app='document')


class PersonAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        persons = Person.objects.exclude(surname='').order_by('surname')
        person_ids = []
        if self.q:
            for person in persons:
                if self.q.lower() in person.fullname().lower():
                    person_ids.append(person.id)
            return Person.objects.filter(pk__in=person_ids)
        return persons

    def get_result_value(self, result):
        return result.slug


class ModelSelect2PersonWidget(autocomplete.ModelSelect2):

    def filter_choices_to_render(self, selected_choices):
        """Override from QuerySetSelectMixin to use the slug instead of pk (pk will change on database reset)"""
        self.choices.queryset = self.choices.queryset.filter(
            slug__in=[c for c in selected_choices if c]
        )


class DossierFilter(django_filters.FilterSet):
    DOSSIER_STATUS_CHOICES = (
        (Dossier.AANGENOMEN, 'Aangenomen'),
        (Dossier.VERWORPEN, 'Verworpen'),
        (Dossier.INGETROKKEN, 'Ingetrokken'),
        (Dossier.IN_BEHANDELING, 'In behandeling'),
        (Dossier.ONBEKEND, 'Onbekend'),
    )
    title = django_filters.CharFilter(method='title_filter', label='')
    submitter = django_filters.ModelChoiceFilter(
        queryset=Person.objects.all(),
        to_field_name='slug',
        method='submitter_filter',
        label='',
        widget=ModelSelect2PersonWidget(url='person-autocomplete')
    )
    status = django_filters.ChoiceFilter(
        choices=DOSSIER_STATUS_CHOICES,
        method='status_filter',
        # widget=forms.ChoiceField()
    )
    categories = django_filters.ModelMultipleChoiceFilter(
        name='categories',
        queryset=CategoryDossier.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = Dossier
        exclude = '__all__'

    def title_filter(self, queryset, name, value):
        dossiers = queryset.filter(document__title_full__icontains=value).distinct()
        return dossiers

    def submitter_filter(self, queryset, name, value):
        dossiers = queryset.filter(document__submitter__person=value).distinct()
        return dossiers

    def status_filter(self, queryset, name, value):
        return queryset.filter(status=value)


class DossiersView(TemplateView):
    template_name = 'document/dossiers.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dossier_filter = DossierFilter(self.request.GET, queryset=Dossier.objects.all())
        dossiers_filtered = dossier_filter.qs
        paginator = Paginator(dossier_filter.qs, settings.DOSSIERS_PER_PAGE)
        page = self.request.GET.get('page')
        try:
            dossiers = paginator.page(page)
        except PageNotAnInteger:
            dossiers = paginator.page(1)
        except EmptyPage:
            dossiers = paginator.page(paginator.num_pages)
        context['dossiers'] = dossiers
        two_month_ago = datetime.date.today()-datetime.timedelta(days=60)
        context['dossiers_voted'] = dossiers_filtered.filter(voting__is_dossier_voting=True, voting__vote__isnull=False, voting__date__gt=two_month_ago).distinct().order_by('-voting__date')[0:settings.NUMBER_OF_LATEST_DOSSIERS]
        context['filter'] = dossier_filter
        return context


class DossierView(TemplateView):
    template_name = 'document/dossier.html'

    def get_context_data(self, dossier_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dossier'] = Dossier.objects.get(dossier_id=dossier_id)
        return context


class TimelineItem(object):
    def __init__(self, obj):
        self.obj = obj

    @staticmethod
    def template_name():
        raise NotImplementedError

    @property
    def date(self):
        raise NotImplementedError


class TimelineKamerstukItem(TimelineItem):
    def __init__(self, obj, besluit_cases=None):
        super().__init__(obj)
        self.besluit_cases = besluit_cases

    @staticmethod
    def template_name():
        return 'document/items/timeline_kamerstuk.html'

    @property
    def date(self):
        return self.obj.document.date_published


class TimelineBesluitItem(TimelineItem):
    def __init__(self, obj):
        super().__init__(obj)

    @staticmethod
    def template_name():
        return 'document/items/timeline_besluit.html'

    @property
    def date(self):
        return self.obj.besluit_item.besluiten_lijst.date_published


class DossierTimelineView(TemplateView):
    template_name = 'document/dossier_timeline.html'

    def get_context_data(self, dossier_id, **kwargs):
        context = super().get_context_data(**kwargs)
        dossier = Dossier.objects.get(dossier_id=dossier_id)
        context['dossier'] = dossier
        timeline_items = []
        besluitenlijst_cases = dossier.besluitenlijst_cases
        to_exclude = []
        for kamerstuk in dossier.kamerstukken:
            besluit_cases = []
            for case in besluitenlijst_cases:
                if kamerstuk in case.related_kamerstukken:
                    besluit_cases.append(case)
            if besluit_cases:
                for case in besluit_cases:
                    to_exclude.append(case.id)
            timeline_items.append(TimelineKamerstukItem(kamerstuk, besluit_cases=besluit_cases))
        besluitenlijst_cases = besluitenlijst_cases.exclude(pk__in=to_exclude)
        for case in besluitenlijst_cases:
            timeline_items.append(TimelineBesluitItem(case))
        timeline_items = sorted(timeline_items, key=lambda items: items.date, reverse=True)
        context['timeline_items'] = timeline_items
        return context


class DossierTimelineHorizontalView(TemplateView):
    template_name = 'document/dossier_timeline_horizontal.html'

    def get_context_data(self, dossier_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dossier'] = Dossier.objects.get(dossier_id=dossier_id)
        return context


class AgendasView(TemplateView):
    template_name = 'document/agendas.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paginator = Paginator(Agenda.objects.all(), settings.AGENDAS_PER_PAGE)
        page = self.request.GET.get('page')
        try:
            agendas = paginator.page(page)
        except PageNotAnInteger:
            agendas = paginator.page(1)
        except EmptyPage:
            agendas = paginator.page(paginator.num_pages)
        context['agendas'] = agendas
        return context


class AgendaView(TemplateView):
    template_name = 'document/agenda.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agenda = Agenda.objects.get(id=self.kwargs['pk'])
        context['agenda'] = agenda
        context['agendaitems'] = AgendaItem.objects.filter(agenda=agenda)
        return context


class AddDossierView(TemplateView):
    template_name = 'document/dossier.html'

    def get(self, request, **kwargs):
        super().get(request=request, **kwargs)
        dossiers = Dossier.objects.filter(dossier_id=self.kwargs['dossier_id'])
        if dossiers.exists():
            dossier = dossiers[0]
        else:
            dossier = create_or_update_dossier(self.kwargs['dossier_id'])
        return redirect(reverse('dossier-timeline', args=(dossier.dossier_id,)))
        # return HttpResponseRedirect()


class VotingView(TemplateView):
    template_name = 'document/voting.html'

    def get_context_data(self, dossier_id, sub_id=None, **kwargs):
        context = super().get_context_data(**kwargs)
        if sub_id:
            kamerstuk = Kamerstuk.objects.get(id_main=dossier_id, id_sub=sub_id)
            voting = kamerstuk.voting
        else:
            dossier = Dossier.objects.get(dossier_id=dossier_id)
            voting = dossier.voting
        context['voting'] = voting
        return context


class VotingFilter(django_filters.FilterSet):
    VOTING_RESULT_CHOICES = (
        (Voting.AANGENOMEN, 'Aangenomen'),
        (Voting.VERWORPEN, 'Verworpen'),
        (Voting.INGETROKKEN, 'Ingetrokken'),
        (Voting.AANGEHOUDEN, 'Aangehouden'),
        (Voting.CONTROVERSIEEL, 'Controversieel'),
        (Voting.ONBEKEND, 'Onbekend'),
    )
    status = django_filters.ChoiceFilter(
        choices=VOTING_RESULT_CHOICES,
        method='status_filter',
    )

    class Meta:
        model = Voting
        exclude = '__all__'

    def result_filter(self, queryset, name, value):
        return queryset.filter(result=value)


class VotingsView(TemplateView):
    template_name = 'document/votings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voting_filter = VotingFilter(self.request.GET, queryset=Voting.objects.all())
        votings_filtered = voting_filter.qs
        paginator = Paginator(votings_filtered.order_by('-date'), settings.VOTINGS_PER_PAGE)
        page = self.request.GET.get('page')
        try:
            votings = paginator.page(page)
        except PageNotAnInteger:
            votings = paginator.page(1)
        except EmptyPage:
            votings = paginator.page(paginator.num_pages)
        context['votings'] = votings
        context['filter'] = voting_filter
        return context


class BesluitenLijstenView(TemplateView):
    template_name = 'document/besluitenlijsten.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paginator = Paginator(BesluitenLijst.objects.all(), settings.BESLUITENLIJSTEN_PER_PAGE)
        page = self.request.GET.get('page')
        try:
            besluitenlijsten = paginator.page(page)
        except PageNotAnInteger:
            besluitenlijsten = paginator.page(1)
        except EmptyPage:
            besluitenlijsten = paginator.page(paginator.num_pages)
        context['besluitenlijsten'] = besluitenlijsten
        return context


class BesluitenLijstView(TemplateView):
    template_name = 'document/besluitenlijst.html'

    def get_context_data(self, activity_id, **kwargs):
        context = super().get_context_data(**kwargs)
        context['besluitenlijst'] = BesluitenLijst.objects.get(activity_id=activity_id)
        return context
