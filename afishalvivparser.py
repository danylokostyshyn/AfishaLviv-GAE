#!/usr/bin/python
# -*- coding: utf-8 -*-

import urllib
import datetime
import webapp2
import logging

from lxml import html
from lxml.etree import tostring

from google.appengine.ext import db
from google.appengine.api import taskqueue
from google.appengine.api import memcache
from django.utils import simplejson

import re

def _callback(matches):
    id = matches.group(1)
    try:
        return unichr(int(id))
    except:
        return id

def decode_unicode_references(data):
    return re.sub("&#(\d+)(;|(?=\s))", _callback, data)

class EventsPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        
        date = self.request.query_string
        
        items_json = memcache.get(date)
        if items_json is not None:
            self.response.out.write(items_json)
        else:
            items_json = self.getEventsByDate(date)
            memcache.add(date, items_json, 60*60*3)
            self.response.out.write(items_json)

    def getEventsByDate(self, date):
        events_page_url = urllib.urlopen("http://afishalviv.net/page/events/" + date)
        html_page = html.parse(events_page_url)
        root = html_page.getroot()
        events_list_liTags = root.xpath("/html/body[@class='yui-skin-sam']/div[@id='allWrap']/div[@class='contentWrap']/div[@class='col-2a-l']/div[@class='playbill']/div[@class='textBox grey']/div[@class='inside']/ul[@id='event_list']/li")
        
        items = []
        for liTag in events_list_liTags:
            try:
                current_date = date
                current_title = unicode(liTag.xpath("h3/a")[0].text_content())

                current_url = unicode(liTag.xpath("h3/a/@href")[0])
                current_event_type = unicode(liTag.xpath("@class")[0])

                #concerts концерти і свята
                #exhibitions виставки
                #cinema кіно
                #parties вечірки
                #performance спектаклі
                #presentations презентації та інше

                if current_event_type == "concerts": current_event_type = "concert"
                elif current_event_type == "exhibitions": current_event_type = "exhibition"
                elif current_event_type == "cinema": current_event_type = "cinema"
                elif current_event_type == "parties": current_event_type = "party"
                elif current_event_type == "performance": current_event_type = "performance"
                elif current_event_type == "presentations": current_event_type = "presentation"

                current_desc = unicode(liTag.xpath("p[@class='desc']")[0].text_content())
                current_simage_url = "http://afishalviv.net/" +  unicode(liTag.xpath("a[@class='thumb']/img/@src")[0])
                
                current_place_url = "null"
                current_place_title = "null" 
                try: 
                    current_place_url = unicode(liTag.xpath("p[@class='location']/a/@href")[0])
                    current_place_title = unicode(liTag.xpath("p[@class='location']/a")[0].text_content())
                except: 
                    current_place_url = "null"
                    current_place_title = "null" 
                
                current_event = {"date":current_date, 
                                "title":current_title, 
                                "url":current_url, 
                                "event_type":current_event_type, 
                                "desc":current_desc, 
                                "simage_url":current_simage_url, 
                                "place_url":current_place_url,
                                "place_title":current_place_title}
                
                items.append(current_event)
            except: 
                logging.info("no events: %s", events_page_url)

        items_json = simplejson.dumps(items, ensure_ascii=False, indent=4, sort_keys=True)

        return items_json


class EventInfoPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        
        event_url = self.request.query_string
        
        event_info_json = memcache.get(event_url)
        if event_info_json is not None:
            self.response.out.write(event_info_json)
        else: 
            event_info_json = self.getEventExtendedInfo(event_url)
            memcache.add(event_url, event_info_json, 60*60*3)
            self.response.out.write(event_info_json)

    def getEventExtendedInfo(self, event_url):
        logging.info("event url:%s", event_url)

        url = urllib.urlopen(event_url)
        html_page = html.parse(url)
        root = html_page.getroot()

        try:
            eventTag = root.xpath("/html/body[@class='yui-skin-sam']/div[@id='allWrap']/div[@class='contentWrap']/div[@class='col-2a-l']/div[@class='event']")[0]
             
            current_title = unicode(eventTag.xpath("h1")[0].text_content())

            current_bimage_url = "http://afishalviv.net/" +  unicode(eventTag.xpath("div[@class='thumb']/img/@src")[0])
            try: current_date_interval = unicode(eventTag.xpath("h2/span[@class='date']")[0].text_content())
            except: current_date_interval = "null"
            try: current_worktime = unicode(eventTag.xpath("h2/span[@class='worktime']")[0].text_content())
            except: current_worktime = "null"
            
            try: 
                if (eventTag.xpath("div/table/tr/td")[0].text_content() == "Вартість:".decode("utf-8")):
                    current_price = unicode(eventTag.xpath("div/table/tr/td")[1].text_content())
                else: current_price = "null"
            except: current_price = "null"
            
            #setting place info
            try: 
                current_place_url = unicode(eventTag.xpath("h2/span[@class='place']/a/@href")[0])
                current_place_title = unicode(eventTag.xpath("h2/span[@class='place']")[0].text_content())
                current_place_address = unicode(eventTag.xpath("h2/span[@class='place']")[1].text_content()[:-1]) #remove last char ")"
            except: 
                current_place_url = "null"
                current_place_title = "null"
                current_place_address = unicode(eventTag.xpath("h2/span[@class='place']")[0].text_content())

            #get all text
            tmp = "null"
            for pTag in eventTag.xpath("p"):
                if (tmp == "null"): tmp = ""
                tmp = tmp + tostring(pTag)
            
            current_text = (decode_unicode_references(tmp))

            extended_info = {"title":current_title, 
                            "url":event_url, 
                            "bimage_url":current_bimage_url, 
                            "date_interval":current_date_interval, 
                            "worktime":current_worktime, 
                            "price":current_price, 
                            "place_url":current_place_url, 
                            "place_title":current_place_title, 
                            "place_address":current_place_address, 
                            "text":current_text}
            
            extended_info_json = simplejson.dumps(extended_info, ensure_ascii=False, indent=4, sort_keys=True)

        except: 
            logging.info("failed at event: %s", event_url)
            return []

        return extended_info_json

class PlacesPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'

        type_string = self.request.query_string

        items_json = memcache.get(type_string)
        if items_json is not None:
            self.response.out.write(items_json)
        else:
            items_json = self.getPlacesByType(type_string)
            memcache.add(type_string, items_json, 60*60*24*7)
            self.response.out.write(items_json)

    def getPlacesAtPage(self, page, place_type):
        url = urllib.urlopen(page)
        html_page = html.parse(url)
        root = html_page.getroot()
        
        searchResults_liTags = root.xpath("/html/body[@class='yui-skin-sam']/div[@id='allWrap']/div[@class='contentWrap']/div[@class='col-2a-l']/div[@class='searchResults']/ul/li")
        type_Tag = root.xpath("/html/body[@class='yui-skin-sam']/div[@id='allWrap']/div[@class='contentWrap']/div[@class='col-2a-l']/div[@class='resultsHeader']/h2")
        
        items = []
        for liTag in searchResults_liTags:
            try:
                current_url = unicode(liTag.xpath("h2/a/@href")[0])
                current_simage_url = "http://afishalviv.net/" +  str(liTag.xpath("a[@class='thumb']/img/@src")[0])
                current_title = unicode(liTag.xpath("h2/a")[0].text_content())
                
                try: current_desc = unicode(liTag.xpath("p[@class='desc']")[0].text_content())
                except: current_desc = "null"
                
                if (type_Tag[0].text_content() == "Кнайпи".decode("utf-8")): current_placetype = "restaurant"
                elif (type_Tag[0].text_content() == "Музеї".decode("utf-8")): current_placetype = "museum"
                elif (type_Tag[0].text_content() == "Галереї".decode("utf-8")): current_placetype = "gallery"
                elif (type_Tag[0].text_content() == "Театри".decode("utf-8")): current_placetype = "theater"
                elif (type_Tag[0].text_content() == "Кіно".decode("utf-8")): current_placetype = "cinema"
                else: current_placetype = "hall"
                
                current_place = {"url":current_url,
                                "title":current_title,
                                "place_type":current_placetype,
                                "simage_url":current_simage_url,
                                "desc":current_desc,
                                "place_type":place_type}
                
                items.append(current_place)
            except: 
                logging.info("no places: %s", page)

        return items
    
    def getPlacesByType(self, place_type):

# http://afishalviv.net/page/ua/restaurants/
# http://afishalviv.net/page/ua/event-galleries/
# http://afishalviv.net/page/ua/event-museums/
# http://afishalviv.net/page/ua/event-theatres/
# http://afishalviv.net/page/ua/event-cinema/
# http://afishalviv.net/page/ua/event-clubs/`
# http://afishalviv.net/page/ua/event-halls/

        if place_type == "restaurant": places_url = "http://afishalviv.net/page/ua/restaurants/"
        elif place_type == "gallery": places_url = "http://afishalviv.net/page/ua/event-galleries/"
        elif place_type == "museum": places_url = "http://afishalviv.net/page/ua/event-museums/"
        elif place_type == "theater": places_url = "http://afishalviv.net/page/ua/event-theatres/"
        elif place_type == "cinema": places_url = "http://afishalviv.net/page/ua/event-cinema/"
        elif place_type == "club": places_url = "http://afishalviv.net/page/ua/event-clubs/"
        elif place_type == "hall": places_url = "http://afishalviv.net/page/ua/event-halls/"
        else: return []

        items = self.getPlacesAtPage(places_url, place_type)

        url = urllib.urlopen(places_url)
        html_page = html.parse(url)
        root = html_page.getroot()
        
        searchPagesList = root.xpath("/html/body[@class='yui-skin-sam']/div[@id='allWrap']/div[@class='contentWrap']/div[@class='col-2a-l']/div[@id='searchpagesList']/span[@class='data']/a/@href")
        for page in searchPagesList:
            logging.info("page: %s", page)
            items += self.getPlacesAtPage(page, place_type)

        items_json = simplejson.dumps(items, ensure_ascii=False, indent=4, sort_keys=True)

        return items_json

class PlaceInfoPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'
        
        place_url = self.request.query_string

        place_info_json = memcache.get(place_url)
        if place_info_json is not None:
            self.response.out.write(place_info_json)
        else: 
            place_info_json = self.getPlaceExtendedInfo(place_url)
            memcache.add(place_url, place_info_json, 60*60*24*7)
            self.response.out.write(place_info_json)

    def getPlaceExtendedInfo(self, place_url):
        logging.info("place url: %s", place_url)

        url = urllib.urlopen(place_url)
        html_page = html.parse(url)
        root = html_page.getroot()
            
        try:
            localInfoTag = root.xpath("/html/body[@class='yui-skin-sam']/div[@id='allWrap']/div[@class='contentWrap']/div[@class='col-2a-l']/div[@class='localInfo']")[0]
                    
            current_title = unicode(localInfoTag.xpath("h1/span[@class='fn org']")[0].text_content())
                
            current_bimage_url = "http://afishalviv.net/" +  unicode(localInfoTag.xpath("div[@class='thumb']/img/@src")[0])
            
            current_address = "null"
            current_location = "null"
            current_phone = "null"
            current_email = "null"
            current_website = "null"
            current_schedule = "null"
            
            trTags = localInfoTag.xpath("div/table/tr")
            for trTag in trTags:
                if (trTag.xpath("td[1]")[0].text_content() == "Адреса:\n ".decode("utf-8")): 
                    current_address = unicode(trTag.xpath("td[2]")[0].text_content())
                  
                if (trTag.xpath("td[1]")[0].text_content() == "Розміщення:\n ".decode("utf-8")): 
                    current_location = unicode(trTag.xpath("td[2]")[0].text_content())
                
                if (trTag.xpath("td[1]")[0].text_content() == "Телефон:\n ".decode("utf-8")): 
                    current_phone = unicode(trTag.xpath("td[2]")[0].text_content())
                
                if (trTag.xpath("td[1]")[0].text_content() == "\n E-mail:\n ".decode("utf-8")): 
                    current_email = unicode(trTag.xpath("td[2]")[0].text_content())
                
                if (trTag.xpath("td[1]")[0].text_content() == "Веб-сайт:\n ".decode("utf-8")): 
                    current_website = unicode(trTag.xpath("td[2]")[0].text_content())

                if (trTag.xpath("td[1]")[0].text_content() == "Графік роботи:\n ".decode("utf-8")): 
                    current_schedule = unicode(trTag.xpath("td[2]")[0].text_content())
                
            current_googlemap = unicode(root.xpath("/html/body[@class='yui-skin-sam']/div[@id='allWrap']/div[@class='contentWrap']/div[@class='col-2b-r']/div[@class='textBox dotted location']/ul/li/a/@href")[0])
                        
            tmp = "null"
            for pTag in localInfoTag.xpath("div[@class='content']/p"):
                if (tmp == "null"): tmp = ""
                tmp = tmp + tostring(pTag)
            
            current_text = (decode_unicode_references(tmp))
                        
            extended_info = {"title":current_title,
                            "url":place_url,
                            "bimage_url":current_bimage_url,
                            "address":current_address,
                            "location":current_location,
                            "phone":current_phone,
                            "email":current_email,
                            "website":current_website,
                            "schedule":current_schedule,
                            "googlemap":current_googlemap,
                            "text":current_text}

            extended_info_json = simplejson.dumps(extended_info, ensure_ascii=False, indent=4, sort_keys=True)

        except: 
            logging.info ("failed at place: %s", place_url)
            return []

        return extended_info_json

#########################################################################################################################################################
#########################################################################################################################################################
#########################################################################################################################################################
#########################################################################################################################################################
#########################################################################################################################################################

class FlushMemcachePage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        memcache.flush_all()
        self.response.out.write("flushing memcache done!")

#########################################################################################################################################################
#########################################################################################################################################################
#########################################################################################################################################################
#########################################################################################################################################################
#########################################################################################################################################################

class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('@danylokostyshyn\n')
        self.response.out.write('\n/events?YYYY-MM-DD\n')
        self.response.out.write('\n/event_info?%EVENT_URL%\n')
        self.response.out.write('\n/places?TYPE //{restaurant, museum, gallery, theater, cinema, club, hall}\n')
        self.response.out.write('\n/place_info?%PLACE_URL%\n') 

app = webapp2.WSGIApplication([('/', MainPage),
                               ('/events', EventsPage),
                               ('/event_info', EventInfoPage),
                               ('/places', PlacesPage),
                               ('/place_info', PlaceInfoPage),
                               ('/flush_memcache', FlushMemcachePage)],
                              debug=True)