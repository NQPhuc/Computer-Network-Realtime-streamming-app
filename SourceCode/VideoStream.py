import os

class VideoStream:
	def __init__(self, filename):
		self.filename = filename
		self.frameNum = 0
		self.indexTable = [0]
		try:
			self.file = open(filename, 'rb')
			self.buildIndex()
		except:
			raise IOError
	
	def buildIndex(self): #new - used to handle jump request more efficiently
		data = self.nextFrame()
		while data:
			self.indexTable.append(self.file.tell())
			data = self.nextFrame()
		self.file.seek(0, 0)
		self.frameNum = 0
		
	def nextFrame(self):
		"""Get next frame."""
		data = self.file.read(5) # Get the framelength from the first 5 bits
		if data: 
			#WOW. The first 5 byte is a string of digit...
			framelength = int(data)
							
			# Read the current frame
			data = self.file.read(framelength)
			self.frameNum += 1
		return data
		
	def frameNbr(self):
		"""Get frame number."""
		return self.frameNum #frameNum is actutally index in indexTable + 1
	
	def jumpTo(self, frameIndex):
		self.file.seek(self.indexTable[frameIndex], 0)
		self.frameNum = frameIndex

	def getFileSize(self):
		file_stats = os.stat(self.filename)
		return file_stats.st_size

	def getNumberOfFrame(self):
		return len(self.indexTable) 
		"""
		currentPos = self.file.tell() #save current position
		currentFrameNum = self.frameNum

		self.file.seek(0, 0) #move position to start to prepare for counting
		data = self.nextFrame()
		while data:
			data = self.nextFrame()
		self.file.seek(currentPos, 0) #move the stream position to current
		
		result = self.frameNum
		self.frameNum = currentFrameNum

		return result
		"""
	
	