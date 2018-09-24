from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .forms import *
from config_migrate import make_site_name
from django.views.decorators.csrf import csrf_exempt

from models import WebSite
from datetime import datetime, timedelta
import middleware
import bcrypt
import urllib
import json
import utils
import uuid
import re
import socket
import requests
import json

from collections import defaultdict

redis_q = middleware.RedisQueue()

# Shared token
SHARED_TOKEN='0c437e9ba6ca7948362d4624b7bdc303'

global_tokens = {}

# * in the beginning
asterisk_begin_re = re.compile(r'^\*')
# * at end
asterisk_end_re = re.compile(r'\*$')

@login_required
def site_add(request):
    """ Add a website to the configuration """
    
    form = {}

    if request.method == "POST":
        website_form = WebSiteForm(request.POST)
        if website_form.is_valid():
            website_form = website_form.save(commit=False)

            if not website_form.visible_url:
                website_form.visible_url = website_form.website_url

            if not website_form.name:
                website_form.name = make_site_name(website_form.website_url)

            website_form.last_updated = datetime.now()
            website_form.save()
            return render(request, 'saved_thanks.html')          

    else:
        website_form = WebSiteForm()

    return render(request, 'siteconfig/siteadd.html', {'site_add_form': website_form,
                                                       'add_title': 'Add a new website to crawl',
                                                       'action': '',
                                                       'add_site': True
                                                       })

@login_required
def site_edit(request):
    """ Edit an existing website """

    return render(request, 'siteconfig/searchsite.html', {'action': 'search_edit'})

@login_required
def crawl_edit(request):
    """ Edit/add crawl config """

    return render(request, 'siteconfig/searchsite.html', {'action': 'crawl_config'})

@login_required
def site_view(request):
    """ View details of a website """
    
    return render(request, 'siteconfig/searchsite.html', {'action': 'site_info'})    

@login_required
def site_info(request):
    """ Show information for a site """

    query = request.GET.get('q')
    print 'Query=>',query
    
    if query != None:
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
            
        hits = []
        
        for website in websites:
            # Display it
            try:
                website_config = WebSiteCrawlConfig.objects.filter(website=website).all()[0]
            except IndexError:
                website_config=None

            try:
                website_sched = WebSiteCrawlSchedule.objects.filter(website=website).all()[0]
            except IndexError:
                website_sched = None

            last_crawled = website.last_crawled.strftime("%a %b %d %Y %H:%M:%S") if (website.last_crawled != None) else '<not crawled yet>'

            data = { 'website_url': website.website_url,
                     'visible_url': website.visible_url,
                     'name': website.name.strip(),
                     'last_updated': website.last_updated.strftime("%a %b %d %Y %H:%M:%S"),
                     'last_crawled': last_crawled,
                     'config_not_found': False,
                     'sched_not_found': False }

            if website_config != None:
                data['spider_type'] = website_config.spider_type
                data['seed_urls'] = website_config.seed_urls
                data['site_settings'] = website_config.site_settings

                if website_config.spider_type == 'generic':
                    data['url_patterns'] = (website_config.url_patterns, website_config.url_patterns_excl)
                    if website_config.parse_patterns != '{}':
                        data['parse_patterns'] = website_config.parse_patterns

                if website_config.spider_class != None:
                    data['spider_class'] = website_config.spider_class
                    data['class_settings'] = website_config.class_settings
            else:
                data['config_not_found'] = True 

            if website_sched != None:
                data['priority'] = website_sched.priority
                data['frequency'] = website_sched.frequency
                data['enabled'] = website_sched.enabled
            else:
                data['sched_not_found'] = True

            hits.append(data)


        return render(request, 'siteconfig/multisiteinfo.html', {'hits': hits, 'total': len(hits) })

def _crawl_stats_display(request, last_day=False, last_week=False, currently_running=False, zero_crawls=False):
    """ Show status of currently running crawls """

    statistics = []
    now = datetime.now().replace(tzinfo=None)

    if zero_crawls:
        period = '30 days'              
        stats_info = WebSiteCrawlStats.objects.filter(crawl_started__gte=datetime.now() - timedelta(hours=24*7*30), nurls=0).all()
        stats_info = filter(lambda x: x.crawl_ended != None, stats_info)
        
        # Sort according to duration
        stats_info = sorted(stats_info, key=lambda x: x.crawl_ended - x.crawl_started, reverse=True)
                            
    elif currently_running:
        stats_info = WebSiteCrawlStats.objects.filter(crawl_ended=None).all()
        for stats in stats_info:
            stat_dict = {}
            stat_dict['visible_url'] = stats.website.visible_url
            stat_dict['downloads'] = stats.nurls
            stat_dict['crawl_id'] = stats.crawl_id
            stat_dict['start_time'] = stats.crawl_started
            stat_dict['industry'] = stats.website.tag2
            if stats.error:
                stat_dict['error'] = json.dumps(stats.error)
            else:
                stat_dict['error'] = ''
            
            duration = str(stats.last_updated - stats.crawl_started)
            nhours = (stats.last_updated - stats.crawl_started).total_seconds()/3600.0
            
            # If last updated was more than 5 mins back - put this status as 'unknown'
            status = 'running'
            reported_time  = (now - stats.last_updated.replace(tzinfo=None))
            if reported_time.total_seconds() > 3600:
                print 'Skipping zombie => dead status', stat_dict['visible_url']
                # Skip this
                continue
            if reported_time.total_seconds() > 1800:
                status = 'zombie'
            elif reported_time.total_seconds() > 300:
                status = 'unknown'
            # >= 30 minutes mark this as zombie
                

            stat_dict['status'] = status
            stat_dict['rtime'] = reported_time
            stat_dict['rate'] = round(1.0*stats.nurls/nhours, 2)
            reported_time_s = str(reported_time)
            
            stat_dict['reported_time'] = reported_time_s[:reported_time_s.rindex('.')]              
            if '.' in duration:
                duration = duration[:duration.rindex('.')]
            stat_dict['duration'] = duration
            stat_dict['crawl_node_ip'] = stats.crawl_node_ip
            
            try:
                config = WebSiteCrawlConfig.objects.filter(website=stats.website).all()[0]
                stat_dict['spider_type'] = config.spider_type
                if config.spider_type == 'generic':
                    stat_dict['spider_class'] = config.spider_class
            except IndexError:
                pass

            statistics.append(stat_dict)

        data_present = len(statistics)
        statistics = sorted(statistics, key=lambda x: x['downloads'], reverse=True)
        
        return render(request, 'siteconfig/crawl_dashboard.html', {'statistics': statistics,
                                                                   'data_present': data_present,
                                                                   'running': True,
                                                                   'title': 'Showing status of currently running crawls'})
    
    elif last_day:
        period = '24 hours'
        stats_info = WebSiteCrawlStats.objects.filter(crawl_started__gte=datetime.now() - timedelta(hours=24)).all()
        print stats_info

    elif last_week:
        period = '7 days'       
        stats_info = WebSiteCrawlStats.objects.filter(crawl_started__gte=datetime.now() - timedelta(hours=24*7)).all()
        print stats_info
        
    if 1:
        for stats in stats_info:
            stat_dict = {}
            stat_dict['visible_url'] = stats.website.visible_url
            stat_dict['downloads'] = stats.nurls
            stat_dict['crawl_id'] = stats.crawl_id          
            stat_dict['start_time'] = stats.crawl_started
            stat_dict['industry'] = stats.website.tag2
            
            if stats.error:
                stat_dict['error'] = json.dumps(stats.error)
            else:
                stat_dict['error'] = ''             
            
            if stats.crawl_ended:
                duration = str(stats.crawl_ended - stats.crawl_started)
            else:
                duration = str(stats.last_updated - stats.crawl_started)
                status = 'running'
                if (now - stats.last_updated.replace(tzinfo=None)).total_seconds() > 3600*4:
                    print 'Skipping zombie => dead status', stat_dict['visible_url']
                    # Skip this
                    continue                
                if (now - stats.last_updated.replace(tzinfo=None)).total_seconds() > 1800:
                    status = 'zombie'
                elif (now - stats.last_updated.replace(tzinfo=None)).total_seconds() > 300:
                    status = 'unknown'              

                stat_dict['status'] = status

            reported_time  = now - stats.last_updated.replace(tzinfo=None)
            stat_dict['rtime'] = reported_time          
            reported_time_s  = str(now - stats.last_updated.replace(tzinfo=None))
            stat_dict['reported_time'] = reported_time_s[:reported_time_s.rindex('.')]

            if '.' in duration:
                duration = duration[:duration.rindex('.')]              
            stat_dict['duration'] = duration
            stat_dict['crawl_node_ip'] = stats.crawl_node_ip
            stat_dict['end_time'] = stats.crawl_ended
            
            try:
                config = WebSiteCrawlConfig.objects.filter(website=stats.website).all()[0]
                stat_dict['spider_type'] = config.spider_type
                if config.spider_type == 'generic':
                    stat_dict['spider_class'] = config.spider_class
            except IndexError:
                pass
            
            statistics.append(stat_dict)

        data_present = len(statistics)

        # statistics = sorted(statistics, key=lambda x: x['rtime'])
        statistics = sorted(statistics, key=lambda x: x['downloads'], reverse=True)     
        
        return render(request, 'siteconfig/crawl_dashboard.html', {'statistics': statistics,
                                                                   'data_present': data_present,
                                                                   'title': 'Showing status of crawls started in last ' + period,
                                                                   'end_time': True })
        
@login_required
def crawl_zero_crawls(request):
    """ Show crawls with zero results """

    return _crawl_stats_display(request, zero_crawls = True)

@login_required
def crawl_dashboard_running(request):
    """ Dashboard for running crawls """

    return _crawl_stats_display(request, currently_running=True)

@login_required
def crawl_dashboard_lastday(request):
    """ Dashboard for crawls started last 24 hours """

    return _crawl_stats_display(request, last_day=True)


@login_required
def crawl_dashboard_lastweek(request):
    """ Dashboard for crawls started last 7 days """

    return _crawl_stats_display(request, last_week=True)
        
@login_required
def save_website(request):
    """ Save website in POST request """

    print request.POST
    try:
        website = WebSite.objects.get(id=int(request.POST.get('website_id')))
    except Exception:
        try:
            website = WebSite.objects.filter(website_url=request.POST.get('visible_url')).all()[0]      
        except IndexError:
            return render(request, 'error.html', {'error': 'Error in save - Cannot find the website.'})
        
    website.visible_url = request.POST.get('visible_url')
    website.website_url = request.POST.get('website_url')   
    website.name = request.POST.get('name')
    website.last_updated = datetime.now()
    website.save()

    return render(request, 'saved_thanks.html')
            
@login_required
def search_edit(request):
    """ Search and edit a site """

    query = request.GET.get('q')
    print 'Query=>',query
    
    if query != None:
        try:
            website = WebSite.objects.filter(visible_url__icontains=query.strip()).all()[0]
        except IndexError:
            return render(request, 'site_not_found.html', {'site': query })

        # Edit it
        print website
        website_form = WebSiteForm(instance=website)
        return render(request, 'siteconfig/siteadd.html', {'site_add_form': website_form,
                                                           'add_title': 'Editing website ' + website.name + '...',
                                                           'edit_site': True,
                                                           'website_id': website.id,
                                                           'action': '/save_website/' })

@login_required
def crawl_config_pick(request):

    crawl_config_form = WebSiteCrawlConfigFormBasic()
    form = {'crawl_config_form': crawl_config_form}
            
    return render(request, 'siteconfig/crawlconfigpick.html', form)

@login_required
def crawl_config_search(request):

    return render(request, 'siteconfig/searchsite.html', {'action': 'edit_config_search'})

@login_required
def edit_config_search(request):
    """ Search a website, present results for edit config action """

    if request.method == 'POST':
        data = request.POST
        website_key = None
        website_keys = []
        
        for key in data:
            if key.startswith('radio_'):
                website_key = int(key.replace('radio_','').strip())
                break

        if website_key == None:
            return render(request, 'error.html', {'error': 'No website selected!'})
        else:
            website_keys.append(website_key)

        print 'Editing config ...'
        # Calling a view from another view!
        return edit_config(request, int(website_key))
        
    query = request.GET.get('q')
    print 'Query=>',query
    
    if query != None:
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
        
        if len(websites):
            # Filter out those without configuration
            websites_selected = []
            for website in websites:
                try:
                    config = WebSiteCrawlConfig.objects.filter(website=website).all()[0]
                    tag = website.tag1 if website.tag1 != None else ''
                    websites_selected.append({'name': website.name,
                                              'id': website.id,
                                              'tag': tag,
                                              'visible_url': website.visible_url,
                                              'website_url': website.website_url,
                                              'last_updated': website.last_updated,
                                              'last_crawled': website.last_crawled,
                                              'spider_type': config.spider_type,
                                              'spider_class': config.spider_class,
                                              'seed_urls': config.seed_urls})

                except IndexError:
                    pass

            if len(websites_selected) == 0:
                # Possibly first time adding configuration ?
                print 'Possibly first time config ?'
                website = websites[0]
                websites_selected.append({'name': website.name,
                                          'id': website.id,
                                          'tag': '',
                                          'visible_url': website.visible_url,
                                          'website_url': website.website_url,
                                          'last_updated': website.last_updated,
                                          'last_crawled': website.last_crawled,
                                          'spider_type': 'generic',
                                          'spider_class': None,
                                          'seed_urls': []})             
                                                  
            return render(request, 'siteconfig/siteselect.html', {'websites': websites_selected,
                                                                  'action': 'edit_config_search/'})

        else:
            return render(request, 'site_not_found.html', {'site': query })         
    
@login_required
def save_crawl_config(request):

    # <QueryDict: {u'website': [u'48'], u'class_settings': [u'{}'], u'url_patterns': [u'\\/reports\\/'], u'priority': [u'1']
    # , u'url_patterns_excl': [u'0'], u'spider_class': [u''], u'frequency': [u'30'], u'spider_type': [u'generic'], u'site_se
    # ttings': [u'{}'], u'parse_patterns': [u'{}'], u'csrfmiddlewaretoken': [u'iQznI59Hay58N9LxxT09FPrYIopbJVW5WJGFvTBZQVQ31
    # beF0neICiiajEcirZfx'], u'seed_urls': [u'["http://www.insight-corp.com"]']}>

    
    if request.POST != {}:
        f = request.POST
        class_settings = f.get('class_settings')
        url_patterns = f.get('url_patterns')
        url_patterns_excl = f.get('url_patterns_excl')
        seed_urls = f.get('seed_urls')
        site_settings = f.get('site_settings')
        spider_class = f.get('spider_class')
        spider_type = f.get('spider_type')
        website_id = int(f.get('website'))
        priority = int(f.get('priority'))
        frequency = int(f.get('frequency'))

        # Load websitet
        try:
            website = WebSite.objects.get(id=website_id)
        except Exception, e:
            print e
            render(request, 'error.html', {'error': 'Website with id %d not found.' % website_id})

        try:
            config = WebSiteCrawlConfig.objects.filter(website=website).all()[0]
        except IndexError:
            # Create fresh
            print 'Creating new configuration for',website
            config = WebSiteCrawlConfig()

        config.url_patterns = url_patterns
        config.url_patterns_excl = int(url_patterns_excl)
        config.last_updated = datetime.now()
        config.spider_class = spider_class
        config.spider_type = spider_type
        config.website_id = website_id

        try:
            config.class_settings = json.loads(class_settings)
        except Exception, e:
            print e
            return render(request, 'error.html', {'error': 'Error parsing class settings - ' + str(e)})
        
        try:
            config.seed_urls = json.loads(seed_urls)
        except Exception, e:
            print e
            return render(request, 'error.html', {'error': 'Error parsing seed URLs - ' + str(e)})

        try:
            config.site_settings = json.loads(site_settings)
        except Exception, e:
            print e
            return render(request, 'error.html', {'error': 'Error parsing site settings  - ' + str(e)})         
        
        config.save()

        try:
            sched = WebSiteCrawlSchedule.objects.filter(website=website).all()[0]
        except IndexError:
            # Create fresh
            print 'Creating new scheduler configuration for',website
            sched = WebSiteCrawlSchedule()           
            
            
        sched.priority = priority
        sched.frequency = frequency
        sched.last_updated = datetime.now()        
        sched.website_id = website_id

        sched.save()
        
        return render(request, 'success.html', {'message': 'Crawl configuration is saved.'})

    else:
        return render(request, 'error.html', {'error': 'Empty POST request!'})
            
@login_required
def edit_config(request, website_id):
    form = {}

    website_id = int(website_id)
    website = WebSite.objects.get(id=website_id)
    print website
    new = False
    
    try:
        config = WebSiteCrawlConfig.objects.filter(website=website).all()[0]
        crawl_config_form = WebSiteCrawlConfigForm(instance=config)
    except IndexError:
        new = True
        crawl_config_form = WebSiteCrawlConfigForm()
        crawl_config_form.fields['website'].initial=website
        print 'No website configuration exists for',website,'creating new...'       

    try:
        sched = WebSiteCrawlSchedule.objects.filter(website=website).all()[0]
        crawl_schedule_form = WebSiteCrawlScheduleForm(instance=sched)
    except IndexError:        
        crawl_schedule_form = WebSiteCrawlScheduleForm()
        print 'No website schedule configuration exists for',website,'creating new...'

    form = {'crawl_config_form': crawl_config_form,
            'crawl_schedule_form': crawl_schedule_form,
            'website': website.name,
            'site_new': new
            }
    
    return render(request, 'siteconfig/crawlconfig.html', form)


def thanks(request):
    return render(request, 'siteconfig/thanks.html')


@login_required
def home(request):
    """ Home view """

    return render(request, 'home.html')
    
def verify_secure_token(token, ip, handshake=False):
    """ Verify secure token """
    
    if token == None:
        return HttpResponse('Forbidden', status=403)

    try:
        # Unquote the token
        token_u = str(urllib.unquote(token).strip())
        print 'TOKEN UNQUOTED=>',token_u
        # Check for global tokens
        if handshake:
            tok = SHARED_TOKEN
        else:
            tok = global_tokens.get(ip)
            print 'GLOBAL TOKEN=>',tok
            if tok == None:
                print 'Using shared token'
                tok = SHARED_TOKEN
            else:
                print 'Using session token for',ip,'=>',tok

        if not bcrypt.checkpw(tok, token_u):
            # import pdb; pdb.set_trace()
            return HttpResponse('Forbidden - Wrong Token', status=403)
    except Exception:
        return HttpResponse('Forbidden - Wrong Token', status=503)

    return None
    
def get_crawl(request):
    """ Callback for popping the next crawl config from Redis and returning
        to the caller. """

    timeout = int(request.GET.get('timeout', 5))
    token = request.GET.get('token')
    verify = verify_secure_token(token, request.META.get('HTTP_X_FORWARDED_FOR', '127.0.0.1'))

    if verify != None:
        return verify

    data = redis_q.cpop(timeout)
    if data != None:
        print 'Crawl config obtained =>', data
        return HttpResponse(data[1], content_type='application/json')
    else:
        return HttpResponse('{}', content_type='application/json')

def handshake(request):
    """ Handshake protocol for crawlers """

    token = request.GET.get('token')
    memory = request.GET.get('memory',0)
    
    verify = verify_secure_token(token, request.META.get('HTTP_X_FORWARDED_FOR', '127.0.0.1'), handshake=True)

    if verify != None:
        return verify

    # generate new token and save it against the IP
    session_token = uuid.uuid4().hex
    print 'Created token',session_token
    crawler_ip = request.META.get('HTTP_X_FORWARDED_FOR', '127.0.0.1')

    # Save it
    wtoken = WebCrawlSessionToken(session_token=session_token,
                                  crawl_node_ip=crawler_ip,
                                  created_at=datetime.now())
    wtoken.save()

    try:
        most_recent_status = WebCrawlNodeStatus.objects.filter(crawl_node_ip=crawler_ip).order_by('-last_updated')[0]
        most_recent_status.memory = float(memory)
        most_recent_status.save()
    except IndexError:
        pass
        
    # Global token dictionary
    global_tokens[crawler_ip] = str(session_token)

    return HttpResponse(json.dumps({'session_token': session_token}),
                        status=200)

def parse_uploaded_file_extended(fileobj, allow_update=False, spider_type='org', tag1=None, tag2=None, tag3=None):
    """ Parse uploaded file in extended format """

    # csv
    count_n, count_u, count_c = 0, 0, 0
    websites_new, websites_there, website_configs, website_configs_u = [], [], [], []

    site_dict = {}
        
    if fileobj._name.endswith('.csv'):
        for idx,line in enumerate(fileobj):
            # First line always skipped
            if idx == 0: continue
            if line.strip()=='': continue

            visible_url = ''
            regex1, regex2, regex3 = '', '', ''
            seed_url1, seed_url2, seed_url3 = '', '', ''
            ctype1, ctype2, ctype3, ctype4, ctype5 = '','','','',''

            print line
            items = line.split(',')
            if len(items) >= 12:
                # Ignore yscore at end
                website_url, visible_url, seed_url1, seed_url2, seed_url3, ctype1, ctype2, ctype3, ctype4, ctype5,dummy1,dummy2 = items[:12]
            elif len(items) == 11:
                # Ignore yscore at end
                website_url, visible_url, seed_url1, seed_url2, seed_url3, ctype1, ctype2, ctype3, ctype4, ctype5,dummy1 = items
            elif len(items) == 10:
                website_url, visible_url, seed_url1, seed_url2, seed_url3, ctype1, ctype2, ctype3, ctype4, ctype5 = items
            elif len(items) == 9:
                website_url, visible_url, seed_url1, seed_url2, seed_url3, ctype1, ctype2, ctype3, ctype4 = items
            elif len(items) == 8:           
                website_url, visible_url, seed_url1, seed_url2, seed_url3, ctype1, ctype2, ctype3 = items
            elif len(items) == 7:           
                website_url, visible_url, seed_url1, seed_url2, seed_url3, ctype1, ctype2 = items
            elif len(items) == 6:           
                website_url, visible_url, seed_url1, seed_url2, seed_url3, ctype1 = items
            elif len(items) == 5:           
                website_url, visible_url, seed_url1, seed_url2, seed_url3 = items               
            elif len(items) == 1:
                print 'Single line input!',line,'...'
                website_url = visible_url = items[0]
            else:
                print 'Error in parsing line, wrong number of items',len(items)
                continue


            if visible_url.strip() == '':
                visible_url = website_url
                
            try:
                visible_url = visible_url.decode('utf-8', errors='ignore').strip()
                website_url = website_url.decode('utf-8', errors='ignore').strip()               
            except (UnicodeDecodeError, UnicodeEncodeError), e:
                print 'Error parsing',line,'...'
                # import pdb;pdb.set_trace()
                # raise
                continue
                
            # We remove any http or https from the URLs
            if 'http' in website_url:
                website_url = website_url.replace('http://','').replace('https://','').strip()

            if 'http' in visible_url:
                visible_url = visible_url.replace('http://','').replace('https://','').strip()              

            if visible_url in site_dict or visible_url.strip() in site_dict:
                print 'Skipping duplicate',visible_url,'...'
                continue

            name = make_site_name(website_url)
            print 'NAME FOR',website_url,'=>',name
            if name == None:
                continue

            if len(name)>128:
                print 'Trimming name to',name[:127]
                name = name[:127]
            
            site_dict[visible_url] = 1
            site_dict[visible_url.strip()] = 1

            website_exists = False
            website = None
            
            for url in (visible_url, visible_url.strip()):
                try:
                    website_current = WebSite.objects.filter(visible_url=url).all()[0]
                    website = website_current
                    
                    website_exists = True                   
                    if allow_update=='on':
                        website_current.website_url = website_url.strip()
                        website_current.name = name
                        website_current.tag1 = tag1
                        website_current.tag2 = tag2
                        website_current.tag3 = tag3

                        website_current.content_type1 = ctype1
                        website_current.content_type2 = ctype2
                        website_current.content_type3 = ctype3
                        website_current.content_type4 = ctype4
                        website_current.content_type5 = ctype5
                        
                        websites_there.append(website_current)
                        break
                except IndexError:
                    pass
                        
            if not website_exists:
                print 'Adding',visible_url,'...'
                website = WebSite(website_url=website_url.strip(),
                                  visible_url=visible_url.strip(),
                                  name=name,
                                  tag1=tag1, tag2=tag2, tag3=tag3,
                                  content_type1=ctype1,content_type2=ctype2,
                                  content_type3=ctype3,content_type4=ctype4,
                                  content_type5=ctype5)
                                  
                websites_new.append(website)

            # Add configuration too
            seed_urls = []
            
            for surl in (seed_url1, seed_url2, seed_url3):
                if surl != '':
                    seed_urls.append(surl.strip())

            regexes = []
            # Modify regular expressions
            for regex in (regex1, regex2, regex3):
                regex = regex.strip()
                if regex:
                    # Replace * with .*
                    # Replace on left with [^\.]*
                    if asterisk_begin_re.match(regex):
                        regex = asterisk_begin_re.sub('/[^.]*', regex)
                    if asterisk_end_re.search(regex):
                        regex = asterisk_end_re.sub('.*/', regex)                        
                        
                    regexes.append(regex.strip())
                    
            regex_string = '|'.join(regexes)

            # If we are using regexes, make the spider generic type
            if len(regexes):
                print 'Using regular expressions, switching to generic spider'
                spider_type = 'generic'
                if regex_string[-1] != '/':
                    regex_string += '/'
                
            try:
                config_existing = WebSiteCrawlConfig.objects.filter(website=website).all()[0]
                config = config_existing
                if allow_update:
                    config.url_patterns = regex_string
                    config.url_patterns_excl = 0
                    config.seed_urls = seed_urls
                    config.spider_type = spider_type
                    website_configs_u.append(config)
            except IndexError:
                config = WebSiteCrawlConfig(url_patterns=regex_string,
                                            url_patterns_excl=0,
                                            seed_urls = seed_urls,
                                            spider_type = spider_type,
                                            website = website)

                website_configs.append(config)


    if len(websites_new):
        print 'Creating websites...'
        count_n = len(WebSite.objects.bulk_create(websites_new))
        
    if len(websites_there):
        print 'Updating websites...',len(websites_there)
        count_u = WebSite.objects.bulk_update(websites_there)
            
    if len(website_configs):
        # Now create others
        for config in website_configs:
            visible_url = config.website.visible_url
            config.website = WebSite.objects.filter(visible_url = visible_url).all()[0]               

        count_c = len(WebSiteCrawlConfig.objects.bulk_create(website_configs))
        print 'Created',count_c,'configuration objects.'

    if len(website_configs_u):
        print 'Updating website configs',len(website_configs_u)
        WebSiteCrawlConfig.objects.bulk_update(website_configs_u)       

    total = count_u + count_n + count_c
    if total:
        return count_n, count_u, count_c, True
    
    return 0, 0, 0,True


def parse_uploaded_file(fileobj, allow_update=False, tag1=None, tag2=None, tag3=None):
    """ Parse uploaded file """

    # csv
    count_n, count_u = 0, 0
    websites_new, websites_there = [], []
    # import pdb; pdb.set_trace()

    site_dict = {}
        
    if fileobj._name.endswith('.csv'):
        for idx,line in enumerate(fileobj):
            # First line always skipped
            if idx == 0: continue
            if line.strip()=='': continue
            name = None

            try:
                website_url, visible_url, name = line.split(',')
            except ValueError:
                try:
                    website_url, visible_url = line.split(',')
                except ValueError:
                    # Just take it as one
                    website_url, visible_url = line.strip(), ''
                    print 'Taking entire line as website URL',line

            if website_url.strip() == '' and visible_url.strip() == '':
                print 'Skippiing empty line'
                continue

            # Fix: If website URL or visible URL has path components, we should not use them...
            
            if visible_url.strip() == '':
                visible_url = website_url
                
            try:
                visible_url = visible_url.decode('utf-8', errors='ignore').strip()
                website_url = website_url.decode('utf-8', errors='ignore').strip()               
            except (UnicodeDecodeError, UnicodeEncodeError), e:
                print 'Error parsing',line,'...'
                # import pdb;pdb.set_trace()
                # raise
                continue
                
            # We remove any http or https from the URLs
            if 'http' in website_url:
                website_url = website_url.replace('http://','').replace('https://','').strip()

            if 'http' in visible_url:
                visible_url = visible_url.replace('http://','').replace('https://','').strip()              

            if visible_url in site_dict or visible_url.strip() in site_dict:
                print 'Skipping duplicate',visible_url,'...'
                continue

            if name == None:
                name = make_site_name(website_url)

            if name == None:
                print 'Skipping',visible_url,'as name is None'
                continue
                
            site_dict[visible_url] = 1
            site_dict[visible_url.strip()] = 1          
                
            # Add website - if does not exist
            print 'Checking for',visible_url,'...'
            # import pdb;pdb.set_trace()
            website_exists = False
            
            for url in (visible_url, visible_url.strip()):
                try:
                    website_current = WebSite.objects.filter(visible_url=url).all()[0]
                    website_exists = True                   
                    if allow_update=='on':
                        website_current.website_url = website_url.strip()
                        website_current.name = name
                        website_current.tag1 = tag1
                        website_current.tag2 = tag2
                        website_current.tag3 = tag3                     
                        websites_there.append(website_current)
                        break
                except IndexError:
                    pass
                        
            if not website_exists:
                print 'Adding',visible_url,'...'
                websites_new.append(WebSite(website_url=website_url.strip(),
                                            visible_url=visible_url.strip(),
                                            name=name,
                                            tag1=tag1, tag2=tag2, tag3=tag3))
    if len(websites_new):
        print 'Creating websites...'
        count_n = len(WebSite.objects.bulk_create(websites_new))
        
    if len(websites_there):
        print 'Updating websites...',len(websites_there)
        count_u = WebSite.objects.bulk_update(websites_there)

    total = count_u + count_n
    if total:
        return count_n, count_u, True
    
    return 0, 0, True

@login_required
def upload_sites(request):
    """ Upload websites via a CSV or Excel file """

    if request.method == 'POST':
        print request.POST
        allow_update = request.POST.get('allow_update', 'off')
        extended_format = request.POST.get('extended_format', 'off')
        
        form = DocumentForm(request.POST, request.FILES)
        print 'Posted form =>',form
        tag1, tag2, tag3 = map(lambda x: request.POST[x], ('tag1','tag2','tag3'))
        
        if form.is_valid():
            if extended_format:
                count_n, count_u, count_c, status = parse_uploaded_file_extended(request.FILES['document'], allow_update, 'org', tag1, tag2, tag3)
            else:
                count_n, count_u, status = parse_uploaded_file(request.FILES['document'], allow_update, tag1, tag2, tag3)
                
            form.save()
            
            if status:
                if extended_format:                
                    return render(request, 'success.html',
                                  {'message': 'File uploaded successfully - %d sites created, %d sites updated, %d configs created' % (count_n,
                                                                                                                                       count_u,
                                                                                                                                       count_c)})
                else:
                    return render(request, 'success.html',
                                  {'message': 'File uploaded successfully - %d records created, %d updated' % (count_n,
                                                                                                               count_u)})               
            else:
                return render(request, 'error.html', {'error': 'File upload failed with errors.'})
    else:
        form = DocumentForm()

    return render(request, 'siteconfig/upload_file.html', {'upload_form': form })
            
@csrf_exempt
def update_crawl_status(request):
    """ Update crawl status """


    try:
        token = request.POST.get('token')
        verify = verify_secure_token(token, request.META.get('HTTP_X_FORWARDED_FOR','127.0.0.1'))

        if verify != None:
            return verify
        
        website_url = request.POST.get('website_url')
        visible_url = request.POST.get('visible_url')
        
    except Exception, e:
        return HttpResponse('Error processing request => ' + str(e), status=503)

    try:
        website = WebSite.objects.filter(visible_url=visible_url,
                                         website_url=website_url).all()[0]
        # Update the last crawled timestamp
        website.last_crawled = datetime.now()
        website.save()
        print 'Updated last crawled timestamp'
    except Exception, e:
        return HttpResponse('Error processing request => ' + str(e), status=503)        
    
    return HttpResponse('OK', status=200)

@login_required
def crawl_node_status(request):
    """ Report crawl node status """

    
    crawl_ips = []
    for node in WebCrawlNodeStatus.objects.distinct('crawl_node_ip'):
        crawl_ips.append(node.crawl_node_ip)

    now = datetime.now().replace(tzinfo=None)
    
    node_status = []
    status_totals = defaultdict(int)
    
    # Now query via IP for crawls
    for node_ip in crawl_ips:
        # Current active crawls
        info = {"node_ip": node_ip}
        
        for status in ('running','finished','unknown'):
            # For running the status should be updated in last 1 minute
            if status == 'running':
                query = WebCrawlNodeStatus.objects.filter(crawl_node_ip=node_ip, status=status,
                                                          last_updated__gt=(now - timedelta(seconds=60)))
                value = query.count()
            else:
                value = WebCrawlNodeStatus.objects.filter(crawl_node_ip=node_ip, status=status).count()

            info[status] = value
            status_totals[status] += value

        nurls = sum(WebSiteCrawlStats.objects.filter(crawl_node_ip=node_ip, nurls__gt=0).values_list('nurls', flat=True))
        # In millions of URLs
        nurls_m = round(1.0*nurls/1000000.0, 2)
        info['nurls'] = nurls_m
        status_totals['nurls'] += nurls_m
            
        # Most recently updated timestamp
        most_recent_status = WebCrawlNodeStatus.objects.filter(crawl_node_ip=node_ip).order_by('-last_updated')[0]
        recent_timestamp = most_recent_status.last_updated
        memory = most_recent_status.memory
        
        info['recent'] = recent_timestamp
        info['memory'] = round(memory, 2)
        # If recent timestamp is within the last 15 minutes - we can call this node as active
        if (now - recent_timestamp.replace(tzinfo=None)) < timedelta(seconds=900):
            info['active'] = 1
        else:
            info['active'] = 0

        node_status.append(info)

    # Sort according to active
    node_status = sorted(node_status, key=lambda x: x['active'])
                         
    return render(request, 'siteconfig/nodestatus.html', {'node_status': node_status,
                                                          'total': status_totals })
        

@csrf_exempt
def get_crawl_data(request):
    """ Get completed crawls information (filepaths) on nodes """

    print request.GET
    token = request.GET.get('token')

    timeout = int(request.GET.get('timeout', 5))
    node_ip = request.META.get('HTTP_X_FORWARDED_FOR','127.0.0.1')
    verify = verify_secure_token(token, node_ip)

    if verify != None:
        print '\tToken verification failed!',verify
        return verify

    # Return data from the redis queue
    data = redis_q.lpop(timeout)
    if data != None:
        print 'File data obtained =>', data
        return HttpResponse(data[1], content_type='application/json')
    else:
        return HttpResponse('{}', content_type='application/json')    
    
@csrf_exempt
def update_crawl_stats(request):
    """ Update statistics of crawls to DB """


    # import pdb;pdb.set_trace()
    print request.POST

    now = datetime.now().replace(tzinfo=None)
    
    try:
        token = request.POST.get('token')
        node_ip = request.META.get('HTTP_X_FORWARDED_FOR','127.0.0.1')
        verify = verify_secure_token(token, node_ip)

        if verify != None:
            print '\tToken verification failed!',verify
            return verify
        
        website_url = request.POST.get('website_url')
        crawl_id = request.POST.get('crawl_id')
        visible_url = request.POST.get('visible_url')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        updated_time = request.POST.get('updated_time')
        downloads = request.POST.get('downloads', 0)
        error = request.POST.get('error', None)
        freemem = request.POST.get('memory', None)
        fileinfo = json.loads(request.POST.get('fileinfo', '{}'))
        # import pdb; pdb.set_trace()
        
        # If file info is provided, it means files are generated for this crawl
        # Put this in redis
        if fileinfo and fileinfo.get('path'):
            fileinfo['node_ip'] = node_ip
            fileinfo['timestamp'] = now.strftime("%Y-%m-%d %H:%M:%S")
            print 'Files generated for crawl=>',crawl_id,fileinfo
            print 'Pushing information to listener queue'
            redis_q.lpush(json.dumps(fileinfo))
                
    except Exception, e:
        return HttpResponse('Error processing request => ' + str(e), status=503)

    # If this was a non-selenium crawl and had a download count of zero - retry with selenium
    # enabled.
    
    try:
        website = WebSite.objects.filter(visible_url=visible_url,
                                         website_url=website_url).all()[0]

        if downloads == 0:
            try:
                website_config = WebSiteCrawlConfig.objects.filter(website=website).all()[0]
                # Check site settings
                site_settings= website_config.site_settings
                if site_settings.get('selenium') == False:
                    print 'Zero downloads and no selenium enabled, re-trying crawl with selenium enabled! =>',website
                    website_config.site_settings['selenium'] = True
                    website_config.save()
                    
                    webconfig_json = utils.website_config_to_json(website)
                    print 'Adding website for crawl',website.website_url,'...'
                    json_s = json.dumps(webconfig_json)
                    print json_s
                    redis_q.cpush(json_s)
                    website.last_checked = datetime.now()
                    website.save()
                else:
                    print 'Zero downloads but selenium was enabled, so doing nothing =>',website
            except IndexError:
                pass
        
        try:
            website_stats = WebSiteCrawlStats.objects.filter(crawl_id=crawl_id).all()[0]
        except IndexError:
            website_stats = WebSiteCrawlStats()
            website_stats.crawl_id = crawl_id

        website_stats.website = website
        website_stats.crawl_started = datetime.fromtimestamp(int(start_time))
        if updated_time != None:
            website_stats.last_updated = datetime.fromtimestamp(int(updated_time))
        else:
            website_stats.last_updated = website_stats.crawl_started
            
        if end_time != None:
            website_stats.crawl_ended = datetime.fromtimestamp(int(end_time))
            
        website_stats.nurls = int(downloads)
        if error != None:
            website_stats.error = json.loads(error)
            
        # Assuming we are always behind a reverse proxy
        node_ip = request.META.get('HTTP_X_FORWARDED_FOR', '127.0.0.1')
        website_stats.crawl_node_ip = node_ip
        website_stats.save()

        print 'Updated crawl stats for',visible_url,'...'

        # Update node status
        # Query node status element within last 5 minutes
        try:
            node_stats = WebCrawlNodeStatus.objects.filter(crawl_node_ip=node_ip,
                                                           last_updated__gte=now - timedelta(seconds=300),
                                                           crawl_id=crawl_id).all()[0]
            print 'Updating node stats =>',node_stats
            # Is it the same crawl ?
            node_stats.last_updated = now
            node_stats.memory = freemem
            # Did crawl end ?
            if end_time != None:
                node_stats.status = 'finished'
                
            node_stats.save()
        except IndexError:
            node_stats = WebCrawlNodeStatus(status='running', crawl_node_ip=node_ip, crawl_id=crawl_id, memory=freemem)
            print 'Saving fresh node status',node_stats
            node_stats.save()
            
    except Exception, e:
        # raise
        return HttpResponse('Error processing request => ' + str(e), status=503)        
    
    return HttpResponse('OK', status=200)

@login_required
def schedule_crawl(request):
    """ Schedule crawl of a website """

    return render(request, 'siteconfig/searchsite.html', {'action': 'queue_crawl'}) 

@login_required
def schedule_crawl_bulk(request):
    """ Schedule crawl of multiple websites at one go """

    return render(request, 'siteconfig/searchsite.html', {'action': 'queue_crawl',
                                                          'multiple': True })

@login_required
def queue_crawl(request):
    """ Queue crawl of site """

    if request.method == 'POST':
        data = request.POST
        website_key = None
        website_keys = []
        
        for key in data:
            if key.startswith('radio_'):
                website_key = int(key.replace('radio_','').strip())
                break

        if website_key == None:
            # Multiple sites ?
            for key in data:
                if key == 'check_all': continue
                if key.startswith('check_'):
                    website_keys.append(int(key.replace('check_','').strip()))
                    
            if len(website_keys)==0:
                return render(request, 'error.html', {'error': 'No website selected!'})
        else:
            website_keys.append(website_key)

        for wkey in website_keys:
            website = WebSite.objects.get(id=wkey)
            tag = data.get('tag_' + str(wkey), '')
            print 'TAG=>',tag
        
            print website
            webconfig_json = utils.website_config_to_json(website)
            # Add tag
            if tag:
                webconfig_json['tag'] = tag
            print 'Adding website for crawl',website.website_url,'...'
            json_s = json.dumps(webconfig_json)
            print json_s
            redis_q.cpush(json_s)
            website.last_checked = datetime.now()
            website.save()
        if website_key != None:
            return render(request, 'success.html', {'message': 'Crawl scheduled for %s' % website.visible_url})
        elif len(website_keys):
            return render(request, 'success.html', {'message': 'Crawl scheduled for %d websites' % len(website_keys)})          
        
    query = request.GET.get('q')
    print 'Query=>',query
    # print request.GET
    multiple = request.GET.get('multiple')
    print  multiple
    
    if query != None:
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
        
        if len(websites):
            # Filter out those without configuration
            websites_selected = []
            for website in websites:
                try:
                    config = WebSiteCrawlConfig.objects.filter(website=website).all()[0]
                    tag = website.tag1 if website.tag1 != None else ''
                    websites_selected.append({'name': website.name,
                                              'id': website.id,
                                              'tag': tag,
                                              'visible_url': website.visible_url,
                                              'website_url': website.website_url,
                                              'last_updated': website.last_updated,
                                              'last_crawled': website.last_crawled,
                                              'spider_type': config.spider_type,
                                              'spider_class': config.spider_class,
                                              'seed_urls': config.seed_urls})

                except IndexError:
                    pass
                
            return render(request, 'siteconfig/siteselect.html', {'websites': websites_selected,
                                                                  'action': 'queue_crawl/',
                                                                  'multiple': multiple })
        else:
            return render(request, 'site_not_found.html', {'site': query })         

def load_sessions():
    """ Load webcrawl sessions into global config """

    global global_tokens

    tok_dict = {}
    sessions = WebCrawlSessionToken.objects.order_by('created_at').all()

    for session in sessions:
        tok_dict[session.crawl_node_ip] = str(session.session_token)

    global_tokens = tok_dict

def fetch_elastic_stats(filename):
    """ Fetch elastic search stats and save to filename """

    try:
        data = requests.get('http://elastic-server/_stats').content
        open(filename, 'w').write(data)

        return data
    except Exception, e:
        print 'Error fetching stats =>',e
        

@login_required
def elastic_index_stats(request):
    """ Return stats on Elastic Search """
    
    content = fetch_elastic_stats('elastic.json')

    try:
        stats = json.loads(content)

        index_size = stats['_all']['primaries']['docs']['count']
        index_del = stats['_all']['primaries']['docs']['deleted']       
        return render(request, 'siteconfig/elasticstats.html', {'index_size': index_size,
                                                                'index_del': index_del})
    except Exception, e:
        print 'Error parsing JSON stats',e

        

@login_required
def elastic_index_stats_download(request):
    """ Download elastic stats as JSON """
    
    content = fetch_elastic_stats('elastic.json')
    if content != None:
        response = HttpResponse(open('elastic.json', 'r'),content_type = 'application/json; charset=utf8')
        response['Content-Disposition'] = "attachment; filename=elastic.json"
        
        return response
    else:
        return render(request, 'error.html', {'error': 'Error in downloading ElasticSearch stats!'})        
        
