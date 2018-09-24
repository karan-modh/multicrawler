from django import forms
from django.forms import ModelForm
from .models import  *


class WebSiteForm(ModelForm):
    """ Model form for WebSite class """
    
    visible_url = forms.CharField(required=False)
    name = forms.CharField(required=False)
    class Meta:
        model = WebSite
        fields = ('website_url', 'visible_url', 'name')
        exclude = ['last_crawled']


class WebSiteCrawlConfigFormBasic(ModelForm):
    """ Model form for WebSiteCrawlConfigclass - Basic version (for picking website) """
    
    class Meta:
        model = WebSiteCrawlConfig
        fields = ['website']
        #widgets = {'website': forms.Select(choices=WebSite.objects.all(),
        #                      attrs={'onChange': 'selectWebsite(this)'})}


class WebSiteCrawlConfigForm(ModelForm):
    """ Model form for WebSiteCrawlConfig class """

    class Meta:
        model = WebSiteCrawlConfig
        fields = '__all__'
        widgets = {'url_patterns': forms.Textarea(attrs={'cols': 20,
                                                         'rows': 3}),
                   'parse_patterns': forms.Textarea(attrs={'cols': 20,
                                                           'rows': 3}),
                   'seed_urls': forms.Textarea(attrs={'cols': 40,
                                                      'rows': 5,
                                                      'style': 'height:100px;width:500px'}),
                   'site_settings': forms.Textarea(attrs={'cols': 20,
                                                          'rows': 5,
                                                      'style': 'height:100px'}),                                                          
                   'class_settings': forms.Textarea(attrs={'cols': 20,
                                                           'rows': 5,
                                                      'style': 'height:100px'}),                                                           
                   'spider_type': forms.Select(attrs={'style': 'width: 100px'}),
                   'spider_class': forms.Select(attrs={'style': 'width: 100px'}),                  
                   'url_patterns_excl': forms.NumberInput(attrs={'style': 'width:50px'})}
                   #'website': forms.Select(choices=WebSite.objects.all(),
                   #                       attrs={'onChange': 'selectWebsite(this)'})}                  
        

class WebSiteCrawlScheduleForm(ModelForm):
    """ Model form for WebSiteCrawlSchedule class """
    
    class Meta:
        model = WebSiteCrawlSchedule
        exclude = ['website']
        fields = '__all__'
        widgets = { 'priority': forms.NumberInput(attrs={'style': 'width:50px'}),
                    'frequency': forms.NumberInput(attrs={'style': 'width:50px'}) }
        
class DocumentForm(ModelForm):
    class Meta:
        model = UploadDocument
        fields = ('description', 'document', 'tag1', 'tag2', 'tag3', 'allow_update', 'extended_format')
