from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket

import time
import glob # to list all video files from the server's directory

class ServerWorker:
	SETUP = 'SETUP'
	PLAY = 'PLAY'
	PAUSE = 'PAUSE'
	TEARDOWN = 'TEARDOWN'
	DESCRIBE = 'DESCRIBE' #new
	JUMP = 'JUMP' #new
	SWITCH = 'SWITCH' #new
	CHANGESPEED = 'CHANGESPEED' #new

	INIT = 0
	READY = 1
	PLAYING = 2
	SWITCHING = 3 #new

	state = INIT

	OK_200 = 0
	FILE_NOT_FOUND_404 = 1
	CON_ERR_500 = 2
	
	clientInfo = {}
	
	def __init__(self, clientInfo):
		self.clientInfo = clientInfo
		self.clientInfo['frameDelay'] = 0.05
		
	def run(self):
		threading.Thread(target=self.recvRtspRequest).start()
	
	def recvRtspRequest(self):
		"""Receive RTSP request from the client."""
		connSocket = self.clientInfo['rtspSocket'][0]
		while True:            
			data = connSocket.recv(256)
			if data:
				print("Data received:\n" + data.decode("utf-8"))
				self.processRtspRequest(data.decode("utf-8"))
	
	def processRtspRequest(self, data):
		"""Process RTSP request sent from the client."""
		# Get the request type
		request = data.split('\n')
		line1 = request[0].split(' ')
		requestType = line1[0]
		
		# Get the media file name
		filename = line1[1]
		
		# Get the RTSP sequence number 
		seq = request[1].split(' ')		

		# Process SETUP request
		if requestType == self.SETUP:
			if self.state == self.INIT:
				# Update state
				print("processing SETUP\n")
				
				try:#modified: move 3 last lines into the trycatch
					self.clientInfo['videoStream'] = VideoStream(filename)
					self.state = self.READY

					# Generate a randomized RTSP session ID
					self.clientInfo['session'] = randint(100000, 999999)
				
					# Send RTSP reply
					#self.replyRtsp(self.OK_200, seq[1])
					reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq[1] + '\nSession: ' + str(self.clientInfo['session']) + "\n"
					reply += "TotalFrame " + str(self.clientInfo['videoStream'].getNumberOfFrame())
					connSocket = self.clientInfo['rtspSocket'][0]
					connSocket.send(reply.encode())
				
					# Get the RTP/UDP port from the last line
					self.clientInfo['rtpPort'] = request[2].split(' ')[3]

				except IOError:
					self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])				
				
		
		# Process PLAY request 		
		elif requestType == self.PLAY:
			if self.state == self.READY or self.state == self.SWITCHING:
				print("processing PLAY\n")
				self.state = self.PLAYING
				
				# Create a new socket for RTP/UDP
				self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				
				self.replyRtsp(self.OK_200, seq[1])
				
				# Create a new thread and start sending RTP packets
				self.clientInfo['event'] = threading.Event()
				self.clientInfo['worker']= threading.Thread(target=self.sendRtp) 
				self.clientInfo['worker'].start()
		
		# Process PAUSE request
		elif requestType == self.PAUSE:
			if self.state == self.PLAYING:
				print("processing PAUSE\n")
				self.state = self.READY
				
				self.clientInfo['event'].set()
			
				self.replyRtsp(self.OK_200, seq[1])
		
		# Process TEARDOWN request
		elif requestType == self.TEARDOWN:
			print("processing TEARDOWN\n")
			self.state = self.INIT #addition

			self.clientInfo['event'].set()
			
			self.replyRtsp(self.OK_200, seq[1])
			
			# Close the RTP socket
			self.clientInfo['rtpSocket'].close()
		
		# Process DESCRIBE request - extend 3
		elif requestType == self.DESCRIBE:
			print("processing DESCRIBE\n")
			try:
				sessionInfo = "v=2\n"
				sessionInfo += "o=" + self.clientInfo['rtspSocket'][0].getpeername()[0] + "\n"
				sessionInfo += "s=RTSP " + str(self.clientInfo['session']) + "\n"
				sessionInfo += "m=video " + str(filename) + " RTP/Mjpge\n"
				sessionInfo += "m=size " + str(self.clientInfo['videoStream'].getFileSize()) + " Bytes"

				reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq[1] + '\nSession: ' + str(self.clientInfo['session']) + "\n"
				reply += "Content-Length: " + str(len(sessionInfo)) + "\n\n"
				reply += sessionInfo
				connSocket = self.clientInfo['rtspSocket'][0]
				connSocket.send(reply.encode())
			except IOError:
				self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])

		# Process JUMP request - extend 4
		elif requestType == self.JUMP:
			print("processing JUMP\n")
			try:
				self.replyRtsp(self.OK_200, seq[1])
				frameIndex = int(request[3].split(' ')[1])
				self.clientInfo['videoStream'].jumpTo(frameIndex)
			except IOError:
				self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])

		# Process SWITCH request - extend 5
		elif requestType == self.SWITCH:
			print("processing SWITCH\n")
			self.state == self.SWITCHING
			try:
				fileList = glob.glob('*.Mjpeg')

				reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq[1] + '\nSession: ' + str(self.clientInfo['session']) + "\n"
				reply += "Videos:"
				for file in fileList:
					reply += " "+ file
				connSocket = self.clientInfo['rtspSocket'][0]
				connSocket.send(reply.encode())
			except IOError:
				self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])

		elif requestType == self.CHANGESPEED:
			print("processing CHANGESPEED\n")
			self.replyRtsp(self.OK_200, seq[1])
			newDelay = float(request[3].split(' ')[1])
			self.clientInfo['frameDelay'] = newDelay

	def sendRtp(self):
		"""Send RTP packets over UDP."""
		lastFrameTime = time.time()
		while True:
			currentFrameTime = time.time()
			if (currentFrameTime - lastFrameTime) > self.clientInfo['frameDelay']:
				lastFrameTime = currentFrameTime
				#self.clientInfo['event'].wait(0.05) I don't trust this clock
			
				# Stop sending if request is PAUSE or TEARDOWN
				if self.clientInfo['event'].isSet(): 
					break 
				
				data = self.clientInfo['videoStream'].nextFrame()
				if data: 
					frameNumber = self.clientInfo['videoStream'].frameNbr()
					try:
						address = self.clientInfo['rtspSocket'][1][0]
						port = int(self.clientInfo['rtpPort'])
						self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber),(address,port))
					except:
						print("Connection Error")
						#print('-'*60)
						#traceback.print_exc(file=sys.stdout)
						#print('-'*60)

	def makeRtp(self, payload, frameNbr):
		"""RTP-packetize the video data."""
		version = 2
		padding = 0
		extension = 0
		cc = 0
		marker = 0
		pt = 26 # MJPEG type
		seqnum = frameNbr
		ssrc = 0 
		
		rtpPacket = RtpPacket()
		
		rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)
		
		return rtpPacket.getPacket()
		
	def replyRtsp(self, code, seq):
		"""Send RTSP reply to the client."""
		if code == self.OK_200:
			#print("200 OK")
			reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + '\nSession: ' + str(self.clientInfo['session'])
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())
		
		# Error messages
		elif code == self.FILE_NOT_FOUND_404:
			#addition: inform the client about 404 error
			reply = 'RTSP/1.0 404 FILE_NOT_FOUND\nCSeq: ' + seq
			connSocket = self.clientInfo['rtspSocket'][0]
			connSocket.send(reply.encode())

			print("404 NOT FOUND")
		elif code == self.CON_ERR_500:
			print("500 CONNECTION ERROR")
