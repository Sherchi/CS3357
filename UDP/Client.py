#####################################
#   Author: Darwin Liao             #
#   Student Num: 250959696          #
#   Date: Oct 17th/Nov 1st/Dec 4th  #
#   Assignment 2/3/4                #
#####################################
from ctypes import sizeof
from socket import *
import signal
import sys
import select
import struct
import hashlib
import os
import time
from urllib.parse import urlparse

#Maximum message size
MAX_STRING_SIZE = 256


#parsing command line arguments
#argParser = argparse.ArgumentParser(usage="[username] [chat://host:port]")
name = str(sys.argv[1])#"david"
url = str(sys.argv[2])#"chat://localhost:12000"


#Gets the Host/Servername and ServerPort 
tempStr = urlparse(url)
parsedURL = tempStr[1].split(":")
serverName = parsedURL[0]
serverPort = parsedURL[1]

#Client Socket Setup
clientSocket = socket(AF_INET, SOCK_DGRAM)
clientSocket.settimeout(1)
rList= [clientSocket]
rlist2 = [sys.stdin]
wList = [clientSocket]


#Class to contain file information.
#Contain
class infomationOfTheFile:
    def __init__(self):
        self.fileName = None
        self.fileTerms = None
        self.fileSize = None
        self.numPackets = None
        self.file = None
        
#####       RDT Class
#   @Brief: Contains Send and Recv functions for the RDT3.0 Stop and Wait functionaility, as well as 
#       A few flags and buffers for wordLists and fileLists, as well as a counter to iterate through a
#       File.
#   @__init__: init variables. Has both Send and Rec Ack Sequences.
#   @ recvPkt(self,dataToRead,isAckPacket,userAddr): RDT for receiving a message (dataToRead). Takes 
#           This data and compares it's checksum and it's ACK Sequence and follows the RDT3.0
#           Stop and Wait methodology. 
#   @ sendPkt(self,dataToSend,Socket,ClientAddr): RDT for sending a message(dataToSend). Takes
#           This data and sends it to the clientAddr. Sets a timer for when it has sent to be used
#           later on for checking for a return Ack.
#   
#########################################################################################################
class rdt:
    def __init__(self):
        self.currPacketInfo = None               
        self.sendAckSeq = 0
        self.recvAckSeq = 0
        self.startTime = time.time()
        self.inTransit = False
        self.repeatSend = False
        self.sendingFile = False
        self.recivingFile = False
        self.listToSend = []

    def recvPkt(self,dataToRead,isAckPacket):
        #Checks if the recv Packet is an acknoledgement from a previously sent Packet
        #if it is, then format the packet in a different way.
        if isAckPacket:
            received_sequence = dataToRead[0]
            received_size = dataToRead[1]
            received_checksum = dataToRead[2]

            packer = struct.Struct(f'I I 32s')
            values = (received_sequence,received_size,received_checksum)

        #If it is not an acknowledgement Packet, then it is a normal message and format it
        # like a normal Datagram
        else:
            received_sequence = dataToRead[0]
            received_size = dataToRead[1]
            received_data = dataToRead[2]
            received_checksum = dataToRead[3]

            packer = struct.Struct(f'I I {MAX_STRING_SIZE}s')
            values = (received_sequence,received_size,received_data)

        #Pack the values into a struct.
        packed_data = packer.pack(*values)

       #DEBUG
        '''
        if(isAckPacket):
            #print("Packet Data: " + str(packed_data))
            pass
        '''
    
        
        #Create a checksum with MD5 to be compared to later
        computed_checksum =  bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")

        
        #DEBUG
        '''
        if not isAckPacket:
            #print("COMPUTED CHECKSUM: " + str(computed_checksum))
            #print("RECIEVED CHECKSUM: " + str(received_checksum))
            #print("RECEIVED SEQ: " + str(received_sequence))
            #print("CURRENT SEQ: " + str(self.currAckSeq))
            pass
        '''


        #Create an Ack checksum to be added to the ack Packet that we may use later
        #Same way as packing and creating a checksum for a normal Datagram
        ack = (received_sequence,received_size)
        packer = struct.Struct('I I')
        packed_data = packer.pack(*ack)
        checkSum =  bytes(hashlib.md5(packed_data).hexdigest(), encoding="UTF-8")



        #if the Packet we recieved is an Acknowledgement Packet, then check it's Sequence with
        # our current sequence. If it is equal, then that means the packet we sent has been
        # received. So Swap our Ack Sequence, and turn off our timer.
        if(isAckPacket):
            if(received_sequence != self.sendAckSeq):
                #print("Ack Checksum Failed, Duplicate Ack")
                pass
            else:
                self.sendAckSeq = 1 - self.sendAckSeq
                self.inTransit = False
                self.startTime = None
                self.currPacketInfo = None
                self.repeatSend = False
                #print("Received Ack Packet, sendACK SWAPPED TO: " + str(self.sendAckSeq))       
        


        #If it is not an Ack Packet, then we had received a normal message. So Check if the packet is corrupt by checking it's 
        # checksum with our own comuted checksum.
        #          --> If it is different, then skip everything and don't send an acknowledgement.
        #          --> if it is the same, and the sequence is the same, the start building an Ack packet to
        #               Return to the sender, and return the message.
        #
        #   If the information is file information, then instead of printing out the message, return the
        #       Raw Binary data.
        elif (received_checksum == computed_checksum) and (int(received_sequence) == int(self.recvAckSeq)):
            #Try to Decode the information.
            try:
                received_text = received_data[:received_size].decode()          
            except UnicodeDecodeError:
                return("ERROR DECODING")

            #creack Ack Packet
            ackPacketInfo = (self.recvAckSeq,received_size,checkSum)
            ackPacketFormat = struct.Struct(f'I I 32s')
            ackPacket = ackPacketFormat.pack(*ackPacketInfo)

            #Send the Ack Packet back to the server
            clientSocket.sendto(ackPacket,(serverName,int(serverPort)))


            #If we are not sending a message, then Print the message we received and the ">" at the start of the line
            if not self.sendingFile:
                print(received_text)
                print(">",end = "", flush = True)

            #Toggle our Ack Sequence
            self.recvAckSeq = 1 - self.recvAckSeq


            #If we are receiving a file, then return the text, else return the binary data
            if not self.recivingFile:
                return(received_text)
            else:
                return(received_data)


        #Duplicate Check If the Checksum is the same, and the sequene changed, then that means it was a duplicate message.
        # Ie, the Ack was lost on the way back. So Resend an Ack packet to the source to try and tell them that 
        # the message was already sent. Do not print or return the duplicate
        elif (received_checksum == computed_checksum) and int(received_sequence) != int(self.recvAckSeq):
            seqToSend = 1 - self.recvAckSeq

            #creack Ack Packet
            ackPacketInfo = (seqToSend,received_size,checkSum)
            ackPacketFormat = struct.Struct(f'I I 32s')
            ackPacket = ackPacketFormat.pack(*ackPacketInfo)

            #Send to server
            clientSocket.sendto(ackPacket,(serverName,int(serverPort)))


        #Packet was corrupt if the checksums were not the same, so don't do anything with the information
        else:
            #print("PACKET CORRUPT, NOT SENDING ACK")
            pass

    #Sends a packet with the defined data to the addr. Starts a timer and some flags depending on the 
    #   region it was called from.
    #   If it is sending bytes, then is a repeated message that has been sent already once.
    #       so toggle some flags
    #   Else, it is a new message and try to encode it.
    #       Make a struct in the format of a UDP Datagram and send it to the specified client.
    def sendPkt(self,dataToSend,socket):
        if(self.repeatSend == True):
            self.startTime = time.time()
            self.inTransit = True
            self.receivedAck = False
            socket.sendto(dataToSend,(serverName,int(serverPort)))

        else:
            if(isinstance(dataToSend,bytes)):
                data = dataToSend
            else:
                data = dataToSend.encode()

            #Size of Data  
            if data == None:
                size = 0
            else:
                size = len(data)

            #Compute the checksum
            packet_tuple = (self.sendAckSeq,size,data)
            packetStruct = struct.Struct(f'I I {MAX_STRING_SIZE}s')
            packedData = packetStruct.pack(*packet_tuple)
            checksum =  bytes(hashlib.md5(packedData).hexdigest(), encoding="UTF-8")

            #create Actual Packet that we will send
            packet_tuple = (self.sendAckSeq,size,data,checksum)
            UDP_packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
            UDP_packet = UDP_packet_structure.pack(*packet_tuple)


            #Tell the rest of the RDT that a packet has been sent out
            # and start the timer for timeout
            socket.sendto(UDP_packet,(serverName,int(serverPort)))
            self.startTime = time.time()
            self.inTransit = True

            #Record the packet that we just sent in case we need it later.
            self.currPacketInfo = UDP_packet

#Start Message
print("STARTED")

#Make an RDT for the client, and send a Register message so the server can
#   Add you to the list of users
currRDT = rdt()
currRDT.sendPkt(("REGISTER " + name + " CHAT/1.0"),clientSocket)


#Signal Handler for Ctrl+C to gracefully Exit
#Sends the Server the Disconnect message, then exit.
#****SHOULD NOT NEED RECOGNITION FROM SERVER TO CLOSE YOUR CLIENT****#
#Server will timeout the user if the message is lost.
def signalHandler(sig,fram):
    print("\nInterrupt Received, Shutting Down ...")
    currRDT.sendPkt("DISCONNECT " + name + " CHAT/1.0",clientSocket)
    sys.exit(0)

#A method to format the return Message of a file Acceptance from the server
def filterTerms(string):
    string = string.replace("'","")
    string = string.replace("[","")
    string = string.replace("]","")    
    termList = string.split(",")
    return termList


#CTRL+C Hancler
signal.signal(signal.SIGINT, signalHandler)
#Counter for File Sending
counter = 0

#Loop to go through stdin and the clientSocket
while True:
    
    rSocket,wSocket,eSocket = select.select(rList,wList,[])
    
    #Checks the clientSocket for anything arriving.
    for s in rSocket:
        if s == clientSocket:
            #Assumes the message is not an Acknowledgement Packet, and Receives a msg from the clientSocket
            isAckPacket = False
            recvPacket,addr = clientSocket.recvfrom(1024)

            #There is an unpacker for normal DataGrams and one an Acknowledgement Packet
            unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
            unpackerAck = struct.Struct(f'I I 32s')

            #Try to unpack the recv packet in the way of a datagram. If it cannot, then 
            #   Assume it is an Ack Packet, so toggle flag and unpack it as an Ack Packet
            try:
                packetToRead = unpacker.unpack(recvPacket)
            except struct.error:
                isAckPacket = True
                packetToRead = unpackerAck.unpack(recvPacket)

            #The Message to be read/formatted is returned from the Recv Function
            msg = currRDT.recvPkt(packetToRead,isAckPacket)


            #The only two Messages we need to do somethign with are the File Acceptance Message
            # and the disconnect/Error message.

            if msg != None:
                if currRDT.sendingFile:
                    splitMsg = msg.split(":")
                    #   If it is a file Acceptance message, then format the information
                    #   and make a fileInfo class, add it to our list of Files to send
                    #   And open the file.  
                    if splitMsg[0] == "FILEINFO":
                        currRDT.readyToSend = True
                        info = infomationOfTheFile()
                        info.fileName = splitMsg[1]
                        info.fileTerms = filterTerms(splitMsg[2])
                        info.fileSize = splitMsg[3]
                        info.numPackets = int(splitMsg[4])
                        info.file = open(info.fileName,"rb")

                        currRDT.listToSend.append(info)
                
                    #   If it is an Error/Disconnect Message, then just exit
                    if splitMsg[0] == "ERROR" or splitMsg[0] == "DISCONNECT":
                        sys.exit(0)


    #Needed a timeout for the std.in separately from the ClientSocket
    rSocket2,wSocket2,eSocket2 = select.select(rlist2,wList,[],1)
    if rSocket2:
        for w in wSocket2:
            #Prints out ">" before every line.
            print(">",end = "", flush = True)
            tempMsg = sys.stdin.readline().rstrip()
            splitMsg = tempMsg.split(" ",2)
            
            #If there already is a packet in transit/no ack received yet, 
            #Then let the user know.
            if currRDT.inTransit:
                print("Please wait for Previous Packet")
                print(">",end = "", flush = True)

            #Checks if it is an empty string. If it is, then skip this loop
            if tempMsg == '':
                continue
            
            elif (splitMsg[0] == "!attach"):
                #Sends the Server a msg saying we're going to send a file now
                #along with specified file Info.
                if len(splitMsg) > 2:
                    fileName = splitMsg[1]

                    #If the file exists, then go through, else tell the user
                    if os.path.isfile(fileName):                                                     
                        fileInfo = os.stat(fileName)                        #File Information
                        fileSize = fileInfo.st_size                         #File Size
                        print("File size is: " + str(fileSize) + " bytes")  #Tells user How large the file is
                        numPackets = int(fileSize/256)                      #Number of Packets Needed
                        numPackets += 1  
                        print("Num Packets to be Sent: " + str(numPackets)) #Tells user amount of packets
                        msgToSend = ("@" + name + ": " + tempMsg + " " + str(fileSize) + " " + str(numPackets)) #Prep the message to send to the server

                        #If the currently is something in transit already, then don't send the request.
                        if(currRDT.inTransit != True):
                            currRDT.sendPkt(msgToSend,w)
                            currRDT.sendingFile = True
                        else:
                            print("Please wait for previous File to Finish")
                    else:
                        print("File does not exist")
                else:
                    print("Please enter Terms")
                    
            #Records what is written in std.in.
            #If there is nothign in transit, then we can send the message to the server.
            #If the message was an exit command, then just exit. Same logic as the
            #Signal handler
            else:
                if currRDT.inTransit != True:
                    msgToSend = ("@" + name + ": " + tempMsg)
                    currRDT.sendPkt(msgToSend,w)
                    if (splitMsg[0] == "!exit"):
                        print("Disconnecting from Server.")
                        sys.exit(0)

    #If there is nothing in Std.in then we can proceed to do the following.
    else:

        #If there is a file that is ready to be received, and every time we want to send the next
        #   part of the file data, If nothing is currently being waited on,
        #   then we can send the data.
        if len(currRDT.listToSend) > 0 and currRDT.inTransit == False:
            info = currRDT.listToSend[0]

            #If we haven't sent all the packets, then read from the file,
            #and send the data to the server.
            #Increment counter and tell user we sent a packet
            #THIS SHOULD BE IN ORDER THROUGH PACKET ERROR AND LOSS BECAUSE OF 
            #THE INTRANSIT CONDITION
            if(counter < info.numPackets):
                currRDT.sendingFile = True
                filePkt = info.file.read(256)
                currRDT.sendPkt(filePkt,clientSocket)
                counter += 1
                print("Sent Packet " + str(counter) + " of " + str(info.numPackets))

            #If We have sent enough packets, then the file is done being read from.
            #So we can remove the file from the list of files to be sent,
            #close the file, and reset the counter.
            #as well as tell the user we are done.
            else:
                currRDT.sendingFile = False
                currRDT.listToSend.remove(currRDT.listToSend[0])
                info.file.close()
                counter = 0
                print("FINISHED SENDING")
                print(">",end = "", flush = True)


        #This is the timeout Function for the server's Ack Packets
        #   If the client doesn't receive an acknowledgement Packet, the "inTransit" flag will
        #   never toggle. Every time we send a repeat, we update the RDT's time, and 
        #   if the time > 1s, send the info again.
        if currRDT.inTransit == True:
            #TIMEOUT FUNCTION TO RESEND PACKETS.
            if (time.time() - currRDT.startTime) > 1:
                #print("LEN IS: " + str(len(currRDT.currPacketInfo)))
                currRDT.repeatSend = True
                currRDT.sendPkt(currRDT.currPacketInfo,clientSocket)
