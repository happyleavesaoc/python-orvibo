#!/usr/bin/env python
from http.server import BaseHTTPRequestHandler, HTTPServer
from orvibo.s20 import S20, discover
import argparse
global args
global httpd

class S(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        global ObjectList
        self._set_headers()
        slash,command,address=self.path.split('/')
        if command=='STATUS':
        	notknown=True
        	for (x,y) in ObjectList:
        		if x==address:
        			notknown=False
        			if y.on:
        				self.wfile.write(bytes("ON", 'UTF-8'))
        				print(x, " status is ON")
        			else:
        				self.wfile.write(bytes("OFF", 'UTF-8'))
        				print(x," status is OFF")
        elif command=='ON':
        	notknown=True
        	for (x,y) in ObjectList:
        		if x==address:
        			notknown=False
        			y.on=True
        			self.wfile.write(bytes("ON", 'UTF-8'))
        			print(x," switched to ON.")
        elif command=='OFF':
        	notknown=True
        	for (x,y) in ObjectList:
        		if x==address:
        			notknown=False
        			y.on=False
        			self.wfile.write(bytes("OFF", 'UTF-8'))
        			print(x," switched to OFF")
        else:
        	print("Error, GET command not recognised")
        	self.wfile.write(bytes("ERROR 1", 'UTF-8'))
        if notknown:
        	self.wfile.write(bytes("ERROR 2", 'UTF-8'))        	
        	print("Error, address not active or invalid")

    def do_HEAD(self):
        self._set_headers()
        
    def do_POST(self):
    	'''
    	No POST Implemented
    	'''

def init_s20():
	global ObjectList
	ObjectList=[]
	print('Discovering Orvibo S20 plugs....')
	try:
		hosts=discover()
	except:
		print('Unexpected Error in initialisation plugs')
		return(False)
	else:

		for i in hosts.keys():
			print('Discovered Orvibo S20 plug on',i)
			TempObject=S20(i)
			TempTuple=(i,TempObject)
			ObjectList.append(TempTuple)
		print(len(ObjectList),' plugs found in total')
		return(True)


			
def init_server(server_class=HTTPServer, handler_class=S):
	global httpd
	global args
	print('Starting HTTP Server on', args.IP[0],args.port[0])
	server_address = (args.IP[0], args.port[0])	
	try:
		httpd = server_class(server_address, handler_class)
		print('HTTP server started on',args.IP[0],args.port[0])
		return(True)
	except:
		print('Unexpected Error in starting server')
		return(False)
	                   
def run():
	global httpd
	httpd.serve_forever()

parser = argparse.ArgumentParser(description='Control Orvibo plugs on local network through HTTP GET Requests')
parser.add_argument('IP', metavar='IP Address', type=str, nargs=1,help='IP Address to bind to')
parser.add_argument('port', metavar='port', type=int, nargs=1,help='Port to listen on')
args=parser.parse_args()
if not init_s20():
	exit()
if not init_server():
	exit()
try:
	run()
except KeyboardInterrupt:
	print('^C received, shutting down the web server')
	httpd.socket.close()
