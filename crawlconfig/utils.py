from siteconfig.models import *
from datetime import datetime
import re
import urlparse

www_re = re.compile(r'^www\d*\.', re.IGNORECASE)

def get_domain(url):
    """ Given URL, return domain """

    if not (url.startswith('http://') or url.startswith('https://')):
        url = 'http://' + url
        
    return www_re.sub('', urlparse.urlparse(url).netloc).strip()

def website_config_to_json(website):
    """ Convert a given website config to JSON which can be shared over a middleware """
    
    # Load the config
    config = WebSiteCrawlConfig.objects.filter(website=website).all()[0]
    website_url = website.website_url
    
    # Convert the config to a JSON
    config_json = {"website_url": website.website_url,
                   "visible_url": website.visible_url,
                   "name": website.name,
                   "type": config.spider_type }

    # Add seed URLs
    if len(config.seed_urls):
        config_json["seed_urls"] = config.seed_urls
    else:
        # We need to put website as single seed URL
        if not website_url.startswith('http'):
            website_url_http = 'http://' + website_url
        else:
            website_url_http = website_url
            
        config_json["seed_urls"] = [website_url_http]
        
    # Add site config
    site_config = config.site_settings
    config_json['config'] = {'site_config': site_config}

    # Add URL patterns and parse patterns for generic types
    if config.spider_type == 'generic':
        if config.url_patterns != None:
            config_json['config']['url_patterns'] = [config.url_patterns, config.url_patterns_excl]
        if config.parse_patterns != None:
            config_json['config']['parse_patterns'] = config.parse_patterns

        # Sub-classes
        if config.spider_class:
            # Add config for the sub-class
            config_json['spider_class'] = config.spider_class
            # Add config for the class
            config_json['config']['class_config'] = {'site': config.class_settings}
            # Also add common config for the class
            # Query the config to get this
            class_config = WebSiteClassConfig.objects.filter(spider_class=config.spider_class).all()[0]
            config_json['config']['class_config']['common'] = class_config.settings

    elif config.spider_type == 'path':
        if config.url_patterns != None:
            config_json['config']['url_patterns'] = [config.url_patterns, config.url_patterns_excl]     

    # Finally add timestamp
    now = datetime.now()
    config_json['timestamp'] = now.strftime("%Y-%m-%d %H:%M:%S")
    
    return config_json
    
