#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import webapp2

from parser import *

class FlushMemcachePage(webapp2.RequestHandler):
    def get(self):
        memcache.flush_all()
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("flushing memcache done!")

class MainPage(webapp2.RequestHandler):
    def get(self):
        path = os.path.join(os.path.split(__file__)[0], 'index.html')
        html = open(path, 'r').read()
        self.response.out.write(html)

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/events', EventsPage),
                               ('/event_info', EventInfoPage),
                               ('/top_events', TopEvents),
                               ('/place_info', PlaceInfoPage),
                               ('/places', PlacesPage),
                               ('/photos', Photos),
                               ('/flush_memcache', FlushMemcachePage)],
                              debug=True)