#####################################
#   Author: Darwin Liao             #
#   Student Num: 250959696          #
#   Date: Oct 17th/Nov 1st/Dec 4th  #
#   Assignment 2/3/4                #
#####################################
from ctypes import sizeof
import selectors
import select
import signal
import struct
import sys
import os
import time
import hashlib
from socket import *
#Max String Size for a message.
MAX_STRING_SIZE = 256

###Init###
sel = selectors.DefaultSelector()

###Making Server Socket###
serverPort = 12000
serverSocket = socket(AF_INET,SOCK_DGRAM)  #Creates UDP welcoming socket
serverSocket.bind(("localhost",serverPort))
#Some Lists to contain all the users and their handles for easier access
socketList = [serverSocket]
userList = []
userHandleList = []

#A class that details a file and it's information
class fileInfo:
    def __init__(self,sender,fileName,terms,size,numPackets):
        self.fileName = fileName
        self.sender = sender
        self.terms = terms
        self.size = size
        self.numPackets = numPackets
        self.data = []

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
        self.wordList = []
        self.sendAckSeq = 0
        self.recvAckSeq = 0
        self.startTime = time.time()
        self.inTransit = False
        self.isLeaving = False
        self.fileList = []
        self.pktCounter = 0
            
    def recvPkt(self,dataToRead,isAckPacket,userAddr):
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
            ackPacketInfo = (self.recvAckSeq,received_size,checkSum)                    #Create Ack Packet
            ackPacketFormat = struct.Struct(f'I I 32s')
            ackPacket = ackPacketFormat.pack(*ackPacketInfo)
            serverSocket.sendto(ackPacket,userAddr)                                     #Send the Ack Packet back to the Sender
            self.recvAckSeq = 1 - self.recvAckSeq                                       #Toggler Ack Sequence

            if len(self.fileList) > 0:                                                  #If the data was sent during the time we are 
                                                                                        #Requesting a file, Return Binary data                                               
                return(received_data)

            else:                                                                       #If it wasnt, then print out the msg, and return the decoded msg.
                received_text = received_data[:received_size].decode()
                print("Message was: " + received_text)
                return(received_text)


        #Duplicate Check If the Checksum is the same, and the sequene changed, then that means it was a duplicate message.
        # Ie, the Ack was lost on the way back. So Resend an Ack packet to the source to try and tell them that 
        # the message was already sent. Do not print or return the duplicate
        elif (received_checksum == computed_checksum) and int(received_sequence) != int(self.recvAckSeq):
            seqToSend = 1 - self.recvAckSeq
            #Create Ack Packet with the previous Ack Sequence
            ackPacketInfo = (seqToSend,received_size,checkSum)
            ackPacketFormat = struct.Struct(f'I I 32s')
            ackPacket = ackPacketFormat.pack(*ackPacketInfo)

            serverSocket.sendto(ackPacket,userAddr)                                      #Send the ack back

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
    def sendPkt(self,dataToSend,socket,clientAddr):
        if(isinstance(dataToSend,bytes)):
            if not self.isLeaving:
                self.startTime = time.time()
            self.inTransit = True
            socket.sendto(dataToSend,clientAddr)

        else:
            try:
                data = dataToSend.encode()
            except AttributeError:
                data = dataToSend

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

            #Create The Actual Packet that we will send
            packet_tuple = (self.sendAckSeq,size,data,checksum)
            UDP_packet_structure = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
            UDP_packet = UDP_packet_structure.pack(*packet_tuple)

            #Send to Client
            socket.sendto(UDP_packet,clientAddr)
            #If the client wasn't sending an exit command, then start the timer
            #       Else, no need for a response since the client has already disconnected
            if not self.isLeaving:
                self.startTime = time.time()
            #Tell the rest of the RDT that a packet has been sent out, to stop other things from occuring before it
            # receives an Ack.
            self.inTransit = True

            #Record what we sent so we may send it again if needed.
            self.currPacketInfo = UDP_packet

### USER CLASS
#   @Brief Contains the information of a user connecting to the server.
#           Fields like the username, handle, address, who they are following, 
#           and each user's own RDT.
#           Also contains the following methods.
#
class user:

#   @__init__: Initialization
    def __init__(self,username,addr):
        self.name = username
        self.handle = "@" + str(self.name)
        self.addr = addr
        try:
            self.clientHost = addr[0]
            self.clientPort = addr[1]
        except:
            pass
        self.rdt = rdt()
        self.followList = ["@all",self.handle]


#   @setClientInfo(self,addr): sets the addr of the client.
    def setClientInfo(self,addr):
        self.clientHost = addr[0]
        self.clientPort = addr[1]

#   @getFollowList(self):returns the followList of the user
    def getFollowList(self):
        return str(self.followList)

#   @getUserList(self): returns the userList of ther server
    def getUserList(self):
        return str(userHandleList)

#   @exit(self): toggles the exit flag, and returns the message
#               To disconnect the user
    def exit(self):
        self.rdt.isLeaving = True
        print("USER "  + self.name + " Disconnected")
        return str("DISCONNECTED USER")


#   @follow(self,term): Adds the term to the user's follow list
#               And returns the sepcified errors for situations 
#               where the user is already following a term
    def follow(self,term):
        if term in self.followList:
            return("Already Following: " + "'" + term + "'")
        else:
            self.followList.append(str(term))
            return("You are now following: " + "'" + term + "'")
#   @unfollow(self,Term): Attemps to remove the term from the user's follow list
#               Returns an error message when an invalid attempt is made like 
#               trying to unfollow himself, or unfollowing something they are not 
#               following.
    def unfollow(self,term):
        try:
            for x in self.followList:
                if (term == "@all" or term == self.handle):
                    print(self.handle + " tried to unfollow " + "'" + term + "'")
                    return("Cannot unfollow " + "'" + term + "'")
                
                elif x == term:
                    self.followList.remove(x)
                    print(self.handle + "has unfollowed " + "'" + term + "'")
                    return ("No Longer Following " + "'" + term + "'")
            else:
                return("You are not following this Term")
                
        except(ValueError):
            print("Error Removing" + "'" + term + "'" + "from" + self.handle)
            return("You are not following this Term")


#   @readyFileInfo(self,fileName,terms,fileSize,pckAmount):
#               This makes a fileInfo class and adds it to the user's RDT's 
#               list of files that it needs to recieve.
#               Sends the user client a message saying that it is ready to receive 
#               file information.
    def readyFileInfo(self,fileName,terms,fileSize,pckAmount):
        self.rdt.fileList.append(fileInfo(self,fileName,terms,fileSize,pckAmount))
        return str("FILEINFO:" + str(fileName) +":"+ str(terms) +":"+ str(fileSize) +":"+ str(pckAmount))

#Start Message
print("STARTED")


#A loop for the select and the socket to be constantly checked.
while True:
    rSocket,wSocket,eSocket = select.select(socketList,socketList,[],1)

    #Goes through the socket (only one)
    for curSocket in rSocket:
        if curSocket == serverSocket:                                           #This statement is useless. Should Always be the serverSocket, but just in case.
            
            #Assumes the message is not an Acknowledgement Packet, and Receives a msg from the serverSocket
            isAckPacket = False
            recvPacket, addr = serverSocket.recvfrom(1024)

            #There is an unpacker for normal DataGrams and one an Acknowledgement Packet
            unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
            unpackerAck = struct.Struct(f'I I 32s')

            #Try to unpack the recv packet in the way of a datagram. If it cannot, then 
            #   Assume it is an Ack Packet, so toggle flag and unpack it as an Ack Packet
            try:
                packetToRead = unpacker.unpack(recvPacket)
            except struct.error:
                packetToRead = unpackerAck.unpack(recvPacket)
                isAckPacket = True


            #CLIENT DIFFERNTIATION
            #Assume the client does not exist in the list of clients yet.
            #       Go through the userList, and if it finds an Address Match, then 
            #       that means the client is already added, so use it's RDT and 
            #       manage the data received.
            exists = False
            for client in userList:
                if client.addr == addr:
                    exists = True

                    #If the client has recently been asked to received a file, and the info isn't an Ack packet,
                    #       Make a file with the name previously Specified by the Client.
                    #       And record the amount of packets that will be file information based off of
                    #       The file size.
                    #
                    #       Then keep on reading the serverSocket for data on the File until the specified
                    #       amount of packets have been read in.
                    #
                    #
                    if len(client.rdt.fileList) > 0 and not isAckPacket:
                        newFile = open(client.rdt.fileList[0].fileName,"wb")
                        numPkt = int(client.rdt.fileList[0].numPackets)

                        #While the amount of packets have not been reached, then keep on reading from the socket
                        while client.rdt.pktCounter < numPkt:

                            #If no information has arrived, then don't try to process it
                            if(recvPacket != None):
                                data = client.rdt.recvPkt(packetToRead,isAckPacket,addr)

                            #if the RDT returned nothing, that means the packet info was already received/corrupt,
                            #so don't add it.
                            #If it is not empty, then increase the packet Counter, tell that we have added one more packet,
                            # then write it to the file.
                            if data != None:
                                client.rdt.pktCounter += 1
                                print("Recieving Pkt " + str(client.rdt.pktCounter) + " of " + str(client.rdt.fileList[0].numPackets))
                                newFile.write(data)

                            #As long as the amount of packets has not reaced the specified amount, 
                            #keep on reading from the socket and assume it is file information.
                            if client.rdt.pktCounter < numPkt:
                                recvPacket, addr = serverSocket.recvfrom(1024)
                                unpacker = struct.Struct(f'I I {MAX_STRING_SIZE}s 32s')
                                if recvPacket != None:
                                    packetToRead = unpacker.unpack(recvPacket)
                        
                        #Once the file is done being read, close the file, reset the packet counter,
                        #   and remove the file from the fileList. (This list was originally going to be used as a list to send to every client)
                        newFile.close()
                        client.rdt.pktCounter = 0
                        client.rdt.fileList.remove(client.rdt.fileList[0])
                        print("FINISHED RECEIVING FILE")
                        break
                    


                    #IF There was no file to be copied, then just receive the message like normal
                    #then format it to check if any commands were issued.
                    #If they were, then call the respective method, which will return a message
                    #to be returned to the user
                    else:
                        msg = client.rdt.recvPkt(packetToRead,isAckPacket,addr)
                        
                        #The Following is to check the commands, and as well as what words were said.
                        if msg != None:
                            splitMsg = msg.split(" ",2)
                            words = msg.split(" ")
                            fixHandle = words[0].replace(words[0],words[0].strip(":"))
                            words.remove(words[0])
                            words.append(fixHandle)
                            client.wordList = words

                            #If there is a possibility of a command being printed
                            if len(splitMsg) > 1:


                                #Returns the Follow Command to be send back to the client
                                if splitMsg[1] == "!follow":
                                    try:
                                        client.rdt.currPacketInfo = client.follow(splitMsg[2])
                                    except:
                                        client.rdt.currPacketInfo = "Please Enter Term"


                                #Returns the Unfollow Command to be sent back to the client
                                if splitMsg[1] == "!unfollow":
                                    try:
                                        client.rdt.currPacketInfo = client.unfollow(splitMsg[2])
                                    except:
                                        client.rdt.currPacketInfo ="Please Enter Term"


                                #Returns the list that the user is following
                                if splitMsg[1] == "!follow?":
                                    client.rdt.currPacketInfo = client.getFollowList()


                                #Returns the userList
                                if splitMsg[1] == "!users":
                                    client.rdt.currPacketInfo = client.getUserList()


                                #returns the exit Command To the user and tells the server that they have disconnected.
                                if splitMsg[1] == "!exit" or splitMsg[0] == "DISCONNECT":
                                    client.rdt.currPacketInfo = client.exit()
                                

                                #Tells the server that the user wants to send a file with the following Information
                                #   Here, we make a fileInfo obj, add it to the user's fileList, and
                                #   send the user back a confirmation that they may begin sending file data
                                if splitMsg[1] == "!attach":
                                    tempSplit = msg.split(" ")
                                    fileName = tempSplit[2]                                                                 #FileName of the file being sent
                                    numPackets = tempSplit[-1]                                                              #Last Number is the amt of packets needed to be send/recv
                                    fileSize = tempSplit[-2]                                                                #File Size is 2nd Last Term
                                    terms = tempSplit[3:-2]                                                                 #Grabs all the terms applied to the File
                                    fileToSend = fileInfo(client,fileName,terms,fileSize,numPackets)
                                    client.rdt.currPacketInfo = client.readyFileInfo(fileName,terms,fileSize,numPackets)    #Send a msg to the Origin to let them know we are ready to receive.
                                    
                            #Sending message to other users if they are following Terms.
                            '''
                            for receiver in userList:
                                if receiver != client:
                                    for x in receiver.followList:
                                        if x in words and len(client.rdt.fileList) <= 0:
                                            receiver.rdt.sendPkt(msg,curSocket,receiver.addr)    
                            '''
            #IF THE CLIENT DOESN'T EXIST, THEN ADD IT IN
            #If we have gone through the userlist and there is no matching Addr,
            #then the user doesn't not exist in our list yet,
            #so we make an RDT for the user and make a user Class for them.
            if exists == False:
                tempRDT = rdt()
                msg = tempRDT.recvPkt(packetToRead,isAckPacket,addr)

                if msg != None:

                    #If it is a Register Message from the user, then we may begin making the Class for them
                    if msg.split(" ")[0] == "REGISTER":
                        name = msg.split(" ")[1]
                        newUser = user(name,addr)                                                #User Info
                        newUser.rdt.recvAckSeq = 1 - newUser.rdt.recvAckSeq                      #Toggle the Acknowledge Seq since they sent the Register Msg Already


                        #Check in case we have the same name as another user or no name. If we do, then disconnect them and 
                        #do not add them.
                        for client in userList:
                            if name == False:
                                print("Disconnecting User")
                                newUser.rdt.sendPkt("ERROR 400 Invalid Registration",curSocket,newUser.addr)
                                break

                            if name == client.name:
                                print("Disconnecting User")
                                newUser.rdt.sendPkt("ERROR 401 Client Already Registered",curSocket,newUser.addr)
                                break

                        #If no issues, then add them to the userlist, and their handle to the handleList,
                        #and send them a welcome message.
                        else:
                            userList.append(newUser)
                            userHandleList.append(newUser.handle)
                            newUser.rdt.sendPkt("Welcome " + str(newUser.name),curSocket,newUser.addr)


        #Handles sending messages back to the users.
        #   If the user is stated to leave, then remove them from the list
        for origin in userList:
            if origin.rdt.isLeaving:
                userHandleList.remove(origin.handle)
                userList.remove(origin)
                continue
                

            #If they have information to be sent back, and they are not currently waiting on a packet,
            #Then we can send the user another packet of whatever they needed to be sent based off of
            #whatever command they needed.
            if origin.rdt.currPacketInfo != None and origin.rdt.inTransit == False:
                origin.rdt.sendPkt(origin.rdt.currPacketInfo,curSocket,origin.addr)
                

            #This is where the Timeout for messages is. If the server has sent somethign back to the
            # user but has not recieved an acknowledgement for more than 1 second,
            # send them the message again.
            if origin.rdt.inTransit == True:
                if(time.time() - origin.rdt.startTime) > 1:
                    origin.rdt.sendPkt(origin.rdt.currPacketInfo,curSocket,origin.addr)
                    #print("SENDING FROM TIMEOUT")


            #Adds timeout for disconnection If there client has not typed anything for a long time
            #       Or if the disconnect message was lost.
            if(origin.rdt.startTime != None):
                if(time.time() - origin.rdt.startTime) > 60:
                    origin.rdt.sendPkt("ERROR YOU BEEN DISCONNECTED FOR TIMEOUT",curSocket,origin.addr)
                    userHandleList.remove(origin.handle)
                    userList.remove(origin)
                    continue


