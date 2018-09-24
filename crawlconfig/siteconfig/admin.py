from django.contrib import admin
from django.db import models
from .models import *
# Register your models here.


class WebSiteAdmin(admin.ModelAdmin):
    list_display = ( 'name', 'website_url', 'visible_url')


class WebSiteClassConfigAdmin(admin.ModelAdmin):
    list_display = ('spider_class', 'settings')


class WebSiteCrawlConfigAdmin(admin.ModelAdmin):
    list_display = ('website', 'spider_type', 'url_patterns',
                    'url_patterns_excl')


class WebSiteCrawlScheduleAdmin(admin.ModelAdmin):
    list_display = ('website', 'priority', 'frequency')


admin.site.register(WebSite, WebSiteAdmin)
admin.site.register(WebSiteClassConfig, WebSiteClassConfigAdmin)
admin.site.register(WebSiteCrawlConfig, WebSiteCrawlConfigAdmin)
admin.site.register(WebSiteCrawlSchedule, WebSiteCrawlScheduleAdmin)
