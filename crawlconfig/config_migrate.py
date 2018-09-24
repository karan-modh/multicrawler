"""

Migrate configuration from spider_config.json to webconfig DB

"""

import json
import os
import django
import urlparse
import sys
import re
import argparse


os.environ['DJANGO_SETTINGS_MODULE'] = 'crawlconfig.settings'
django.setup()

from siteconfig.models import *

www_re = re.compile(r'^www\d*\.', re.IGNORECASE)
# Regexp for ports at end of domains. E.g: www.bmf.gv.at:443
domain_port_re = re.compile(r'\:\d{2,}\/?$')


def make_site_name(website_url):
    """ Given website URL return website name """

    root_domain = www_re.sub('', website_url)
    # Name
    try:
        name = " ".join([item.capitalize() for item in root_domain[:root_domain.rindex('.')].split('.')])
        return name
    except ValueError:
        print root_domain
        print 'Error with', root_domain, 'skipping', website_url, '...'


def parse_generic_config(section_config, site=None, create=False, generic_key='start_url_map', skip_class=False):
    """ Parse and import data for 'generic' section config """

    parse_patterns = section_config['parse_patterns']
    url_patterns = section_config['url_patterns']
    site_settings = section_config['site_settings']
    start_url_map = section_config['start_url_map']

    if site != None:
        # Look for specific site
        site_pp = parse_patterns[site]
        site_up = url_patterns[site]
        site_st = site_settings[site]
        site_su = start_url_map[site]

        # Add this
        website_url = urlparse.urlparse(site_su[0]).netloc
        # friendly url
        visible_url = site
        # Name -> Make from domain
        name = make_site_name(website_url)

        # Add website model
        print 'Creating DB Instances ...'
        website_instance = WebSite.objects.bulk_create([WebSite(website_url=website_url,
                                                               visible_url=visible_url,
                                                               name=name)])[0]

        # Create rest of stuff
        website_config_instance = WebSiteCrawlConfig.objects.bulk_create([WebSiteCrawlConfig(website=website_instance,
                                                                                             spider_type='generic',
                                                                                             url_patterns = site_up[0],
                                                                                             url_patterns_excl=int(site_up[1]),
                                                                                             parse_patterns=site_pp,
                                                                                             seed_urls=site_su,
                                                                                             site_settings=site_st)])

        website_scheduler_instance = WebSiteCrawlSchedule.objects.bulk_create([WebSiteCrawlSchedule(website=website_instance,
                                                                                                    priority=1,
                                                                                                    frequency=30)])
        print 'Done.'
    else:
        websites = {}
        website_configs = []
        website_class_configs = []
        website_schedulers = []
        skipped = []

        skip_start_urls=False

        if generic_key == 'start_url_map':
            base_map = start_url_map
        elif generic_key == 'url_patterns':
            base_map = url_patterns
            skip_start_urls = True
            
        # Dump for all sites...
        for site_name in base_map:
            visible_url = site_name
            # Seed URLs
            site_su = start_url_map.get(visible_url, [])

            if skip_start_urls and site_su != []:
                print 'Skipping',site_name
                continue
            
            # URL patterns
            try:
                site_up = url_patterns[visible_url]
            except KeyError:
                print 'Skipping',visible_url,'...'
                skipped.append(visible_url)
                continue

            site_pp = parse_patterns.get(visible_url, {})
            site_st = site_settings.get(visible_url, {})

            try:
                website_url = urlparse.urlparse(site_su[0]).netloc
            except IndexError:
                website_url = site_name

            # Name -> Make from domain
            name = make_site_name(website_url)
            if name == None:
                print 'Skipping',website_url,'...'
                continue

            # Add website model
            print 'Creating DB Instances for',visible_url,website_url,name,'...'

            website_instance = websites[visible_url] = WebSite(website_url=website_url,
                                                               visible_url=visible_url,
                                                               name=name)

            website_configs.append(WebSiteCrawlConfig(website=website_instance,
                                                      spider_type='generic',
                                                      url_patterns = site_up[0],
                                                      url_patterns_excl=int(site_up[1]),
                                                      parse_patterns=site_pp,
                                                      seed_urls=site_su,
                                                      site_settings=site_st))

            website_schedulers.append(WebSiteCrawlSchedule(website=website_instance,
                                                           priority=1,
                                                           frequency=30))
            
        # Parse sub-class sections
        if skip_class:
            section_class = []
        else:
            section_class = section_config['class']

        for spider_class in section_class:
            print 'Parsing generic sub-class',spider_class,'...'
            # Common config goes to 'site_settings' as '<class>:common'
            class_config = section_class[spider_class]

            # Append config for common to another table.
            common_config = class_config['common']
            website_class_configs.append(WebSiteClassConfig(spider_class=spider_class,
                                                            settings=common_config))

            for site in class_config:
                # Skip common config
                if site == 'common': continue

                website_url = site
                visible_url = site
                site_su = start_url_map.get(visible_url, [])
                if skip_start_urls and site_su != []:
                    print 'Skipping',site_name
                    continue
                
                site_st = site_settings.get(visible_url, {})
                # class settings of the site
                class_st = class_config[site]

                # Name -> Make from domain
                name = make_site_name(website_url)
                print 'Creating DB Instances for',visible_url,website_url,name,'...'
                if name == None:
                    print 'Skipping',website_url,'...'
                    continue

                # Each key is a site specific setting for the spider class
                website_instance = websites[visible_url] = WebSite(website_url=website_url,
                                                                   visible_url=visible_url,
                                                                   name=name)

                website_configs.append(WebSiteCrawlConfig(website=website_instance,
                                                          spider_type='generic',
                                                          spider_class=spider_class,
                                                          seed_urls=site_su,
                                                          site_settings=site_st,
                                                          class_settings=class_st))

                website_schedulers.append(WebSiteCrawlSchedule(website=website_instance,
                                                               priority=1,
                                                               frequency=30))

        # Create one by one
        print 'Creating',len(websites),'WebSite models.'
        # Create or update

        
        if create:
            website_instances = WebSite.objects.bulk_create(websites.values())
        else:
            website_instances = WebSite.objects.bulk_update(websites.values())

        print 'Creating',len(website_class_configs), 'WebSiteClassConfig models.'

        try:
            if create:
                WebSiteClassConfig.objects.bulk_create(website_class_configs)
            else:
                WebSiteClassConfig.objects.bulk_update(website_class_configs)
        except Exception, e:
            print 'Error',e

        # Now create others
        for config in website_configs:
            visible_url = config.website.visible_url
            config.website = WebSite.objects.filter(visible_url = visible_url).all()[0]

        print 'Creating',len(website_configs),'WebSiteCrawlConfig models.'
        if create:
            WebSiteCrawlConfig.objects.bulk_create(website_configs)
        else:
            WebSiteCrawlConfig.objects.bulk_update(website_configs)

        for sched in website_schedulers:
            visible_url = sched.website.visible_url            
            sched.website = WebSite.objects.filter(visible_url = visible_url).all()[0]

        print 'Creating',len(website_schedulers),'WebSiteSchedule models.'
        if create:
            WebSiteCrawlSchedule.objects.bulk_create(website_schedulers)
        else:
            WebSiteCrawlSchedule.objects.bulk_update(website_schedulers)

        print 'Skipped sites are',skipped

        print 'All Done.'


def parse_config(spider_type, section_config, site=None, create=False):
    """ Parse and import data for a specific section config """

    print 'Parsing and importing',spider_type,'section config.'

    site_settings = section_config['site_settings']
    print site_settings

    # Path crawlers don't have start_url_map often.
    start_url_map = section_config.get('start_url_map', {})
    if start_url_map != {}:
        base_map = start_url_map
    else:
        base_map = site_settings

    if site != None:
        # Look for specific site
        site_st = site_settings[site]
        site_su = start_url_map.get(site, {})

        # Add this
        website_url = urlparse.urlparse(site_su[0]).netloc
        # friendly url
        visible_url = site
        # Name -> Make from domain
        name = make_site_name(website_url)

        # Add website model
        print 'Creating DB Instances ...'
        website_instance = WebSite.objects.bulk_create([WebSite(website_url=website_url,
                                                               visible_url=visible_url,
                                                               name=name)])[0]

        # Create rest of stuff
        website_config_instance = WebSiteCrawlConfig.objects.bulk_create([WebSiteCrawlConfig(website=website_instance,
                                                                                             spider_type=spider_type,
                                                                                             seed_urls=site_su,
                                                                                             site_settings=site_st)])

        website_scheduler_instance = WebSiteCrawlSchedule.objects.bulk_create([WebSiteCrawlSchedule(website=website_instance,
                                                                                                    priority=1,
                                                                                                    frequency=30)])
        print 'Done.'
    else:
        websites = {}
        website_configs = []
        website_class_configs = []
        website_schedulers = []
        skipped = []

        # Dump for all sites...
        for site_name in base_map:
            visible_url = site_name
            # Seed URLs
            site_su = start_url_map.get(visible_url, {})
            site_st = site_settings.get(visible_url, {})

            if len(site_su):
                website_url = urlparse.urlparse(site_su[0]).netloc
            else:
                website_url = visible_url

            # Name -> Make from domain
            name = make_site_name(website_url)
            if name == None:
                print 'Skipping',website_url,'...'
                continue

            # Add website model
            print 'Creating DB Instances for',visible_url,website_url,name,'...'

            website_instance = websites[visible_url] = WebSite(website_url=website_url,
                                                               visible_url=visible_url,
                                                               name=name)

            website_configs.append(WebSiteCrawlConfig(website=website_instance,
                                                      spider_type=spider_type,
                                                      seed_urls=site_su,
                                                      site_settings=site_st))

            website_schedulers.append(WebSiteCrawlSchedule(website=website_instance,
                                                           priority=1,
                                                           frequency=30))

        # Create one by one
        print 'Creating',len(websites),'WebSite models.'
        # Create or update

        if create:
            website_instances = WebSite.objects.bulk_create(websites.values())
        else:
            website_instances = WebSite.objects.bulk_update(websites.values())

        # Now create others
        for config in website_configs:
            visible_url = config.website.visible_url
            config.website = WebSite.objects.filter(visible_url = visible_url).all()[0]

        print 'Creating',len(website_configs),'WebSiteCrawlConfig models.'
        if create:
            WebSiteCrawlConfig.objects.bulk_create(website_configs)
        else:
            WebSiteCrawlConfig.objects.bulk_update(website_configs)

        for sched in website_schedulers:
            visible_url = sched.website.visible_url                     
            sched.website = WebSite.objects.filter(visible_url = visible_url).all()[0]

        print 'Creating',len(website_schedulers),'WebSiteSchedule models.'
        if create:
            WebSiteCrawlSchedule.objects.bulk_create(website_schedulers)
        else:
            WebSiteCrawlSchedule.objects.bulk_update(website_schedulers)

        print 'Skipped sites are',skipped

        print 'All Done.'


def migrate(filename='spider_config.json', spider_type='generic', site=None, create=False, generic_key='start_url_map',
            skip_class=False):
    """ Migrate all configuration for a given spider type and (optional) site """

    # Load spider_config.json
    config = json.load(open(filename))
    # Load the section
    section_config = config[spider_type]

    if spider_type == 'generic':
        return parse_generic_config(section_config, site, create, generic_key, skip_class)
    else:
        return parse_config(spider_type, section_config, site, create)

def get_default_config(type):
    """ Get default configuration """
    pass

def bulk_add_config(query, spider_type):
    """ Bulk add configuration to sites that don't have it """

    for item in ('visible_url', 'website_url','name','tag1','tag2','tag3'):
        filter_code = 'WebSite.objects.filter(%s__icontains=query.strip()).all()' % item
        websites = eval(filter_code)
        if len(websites):
            break

    configs, scheds = [],[]
    for site in websites:
        # If there is a config ignore the site
        try:
            config = WebSiteCrawlConfig.objects.filter(website=site).all()[0]
        except IndexError:
            # No configuration - so add one
            print 'Adding default configuration for',site.visible_url,'...'
            if spider_type == 'path':
                config = WebSiteCrawlConfig(website=site,
                                            spider_type=spider_type,
                                            site_settings={'allow_queries': False,
                                                           'selenium': False })

                configs.append(config)

        try:
            config = WebSiteCrawlSchedule.objects.filter(website=site).all()[0]
        except IndexError:
            # No configuration - so add one
            print 'Adding default schedule configuration for',site.visible_url,'...'
            sched = WebSiteCrawlSchedule(website=site,
                                         frequency=30,
                                         priority=1,
                                         enabled=False)

            
            scheds.append(sched)              

    print 'Creating',len(configs),'objects.'
    WebSiteCrawlConfig.objects.bulk_create(configs)

    print 'Creating',len(scheds),'objects.'
    WebSiteCrawlSchedule.objects.bulk_create(scheds)    
            

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Migrate configuration of crawlers from JSON to DB')
    parser.add_argument('-s','--site',help='Site to migrate for')
    parser.add_argument('-t','--type',help='Spider type to migrate for')
    parser.add_argument('-c','--create',help='Create objects in DB', action='store_true')
    parser.add_argument('-S','--skipclass',help='Skip class section parsing', action='store_true')  
    parser.add_argument('-k','--key',help='Base key for generic class', default='start_url_map')
    parser.add_argument('-F','--flush',help='Flush all the tables and purge data', action='store_true')
    parser.add_argument('-B','--bulkconfig',help='Bulk add configuration of a specific type')
    
    if len(sys.argv)<2:
        sys.argv.append('-h')

    args = parser.parse_args()
    if args.flush:
        # Deleting all data
        print 'Purging all data...'
        print 'Deleting all WebSiteCrawlConfig instances...'
        WebSiteCrawlConfig.objects.all().delete()
        print 'Deleting all WebSiteScheduler instances...'
        WebSiteCrawlSchedule.objects.all().delete()
        print 'Deleting all WebSiteClassConfig instances...'
        WebSiteClassConfig.objects.all().delete()
        print 'Deleting all WebSite instances...'
        WebSite.objects.all().delete()

    if args.type != None:
        if args.bulkconfig != None:
            print 'Bulk adding configuration to for websites via',args.bulkconfig,'with type',args.type
            bulk_add_config(args.bulkconfig, args.type)
        else:
            migrate(spider_type=args.type, site=args.site, create=args.create, generic_key=args.key, skip_class=args.skipclass)
    else:
        print 'Not doing migration.'
