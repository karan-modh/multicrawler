"""

Scheduler - Reads crawl config information and schedules websites to be crawled in Redis.

"""

import os
import django
import redis
import json
import sys
import pprint
import time
import middleware
import argparse
import random


from datetime import datetime, timedelta

os.environ['DJANGO_SETTINGS_MODULE']='crawlconfig.settings'
django.setup()

from utils import website_config_to_json, get_domain
from siteconfig.models import *
from celery import Celery

# Order by priority
def websites_by_priority():
    """ Return websites to be crawled in priority and updated order (FIFO) """

    for item in WebSiteCrawlSchedule.objects.order_by('-priority').order_by('last_updated'):
        yield item

def scheduler(ignore_last_crawled=False, ignore_last_updated=True):
    """ Run forever scheduling websites to Redis """

    now = datetime.now()
    scheduled = []

    rd = middleware.RedisQueue()
        
    for website_s in websites_by_priority():
        website = website_s.website
        if not website_s.enabled:
            print website.website_url,'=> not enabled for scheduling'
            continue
                
        # Check the last crawled time - if its < frequency skip this site
        last_crawled = website.last_crawled

        if not ignore_last_crawled:
            if last_crawled != None:
                last_crawled = last_crawled.replace(tzinfo=None)
                
                time_diff = (now - last_crawled).days
                if time_diff < website_s.frequency:
                    print time_diff,'<',website_s.frequency,'so skipping the site',website.website_url
                    continue

        if website.last_checked != None:
            last_checked = website.last_checked.replace(tzinfo=None)
        
            # Check last_checked time - if within 24 hours, dont process this site
            # if (now - last_checked).total_seconds() < 86400:
            #    print website.website_url,'already processed in 24 hours.'
            #    continue
        
        # Schedule to be queued
        print 'Adding website for crawl',website.website_url,'...'
        website_json = website_config_to_json(website)

        json_s = json.dumps(website_json)
        print 'Pushing website',website_json['website_url'],'...'
        print website_json
        
        # Push this to redis
        rd.cpush(json_s)
        
        # Update last_checked timestamp
        website.last_checked = now
        # Save the object
        website.save()
        # Sleep a bit - otherwise timestamps will all be same
        time.sleep(random.random())

def mark_site(visible_url, spider_type, enable=True):
    """ Mark a site for automatic crawl - enable/disable """

    website = None
    
    if visible_url and spider_type:
        website = WebSite.objects.filter(visible_url=visible_url, spider_type=spider_type).all()[0]
    elif visible_url:
        website = WebSite.objects.filter(visible_url=visible_url).all()[0]
    elif spider_type:
        website = WebSite.objects.filter(spider_type=spider_type).all()[0]
    else:
        if enable:
            websites = WebSiteCrawlSchedule.objects.filter(enabled=False).all()
        else:
            websites = WebSiteCrawlSchedule.objects.filter(enabled=True).all()

        for sched in websites:
            if enable:
                print 'Marking entry for URL %s as enabled' % sched.website.visible_url
            else:
                print 'Marking entry for URL %s as disabled' % sched.website.visible_url

            sched.enabled = enable
            sched.save()
            

    if website != None:
        # Load schedule
        sched = WebSiteCrawlSchedule.objects.filter(website=website).all()[0]
        
        if enable:
            print 'Marked entry for URL %s and spider type %s as enabled' % (visible_url, spider_type)
            sched.enabled = True
        else:
            print 'Marked entry for URL %s and spider type %s as disabled' % (visible_url, spider_type)         
            sched.enabled = False

        sched.save()
    else:
        print 'No matching entry for given criteria'


def schedule_zero_crawls(ndays=0):
    """ Re-schedule zero crawls (sites with zero downloads) in last 'ndays' days """

    redis_q = middleware.RedisQueue()
    
    stats_info = WebSiteCrawlStats.objects.filter(crawl_started__gte=datetime.now() - timedelta(hours=24*7*ndays), nurls=0).all()
    stats_info = filter(lambda x: x.crawl_ended != None, stats_info)

    websites = {}

    for stats in stats_info:
        # Get the website
        website = stats.website
        if website.id in websites:
            continue
        websites[website.id] = 1

        print 'Scheduling crawl for',website
        
        try:
            webconfig_json = website_config_to_json(website)
            if website.tag2:
                webconfig_json['tag'] = website.tag2
            elif website.tag1 and website.tag1 != 'industry_report':
                webconfig_json['tag'] = website.tag1
        except IndexError:
            print 'Error in getting config for',website
            continue

        print 'Adding website for crawl',website.website_url,'...'
        json_s = json.dumps(webconfig_json)
        print json_s
        redis_q.cpush(json_s)
        website.last_checked = datetime.now()
        website.save()          
    
def schedule_bulk(query):
    """ Schedule websites in bulk using query """

    redis_q = middleware.RedisQueue()

    if ':' in query:
        # tag1:automotive
        # tag2:automotive
        field, query = query.split(':')
        websites = eval('WebSite.objects.filter(%s__icontains=query.strip()).all()' % field)
    else:
        for item in ('visible_url', 'website_url','name','tag1','tag2','tag3'):
            filter_code = 'WebSite.objects.filter(%s__icontains=query.strip()).all()' % item
            websites = eval(filter_code)
            if len(websites):
                break       

    print 'Found',len(websites),'websites. Proceed ?',
    ret = raw_input(' [y/n]').strip()
    if ret.lower() != 'y':
        sys.exit('Quitting')

    ddict = {}
    for website in websites:
        print 'Website =>',website
        # Dont schedule websites in duplicate
        domain = get_domain(website.website_url)
        if domain in ddict:
            print 'URL',website,'already parsed.'
            continue

        ddict[domain] = 1

        try:
            webconfig_json = website_config_to_json(website)
            if website.tag1:
                webconfig_json['tag'] = website.tag1
        except IndexError:
            print 'Error in getting config for',website
            continue

        print 'Adding website for crawl',website.website_url,'...'
        json_s = json.dumps(webconfig_json)
        print json_s
        redis_q.cpush(json_s)
        website.last_checked = datetime.now()
        website.save()    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Crawl auto scheduler')  
    parser.add_argument('-u','--url',help='Visible URL for a website')
    parser.add_argument('-q','--query',help='Query and bulk queue websites for crawl')
    parser.add_argument('-z','--zerocrawls',help='Re-schedule all websites which had zero crawls in the last "n" days',type=int,default=0)
    parser.add_argument('-t','--type',help='Spider type')
    parser.add_argument('-e','--enable',help='Enable selected URLs for automatic crawl schedule',action='store_true')
    parser.add_argument('-E','--enableall',help='Enable all URLs for automatic crawl schedule',action='store_true')    
    parser.add_argument('-d','--disable',help='Disable selected URLs for automatic crawl schedule',action='store_true')
    parser.add_argument('-D','--disableall',help='Disable all URLs for automatic crawl schedule',action='store_true')   
    parser.add_argument('-i','--ignore',help='Ignore last crawled timestamp',action='store_true', default=False)
    
    args = parser.parse_args()
    if args.enableall:
        print 'Enabling automatic crawl for all URLs'
        mark_site(None, None, True)
        sys.exit(0)
    elif args.disableall:
        print 'Disbling automatic crawl for all URLs'
        mark_site(None, None, False)            
        sys.exit(0)
        
    if args.url or args.type:
        if args.enable:
            print 'Enabling automatic crawl for given URL/type combination =>',args.url,args.type
            mark_site(args.url, args.type, True)
        elif args.disable:
            print 'Disabling automatic crawl for given URL/type combination =>',args.url,args.type
            mark_site(args.url, args.type, False)
        else:
            print 'Nothing to do!'
    elif args.query:
        print 'Bulk queueing websites using',args.query
        schedule_bulk(args.query)
    elif args.zerocrawls:
        print 'Re-scheduling crawls for sites with zero downloads in last',args.zerocrawls,'days.'
        schedule_zero_crawls(args.zerocrawls)
    else:
        # Run as scheduler
        print 'Running as scheduler'
        scheduler(ignore_last_crawled=args.ignore)
    
