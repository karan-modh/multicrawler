"""crawlconfig URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from siteconfig import views
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.conf.urls.static import static

urlpatterns = [
    url(r'^accounts/login/', auth_views.login, name='login'),
    url(r'^accounts/logout/', auth_views.logout, {'next_page': '/'}, name='logout'),
    url(r'^admin/logout/$', auth_views.logout,
        {'next_page': '/'}),
    url(r'^admin/', admin.site.urls),
    url(r'^addsite/', views.site_add, name='site_add'),
    url(r'^editsite/search_edit', views.search_edit, name='search_edit'),       
    url(r'^editsite/', views.site_edit, name='site_edit'),
    url(r'^viewsite/site_info', views.site_info, name='site_info'),         
    url(r'^viewsite/', views.site_view, name='site_view'),
    url(r'^save_website/', views.save_website, name='save_website'),
    url(r'^uploadsites/', views.upload_sites, name='upload_sites'),
    url(r'^save_crawl_config/', views.save_crawl_config, name='save_crawl_config'),       
    url(r'^$', views.home, name='home'),    
    # url(r'^addsiteconfig/', views.crawl_config_pick, name='crawl_config_pick'),
    url(r'^addsiteconfig/edit_config_search', views.edit_config_search, name='edit_config_search'),     
    url(r'^addsiteconfig/', views.crawl_config_search, name='crawl_config_search'),
    url(r'^editsiteconfig/(?P<website_id>\d+)/$', views.edit_config, name='crawl_config_edit'), 
    url(r'^thanks/', views.thanks, name='thanks_url'),
    url(r'^schedulecrawl/queue_crawl', views.queue_crawl, name='queue_crawl'),
    url(r'^schedulecrawl/queue_crawl/', views.queue_crawl, name='queue_crawl'),
    url(r'^schedulecrawlbulk/queue_crawl', views.queue_crawl, name='queue_crawl'),
    url(r'^schedulecrawlbulk/queue_crawl/', views.queue_crawl, name='queue_crawl'),         
    url(r'^schedulecrawl/', views.schedule_crawl, name='queue_crawl'),
    url(r'^schedulecrawlbulk/', views.schedule_crawl_bulk, name='queue_crawl_bulk'),  
    url(r'^get_crawl/', views.get_crawl, name='get_crawl_config'),
    url(r'^get_crawl_data/', views.get_crawl_data, name='get_crawl_data'), 
    url(r'^handshake/', views.handshake, name='handshake'),  
    url(r'^crawlsrunning/', views.crawl_dashboard_running, name='crawls_running'),
    url(r'^crawlslastday/', views.crawl_dashboard_lastday, name='crawls_lastday'),
    url(r'^crawlslastweek/', views.crawl_dashboard_lastweek, name='crawls_lastweek'),        
    url(r'^update_crawl_status/', views.update_crawl_status, name='update_crawl_status'),
    url(r'^update_crawl_stats/', views.update_crawl_stats, name='update_crawl_stats'),
    url(r'^nodestatus/', views.crawl_node_status, name='crawl_node_status'),
    url(r'^zerocrawls/', views.crawl_zero_crawls, name='crawl_zero_crawls'),
    url(r'^indexstats/', views.elastic_index_stats, name='elastic_index_stats'),
    url(r'^downloadindexstats/', views.elastic_index_stats_download, name='elastic_index_stats_download')     
    
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Load the tokens
# views.load_sessions()
