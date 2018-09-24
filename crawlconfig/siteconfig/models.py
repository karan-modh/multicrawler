
from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import JSONField
from django_bulk_update.manager import BulkUpdateManager
from django.core.validators import MaxValueValidator, MinValueValidator


# Create your models here.

class WebSite(models.Model):
    """ Website model class """

    objects = BulkUpdateManager()
    # website URL
    website_url = models.CharField(max_length=1024, blank=False, null=False)
    # Friendly URL
    visible_url = models.CharField(max_length=1024, blank=False, null=False,
                                   unique=True)
    # Name of the site
    name = models.CharField(max_length=128, blank=False, null=False)
    # Optional tags for a site - upto 3
    tag1 = models.CharField(max_length=24, blank=True, null=True)
    tag2 = models.CharField(max_length=24, blank=True, null=True)   
    tag3 = models.CharField(max_length=24, blank=True, null=True)

    # Content-types (upto 5)
    content_type1 = models.CharField(max_length=24, blank=True, null=True)
    content_type2 = models.CharField(max_length=24, blank=True, null=True)
    content_type3 = models.CharField(max_length=24, blank=True, null=True)
    content_type4 = models.CharField(max_length=24, blank=True, null=True)
    content_type5 = models.CharField(max_length=24, blank=True, null=True)  
    
    # Last updated
    last_updated = models.DateTimeField(auto_now=True)
    # Last crawled
    last_crawled = models.DateTimeField(blank=True, null=True, default=None)
    # Last checked for crawl
    last_checked = models.DateTimeField(blank=True, null=True, default=None)
    
    def __str__(self):
        try:
            return str(self.id) + '--' + self.name.encode('utf-8', errors='replace')
        except (UnicodeEncodeError, UnicodeDecodeError), e:
            return ''

class WebSiteCrawlStats(models.Model):
    """ Crawl statistics for website """

    objects = BulkUpdateManager()
    website = models.ForeignKey(WebSite, on_delete=models.CASCADE)
    # This is the time stamp of crawl start
    crawl_started = models.DateTimeField(blank=True, null=True, default=None)
    # This is the time stamp of crawl ended
    crawl_ended = models.DateTimeField(blank=True, null=True, default=None)   
    # No of URLs downloaded
    nurls = models.IntegerField(blank=False, null=False, default=0)
    # Which node is it running ?
    crawl_node_ip = models.GenericIPAddressField(blank=False,null=True)
    # Crawl ID
    crawl_id = models.CharField(max_length=64, blank=True, null=True)
    # Error for crawl if any
    error = JSONField("Crawl Error", default={})
    last_updated = models.DateTimeField(auto_now=True)

class WebCrawlNodeStatus(models.Model):
    """ Node status for crawl nodes """

    CRAWL_STATUS = (
        ('unknown', 'UNKNOWN'),
        ('running', 'RUNNING'),
        ('finished', 'FINISHED'))
            
    objects = BulkUpdateManager()
    # Which node is it running ?
    crawl_node_ip = models.GenericIPAddressField(blank=False,null=True)
    # Which crawl is it running
    crawl_id = models.CharField(max_length=64, blank=True, null=True)
    status = models.CharField('CRAWL STATUS', max_length=32, null=False, blank=False,
                              choices=CRAWL_STATUS)
    # free memory
    memory = models.FloatField('Free Memory', default=0.0, blank=False, null=False)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '%s - %s @ %s' % (self.crawl_node_ip, self.status, self.last_updated)

class WebSiteCrawlConfig(models.Model):
    """ WebSite Crawl Configuration - mirroring spider_config.json """
    SPIDER_TYPES = (
        ('generic', 'Generic'),
        ('path', 'Path'),
        ('pdf', 'Pdf'),
        ('click', 'Click'),
        ('pub', 'Pub'),
        ('org', 'Org')
    )

    SPIDER_CLASS = (
        ('press', 'Press'),
        ('speaker', 'Speaker')
    )

    objects = BulkUpdateManager()

    website = models.ForeignKey(WebSite, on_delete=models.CASCADE)
    spider_type = models.CharField("Spider Type",max_length=24, blank=False,
                                   null=False, choices=SPIDER_TYPES)
    # Spider sub-class for generic spiders
    spider_class = models.CharField("Spider Class", max_length=24, blank=True,
                                    null=True, default=None,
                                    choices=SPIDER_CLASS)
    # Only for generic spider
    url_patterns = models.CharField("URL Patterns", max_length=1024, blank=True, null=True)
    url_patterns_excl = models.IntegerField("URL Patterns Exclusive", default=1, null=False, blank=False)
    parse_patterns = models.CharField("Parse Patterns", max_length=512, blank=True, null=True)
    seed_urls = JSONField("Seed URLs", default={})
    # Site specific settings
    site_settings = JSONField("Site Settings", default={})
    # Spider-subclass specific settings for a site-indexed by the sub-class key
    class_settings = JSONField("Class Settings", default={})
    # Last updated
    last_updated = models.DateTimeField(auto_now=True)


class WebSiteClassConfig(models.Model):
    """ WebSite Config for generic class sub-classes """

    objects = BulkUpdateManager()

    # Spider sub-class for generic spiders
    spider_class = models.CharField("Spider Class", max_length=24, blank=True,
                                    null=True, default=None, unique=True,
                                    choices=WebSiteCrawlConfig.SPIDER_CLASS)
    settings = JSONField(default={})
    # Last updated
    last_updated = models.DateTimeField(auto_now=True)



class WebSiteCrawlSchedule(models.Model):
    """ WebSite Crawl Schedule model class """

    objects = BulkUpdateManager()

    website = models.ForeignKey(WebSite, on_delete=models.CASCADE)
    priority = models.IntegerField(default=1, null=False, blank=False,
                                   validators=[MaxValueValidator(100),
                                               MinValueValidator(1)])
    # How often to recrawl a site - in #days
    frequency = models.IntegerField(default=30, null=False, blank=False,
                                    validators=[MaxValueValidator(60),
                                                MinValueValidator(1)])
    # Enabled for regular crawl by scheduler ?
    enabled = models.BooleanField(default=False, null=False, blank=False)
    
    # Last updated
    last_updated = models.DateTimeField(auto_now=True)

class WebCrawlSessionToken(models.Model):
    """ Secure tokens for crawler sessions """

    session_token = models.CharField(max_length=64, blank=False, null=False)
    crawl_node_ip = models.GenericIPAddressField(blank=False,null=False)
    created_at = models.DateTimeField(auto_now=True)
    
class UploadDocument(models.Model):
    """ Model for uploaded files """

    objects = BulkUpdateManager()
    
    description = models.CharField(max_length=120, blank=True)
    document = models.FileField(upload_to='uploads/')
    # Optional tags to attach to each of the site
    tag1 = models.CharField(max_length=24, blank=True, null=True)
    tag2 = models.CharField(max_length=24, blank=True, null=True)   
    tag3 = models.CharField(max_length=24, blank=True, null=True)
    allow_update = models.BooleanField(default=False)
    # Extended format 
    extended_format = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now=True)
