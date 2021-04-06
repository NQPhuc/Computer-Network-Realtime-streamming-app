#newly create file, author: Nguyen Quang Phuc

import tkinter as tk
from tkinter import messagebox as mb
from tkinter import ttk as ttk
import socket as sk
import threading 

from RtpPacket import RtpPacket #rtp decoding

from PIL import Image, ImageTk #jpeg displaying from IO stream
from io import BytesIO #jpeg loading from bytes to IOstream for display 

import time


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    SWITCHING = 3

    state = INIT
    sequence = 0
    session = -1
    

    currentFrame = 0
    lossFrame = 0
    totalFrame = 0
    lastTime = 0
    maxFrameNum = 0
    
    def __init__(self, rootTK, serverAddr, serverPort, rtpPort, fileName):
        self.master = rootTK
        self.serverAddr = serverAddr
        self.serverPort = int(serverPort)
        self.rtpPort = int(rtpPort)
        self.fileName = fileName
        self.master.protocol("WM_DELETE_WINDOW", self.exit)
        #self.master.title("VIDEO SRC: " + fileName)

        #Setting up the GUI
        self.photo = ImageTk.PhotoImage(Image.open('Black.jpg'))

        self.videoFrame = tk.Frame(self.master, width = 600, height = 480)
        self.btnFrame = tk.Frame(self.master)
        self.statsLabel = tk.Label(self.master, text = "statistic", width = 30)

        self.controlScrollVar = tk.IntVar()
        self.videoScrollBar = tk.Scale(self.master, orient = "horizontal", showvalue = 0, sliderlength = 13, 
                                       width = 20, variable = self.controlScrollVar)
        #calling jump to only when user release the left mouse, to prevent firing more than once
        self.videoScrollBar.bind("<ButtonPress-1>", self.pauseBeforeJump) #pause before jump to avoid deadlock
        self.videoScrollBar.bind("<ButtonRelease-1>", self.jumpTo)

        self.statsLabel.pack(side = tk.RIGHT)
        self.videoFrame.pack()
        self.videoScrollBar.pack(fill = tk.X)
        self.btnFrame.pack()    

        self.imagePanel = tk.Label(master = self.videoFrame, image=self.photo)
        self.imagePanel.image = self.photo # keep a reference!
        self.imagePanel.pack() 

        self.playBtn = tk.Button(self.btnFrame, text = "Play", command = self.play)
        self.playBtn.grid(row = 0, column = 0)

        self.pauseBtn = tk.Button(self.btnFrame, text = "Pause", command = self.pause)
        self.pauseBtn.grid(row = 0, column = 1)

        self.teardownBtn = tk.Button(self.btnFrame, text = "STOP", command = self.teardown)
        self.teardownBtn.grid(row = 0, column = 2)

        self.describeBtn = tk.Button(self.btnFrame, text = "DESCRIBE", command = self.describe)
        self.describeBtn.grid(row = 0, column = 3)

        self.speedOptionMenuVar = tk.StringVar()
        self.speedOptionMenuVar.set("playback speed x1")
        self.speedOptionMenu = tk.OptionMenu(self.btnFrame, self.speedOptionMenuVar, "playback speed x0.1", 
            "playback speed x0.25", "playback speed x0.5", "playback speed x1", "playback speed x1.25", 
            "playback speed x1.5", "playback speed x1.75", "playback speed x2", "playback speed x2.5", 
            "playback speed x3")
        self.speedOptionMenu.grid(row = 1, column = 0, columnspan = 4)
        self.speedOptionMenuVar.trace("w", self.changeSpeed)

        #Extend 5 GUI
        self.videoListVar = tk.StringVar()
        self.videoListVar.set(self.fileName)
        self.videoList = tk.OptionMenu(self.btnFrame, self.videoListVar, self.fileName)
        self.videoList.bind('<ButtonRelease-1>', self.requestList) #called when the user click the dropdown menu
        self.videoListVarTraceID = self.videoListVar.trace("w", self.switchChannel)
        self.videoList.grid(row = 1, column = 4, columnspan = 1)     

        #Setting up socket RTPS/TCP
        self.rtpsSocket = sk.socket(sk.AF_INET, sk.SOCK_STREAM)
        self.rtpsSocket.connect((self.serverAddr, self.serverPort))          

    #input event handler
    def setup(self):
        if(self.state == self.INIT):
            #setup RTP/UDP socket
            self.rtpSocket = sk.socket(sk.AF_INET, sk.SOCK_DGRAM)
            self.rtpSocket.bind(('', self.rtpPort))

            self.sequence += 1

            message = "SETUP " + self.fileName + " RTPS/1.0\n"
            message += "CSeq: " + str(self.sequence) + "\n"
            message += "Transprot: RTP/UDP; client_port= " + str(self.rtpPort)
            self.rtpsSocket.send(message.encode())
        
            reply = self.rtpsSocket.recv(1024).decode("utf-8"); #1024 bytes buffer
            
            lines = reply.split('\n')
            if(lines[1] == "CSeq: " + str(self.sequence)):
                if(lines[0] == "RTSP/1.0 200 OK"):
                    self.state = self.READY
                    self.session = lines[2].split(' ')[1] 
                    self.maxFrameNum = int(lines[3].split(' ')[1])

                    self.videoScrollBar.config(to = self.maxFrameNum - 1)
                    self.controlScrollVar.set(0)

                    print("Reply From: " + str(self.serverAddr) + ":" + str(self.serverPort)  + "\n" + reply)
                    print("----------------------\n")
                    #mb.showinfo("Reply" ,"From: " + str(self.serverAddr) + ":" + str(self.serverPort) 
                    #        + "\n" + reply               
                else:
                    mb.showerror("Error", lines[0])
            else:
                mb.showwarning("Warning", "Out of order sequence: " + lines[1] + ". Expecting " + str(self.sequence))
        else:
            mb.showwarning("Warning", "A connection was already setup!")

    def play(self):
        if(self.state == self.READY or self.state == self.SWITCHING):
            self.sequence += 1
            message = "PLAY " + self.fileName + " RTPS/1.0\n"
            message += "CSeq: " + str(self.sequence) + "\n"
            message += "Session: " + str(self.session)
            self.rtpsSocket.send(message.encode())
        
            reply = self.rtpsSocket.recv(1024).decode("utf-8");
            print("Reply From: " + str(self.serverAddr) + ":" + str(self.serverPort) + "\n" + reply)
            print("----------------------\n")
            #mb.showinfo("Reply" ,"From: " + str(self.serverAddr) + ":" + str(self.serverPort) 
            #                + "\n" + reply)

            self.state = self.PLAYING
            self.rtpListener_PlayingFlag = True

            self.rtpSocket.settimeout(0.5)
            self.rtpListener = threading.Thread(target=self.receiveRtp)
            self.rtpListener.start()

        elif(self.state == self.INIT): #Extend 2
            self.setup()
            self.play()
        else:
            mb.showwarning("Warning", "The stream is already playing!")

    def pause(self):
        if(self.state == self.PLAYING):
            self.sequence += 1
            message = "PAUSE " + self.fileName + " RTPS/1.0\n"
            message += "CSeq: " + str(self.sequence) + "\n"
            message += "Session: " + str(self.session)
            self.rtpsSocket.send(message.encode())
        
            reply = self.rtpsSocket.recv(1024).decode("utf-8");
            print("Reply From: " + str(self.serverAddr) + ":" + str(self.serverPort) + "\n" + reply)
            print("----------------------\n")
            #mb.showinfo("Reply" ,"From: " + str(self.serverAddr) + ":" + str(self.serverPort) 
            #                + "\n" + reply)

            self.rtpListener_PlayingFlag = False

            self.state = self.READY

        elif(self.state == self.INIT):
            mb.showwarning("Warning", "You need to setup the stream first!")
        else:
            mb.showwarning("Warning", "The stream is already paused!")

    def teardown(self): #Extend 3
        if(self.state == self.PLAYING or self.state == self.READY or self.state == self.SWITCHING):
            self.sequence += 1
            message = "TEARDOWN " + self.fileName + " RTPS/1.0\n"
            message += "CSeq: " + str(self.sequence) + "\n"
            message += "Session: " + str(self.session)
            self.rtpsSocket.send(message.encode())
        
            reply = self.rtpsSocket.recv(1024).decode("utf-8");
            print("Reply From: " + str(self.serverAddr) + ":" + str(self.serverPort) + "\n" + reply)
            print("----------------------\n")
            #mb.showinfo("Reply" ,"From: " + str(self.serverAddr) + ":" + str(self.serverPort) 
            #                + "\n" + reply)

            self.rtpListener_PlayingFlag = False
            self.rtpSocket.close()

            self.currentFrame = 0
            self.lossFrame = 0
            self.totalFrame = 0

            self.state = self.INIT

        elif(self.state == self.INIT):
            mb.showwarning("Warning", "Nothing to teardown")
        #else:
           # mb.showwarning("Warning", "The stream cannot be teardown while pausing")

    def describe(self):
        if self.state == self.PLAYING or self.state == self.READY:
            self.sequence += 1
            message = "DESCRIBE " + self.fileName + " RTPS/1.0\n"
            message += "CSeq: " + str(self.sequence) + "\n"
            message += "Session: " + str(self.session)
            self.rtpsSocket.send(message.encode())
        
            reply = self.rtpsSocket.recv(1024).decode("utf-8");
            print("Reply From: " + str(self.serverAddr) + ":" + str(self.serverPort) + "\n" + reply)
            print("----------------------\n")
            mb.showinfo("Reply" ,"From: " + str(self.serverAddr) + ":" + str(self.serverPort) + "\n" + reply)

    def jumpTo(self, e):#extend 4
        if self.state == self.READY:
            self.sequence += 1
            message = "JUMP " + self.fileName + " RTPS/1.0\n"
            message += "CSeq: " + str(self.sequence) + "\n"
            message += "Session: " + str(self.session) + "\n"
            message += "Frame: " + str(self.videoScrollBar.get())
            self.rtpsSocket.send(message.encode())
            #mb.showinfo("SEND" ,message)
            reply = self.rtpsSocket.recv(1024).decode("utf-8");
            print("Reply From: " + str(self.serverAddr) + ":" + str(self.serverPort) + "\n" + reply)
            print("----------------------\n")

            self.currentFrame = self.videoScrollBar.get()
            self.play()

    def pauseBeforeJump(self, e):
        if self.state == self.PLAYING:
            self.pause()
    
    #Extend 5
    dropdownActived = False
    def requestList(self, e):
        if self.state == self.PLAYING:
            self.pause() #pause to avoid deadlock
        
        if self.state == self.READY and (not self.dropdownActived):
            self.sequence += 1
            message = "SWITCH " + self.fileName + " RTPS/1.0\n"
            message += "CSeq: " + str(self.sequence) + "\n"
            message += "Session: " + str(self.session)
            self.rtpsSocket.send(message.encode())
            #mb.showinfo("SEND" ,message)
            reply = self.rtpsSocket.recv(1024).decode("utf-8");

            lines = reply.split('\n')
            if(lines[1] == "CSeq: " + str(self.sequence)):
                if(lines[0] == "RTSP/1.0 200 OK"):
                    self.dropdownActived = True
                    self.state = self.SWITCHING

                    self.session = lines[2].split(' ')[1] 
                    fileList = lines[3].split(' ')[1:] #get list of files on server

                    self.videoList['menu'].delete(0, 'end')
                    for file in fileList:
                        tempLabel = file + " (current)" if file == self.fileName else file
                        self.videoList['menu'].add_command(label = tempLabel, command = (lambda x=file: self.videoListVar.set(x)))

                    print("Reply From: " + str(self.serverAddr) + ":" + str(self.serverPort)  + "\n" + reply)
                    print("----------------------\n")

                    #mb.showinfo("Reply" ,"From: " + str(self.serverAddr) + ":" + str(self.serverPort) 
                    #        + "\n" + reply               
                else:
                    mb.showerror("Error", lines[0])
            else:
                mb.showwarning("Warning", "Out of order sequence: " + lines[1] + ". Expecting " + str(self.sequence))

    def switchChannel(self, *arg):
        self.dropdownActived = False
        if self.fileName == self.videoListVar.get():
            self.play()
            return
        #if file name is different than the current, set new file name so that future setup call will change to new channel
        self.fileName = self.videoListVar.get()
        self.teardown()

    #bonus feature - change playbackSpeed
    def changeSpeed(self, *arg):
        self.sequence += 1
        message = "CHANGESPEED " + self.fileName + " RTPS/1.0\n"
        message += "CSeq: " + str(self.sequence) + "\n"
        message += "Session: " + str(self.session) + "\n"
        speed = float(self.speedOptionMenuVar.get().split('x')[1])
        message += "Delay: " + str(0.05 / speed) #default delay between is 0.05

        self.rtpsSocket.send(message.encode())
        #mb.showinfo("SEND" ,message)
        reply = self.rtpsSocket.recv(1024).decode("utf-8");
        print("Reply From: " + str(self.serverAddr) + ":" + str(self.serverPort) + "\n" + reply)
        print("----------------------\n")

    def exit(self):
        self.teardown() #tell server to teardown the stream and stop sending
        self.rtpsSocket.close() #close the tcp connection
        self.master.destroy() #kill the application by stopping the mainloop


    #helper function
    def receiveRtp(self):
        maxFrameTime = 0.05 * self.maxFrameNum
        while self.rtpListener_PlayingFlag:
            try:
                data = self.rtpSocket.recv(1024*1024) #1MB buffer
                if data:
                    packet = RtpPacket()
                    packet.decode(data)

                    if(self.currentFrame + 1 != packet.seqnum):
                        self.lossFrame += 1
                    self.currentFrame = packet.seqnum
                    self.totalFrame += 1

                    current = time.time()
                    duration = current - self.lastTime
                    self.lastTime = current
                    speed = len(packet.frame) / duration
                    fps = 1/duration

                    currentFrameTime = 0.05 * self.currentFrame
                    remainingTime = maxFrameTime - currentFrameTime
                   
                    #Extend 1
                    stats = "RTP packet number: " + str(self.currentFrame) + "\n"
                    stats += "RTP loss packet: " + str(self.lossFrame) + "\n"
                    stats += "RTP packet loss rate: " + '{:.2f}'.format(self.lossFrame / self.totalFrame * 100) + "%\n"
                    stats += "Video data rate: " + '{:.2f}'.format(speed) + " Bytes/s\n"
                    stats += "Frame duration: " + '{:.0f}'.format(duration*1000) + " ms\n"
                    stats += "Frame per second: " + '{:.2f}'.format(fps) + "\n"
                    stats += "-----------------------\n"
                    #Extend 4
                    stats += "Remaining Time: " + '{:.0f}'.format(remainingTime) + " s\n"
                    stats += "Total Time: " + '{:.0f}'.format(maxFrameTime) + " s\n"
                    stats += "-----------------------\n"
                    stats += "VIDEO SRC: " + self.fileName + "\n"

                    self.statsLabel.configure(text = stats)

                    file_jpgdata = BytesIO(packet.frame) #PIL Image.open accept jpeg format from a file stream
                    self.photo = ImageTk.PhotoImage(Image.open(file_jpgdata))
                    self.imagePanel.configure(image = self.photo)
                    self.imagePanel.image = self.photo

                    #self.videoScrollBar.set(self.currentFrame - 1) #This will trigger the callback
                    self.controlScrollVar.set(self.currentFrame - 1) #This won't trigger the callback
            except:
                 pass
                 #print("Timeout Error!")




        
        