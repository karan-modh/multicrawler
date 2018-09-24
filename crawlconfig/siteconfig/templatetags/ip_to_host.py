from django.template import Library
import socket

register = Library()

def ip_to_host(host):
    return socket.gethostbyaddr(host)[0]

register.filter('ip_to_host', ip_to_host)
