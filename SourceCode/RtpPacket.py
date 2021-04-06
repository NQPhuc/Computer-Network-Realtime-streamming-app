#newly create file, author: Nguyen Quang Phuc
import time  


class RtpPacket:
    def decode(self, data):
        self.header = data[0:12]
        self.payload = data[12:]

        self.version = (self.header[0] & 0xC0) >> 6
        self.padding = (self.header[0] & 0x20) >> 5
        self.extension = (self.header[0] & 0x10) >> 4
        self.cc = self.header[0] & 0x0F

        self.marker = (self.header[1] & 0x80) >> 7
        self.pt = self.header[1] & 0x7F

        self.seqnum = int.from_bytes(self.header[2:4], 'big', signed = False)
        self.timestamps = int.from_bytes(self.header[4:8], 'big', signed = False)
        self.ssrc = int.from_bytes(self.header[8:12], 'big', signed = False)

        #self.frameLength = int.from_bytes(self.payload[0:5], 'big', signed = False)
        #self.frame = self.payload[5:self.frameLength + 5] #not sure, just in case payload has blank section at the end
        self.frame = self.payload

    def encode(self, version, padding, extension, cc, seqnum, marker, pt, ssrc, payload):
        self.payload = payload
        byte = version
        byte = byte << 1
        byte = byte | padding
        byte = byte << 1
        byte = byte | extension
        byte = byte << 4
        byte = byte | cc
        byte = byte << 1
        byte = byte | marker
        byte = byte << 7
        byte = byte | pt
        byte = byte << 16
        byte = byte | seqnum

        ts = int(time.time() * 1000)  #timestamp in milisecond
        ts_truncated = 0xFFFFFFFF & ts #only keep lower 32 bit 

        self.header = byte.to_bytes(4, 'big', signed=False) + ts_truncated.to_bytes(4, 'big', signed=False) + ssrc.to_bytes(4, 'big', signed=False)
    def getPacket(self):
        return self.header + self.payload
'''
version = 2
padding = 1
extension = 1
cc = 7
marker = 1
pt = 26 # MJPEG type
seqnum = 1
ssrc = 4 
		
rtpPacket = RtpPacket()
		
rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, b'\x00\x00\x00\x00\x03\xAB\x1C\x2A')

data = rtpPacket.getPacket()

print(data.hex(':'))

rtpPacket.decode(data)
print("Version: " + str(rtpPacket.version))
print("Padding: " + str(rtpPacket.padding))
print("Extension: " + str(rtpPacket.extension))
print("cc: " + str(rtpPacket.cc))
print("marker: " + str(rtpPacket.marker))
print("pt: " + str(rtpPacket.pt))
print("seqnum: " + str(rtpPacket.seqnum))
print("timestamps: " + str(rtpPacket.timestamps))
print("ssrc: " + str(rtpPacket.ssrc))
#print("FrameLenght: " + str(rtpPacket.frameLength))
print(rtpPacket.frame)
'''