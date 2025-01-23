# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import datetime

import django

try:
    import pytz
except ImportError:
    pytz = None

try:
    import csp
except ImportError:
    csp = None

from collections import OrderedDict

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.widgets import AdminDateWidget
from django.contrib.admin.widgets import AdminSplitDateTime as BaseAdminSplitDateTime
from django.template.defaultfilters import slugify
from django.templatetags.static import StaticNode
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.html import format_html

if django.VERSION >= (2, 0, 0):
    from django.utils.translation import gettext_lazy as _
else:
    from django.utils.translation import ugettext_lazy as _  # pylint: disable=E0611


class OnceCallMedia(object):
    _is_rendered = False

    def __str__(self):
        return str([str(s) for s in self._js])

    def __repr__(self):
        return "OnceCallMedia(js=%r)" % ([str(s) for s in self._js])

    def __call__(self):
        if self._is_rendered:
            return []

        self._is_rendered = True
        return self._js

    def get_js(self):
        return [
            StaticNode.handle_simple("admin/js/calendar.js"),
            StaticNode.handle_simple("admin/js/admin/DateTimeShortcuts.js"),
        ]

    _js = property(get_js)


class AdminSplitDateTime(BaseAdminSplitDateTime):
    @staticmethod
    def format_output(rendered_widgets):
        return format_html(
            '<p class="datetime">{}</p><p class="datetime rangetime">{}</p>',
            rendered_widgets[0],
            rendered_widgets[1],
        )


class DateRangeFilter(admin.filters.FieldListFilter):
    _request_key = "DJANGO_RANGEFILTER_ADMIN_JS_LIST"

    def __init__(self, field, request, params, model, model_admin, field_path):
        self.lookup_kwarg_gte = "{0}__range__gte".format(field_path)
        self.lookup_kwarg_lte = "{0}__range__lte".format(field_path)

        self.default_gte, self.default_lte = self._get_default_values(
            request, model_admin, field_path
        )

        super(DateRangeFilter, self).__init__(
            field, request, params, model, model_admin, field_path
        )
        self.request = request
        self.model_admin = model_admin

        custom_title = self._get_custom_title(request, model_admin, field_path)
        if custom_title:
            self.title = custom_title

        self.form = self.get_form(request)

    @staticmethod
    def get_timezone(_request):
        return timezone.get_default_timezone()

    @staticmethod
    def _get_custom_title(request, model_admin, field_path):
        title_method_name = "get_rangefilter_{0}_title".format(field_path)
        title_method = getattr(model_admin, title_method_name, None)

        if not callable(title_method):
            return None

        return title_method(request, field_path)

    @staticmethod
    def _get_default_values(request, model_admin, field_path):
        default_method_name = "get_rangefilter_{0}_default".format(field_path)
        default_method = getattr(model_admin, default_method_name, None)

        if not callable(default_method):
            return None, None

        return default_method(request)

    @staticmethod
    def make_dt_aware(value, tzname):
        if settings.USE_TZ:
            if django.VERSION <= (4, 0, 0) and pytz is not None:
                default_tz = tzname
                if value.tzinfo is not None:
                    value = default_tz.normalize(value)
                else:
                    value = default_tz.localize(value)
            else:
                value = value.replace(tzinfo=tzname)
        return value

    def choices(self, changelist):
        yield {
            "system_name": force_str(
                slugify(self.title) if slugify(self.title) else id(self.title)
            ),
            "query_string": changelist.get_query_string({}, remove=self._get_expected_fields()),
        }

    def expected_parameters(self):
        return self._get_expected_fields()

    def queryset(self, request, queryset):
        if self.form.is_valid():
            validated_data = dict(self.form.cleaned_data.items())
            if validated_data:
                return queryset.filter(**self._make_query_filter(request, validated_data))
        return
