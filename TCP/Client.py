#####################################
#   Author: Darwin Liao             #
#       Student Num: 250959696      #
#       Date: Oct 17th              #
#       Assignment 2                #
#####################################
from socket import *
import signal
import sys
import selectors
import select
import os
import time
from urllib.parse import urlparse

#parsing command line arguments
#argParser = argparse.ArgumentParser(usage="[username] [chat://host:port]")
name = str(sys.argv[1])#"david"
url = str(sys.argv[2])#"chat://localhost:12000"

#Gets the Host/Servername and ServerPort 
tempStr = urlparse(url)
parsedURL = tempStr[1].split(":")
serverName = parsedURL[0]
serverPort = parsedURL[1]

#Client Socket Setup and connecting to Server
clientSocket = socket(AF_INET, SOCK_STREAM)
clientSocket.connect((serverName,int(serverPort)))
clientSocket.setblocking(False)
clientSocket.send(("REGISTER " + name + " CHAT/1.0").encode())
socketList = [clientSocket, sys.stdin]

###Write list. contains the client socket as it is the only
#       Socket we will write to
wList = [clientSocket]
recvFile = False

###Function to check if the message is a disconnect message.
#   Returns True if it is,
#   Returns False if it is not.
def isExit(msg):
    words = msg.split(" ")
    if words[0] == "DISCONNECT" and words[1] == "CHAT/1.0":
        return True
    elif msg == '':
        return True
    else:
        return False

def getFileSize(filePath):
    fileSize = str(os.path.getsize(filePath))
    return fileSize

def sendFile(socket,fileName,terms):
    try:
        file = open(fileName, 'rb')
        data = file.read(2048)        
        while (data):
            print("Sending...")
            socket.send(data)
            data = file.read(2048)
            
        file.close()
        print("File Sent")
        
    except IOError:
        print("Error Opening File")

#Receiving a file from the server. Makes a new file with the info
#   obtained from server
# Checks when it is done by looking at file size
def receiveFile(socket,fileName,fileSize,fileSender):
    total = 0

    file = open(fileName,'wb')
    data = socket.recv(2048)

    total = len(data)
    while(data):
        print("Receiving File from " + fileSender)
        file.write(data)

        if(str(total) != fileSize):
            print("Attempting to Recieve")
            data = socket.recv(2048)
            total += len(data)

        if(int(total) >= int(fileSize)):
            break;
        
    file.close()
    print("Done Recieving File from " + str(fileSender))
    print("Size of File is: " + str(total))


###Signal Handler for Ctrl+C interrupt
#   Prints out interrupt message and sends the Disconnect Message
#       To the server. Then shuts itself down.
def signalHandler(sig,fram):
    print("Interrupt Received, Shutting Down ...")
    clientSocket.send(("DISCONNECT " + name + " CHAT/1.0").encode())
    sys.exit(0)


#Signal Handler for CTRL+C
signal.signal(signal.SIGINT, signalHandler)

###While loop to constantly update and iterate through the read and write lists.
while(True):
    rSocket,wSocket,eSocket = select.select(socketList,wList,[])

    ###If the current item is the client socket, then Tries to receive any
    #       Messages that may have been sent and decodes them.
    #       Checks if it is the exit msg.
    #            If it is, then exit the program
    #       Checks if the message is not blank.
    #           If it is, then print out the message, and check if it is an
    #           Error msg, then Actaccordingly.
    #       Also catches any Errors that are the result of
    #           setBlocking(0). and lets them through
    for s in rSocket:
        
        #if s is the clientSocket, then reading info from a socket
        if s == clientSocket:
            try:
                #Recieves msg and decodes the msg
                msg = s.recv(2048).decode()
                time.sleep(0.005)

                
                #Checks if it is the Exit Message
                if isExit(msg):
                    print("Disconnected From Server ... Exiting!")
                    sys.exit(0)

                #Checks if it is recieving a file. If it is, then 
                elif (str(msg.split(",")[0]) == "FILEINFO"):
                    fileName = msg.split(",")[1]
                    size = msg.split(",")[2]
                    sender = msg.split(",")[3]
                    receiveFile(s,fileName,size,sender)
                   
                #Checks if it is not blank.                    
                elif msg:
                    #Print the Message onto Terminal
                    print("\n" + msg)
                    #Checks if it is an error
                    if (str(msg) == "400 Invalid Registration" or str(msg) == "401 Client Already Registered"):
                        sys.exit()
                        
                print(">",end = "", flush = True)


                            
            except(BlockingIOError):
                pass
            
        ###If we are not reading from the input socket, then we're reading from
        #       The stdin instead of the socket.
        #           This allows us to accept outputs from the server
        #           while still checking for inputs from the input line.
        #       If we are reading rom the input line, then we can write
        #           to the sockets in the wSocketList
        #           (Since this is the only time we should be sending a message)
        elif s == sys.stdin:
            #Goes through the writeList
            for w in wSocket:
                
                #Prints out ">" before every line.
                print(">",end = "", flush = True)
                tempMsg = sys.stdin.readline().rstrip()
                splitMsg = tempMsg.split(" ")

                
                #Checks if it is an empty string. If it is, then skip this loop
                if tempMsg == '':
                    continue
                
                elif (splitMsg[0] == "!attach"):
                    if len(splitMsg) > 2:
                        msgToSend = ("@" + name + ": " + tempMsg + " " + getFileSize(splitMsg[1]))
                        w.send(msgToSend.encode())
                               
                        sendFile(w,splitMsg[1],splitMsg[2])
                
                #If it isn't an empty String, then send the msg
                #@Username: message
                else:
                    msgToSend = ("@" + name + ": " + tempMsg)
                    w.send(msgToSend.encode())
