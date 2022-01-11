#####################################
#   Author: Darwin Liao             #
#       Student Num: 250959696      #
#       Date: Oct 17th/Nov 1st      #
#       Assignment 2/3              #
#####################################
import selectors
import select
import signal
import sys
from socket import *

###Init###
sel = selectors.DefaultSelector()

###Making Server Socket###
serverPort = 12000
serverSocket = socket(AF_INET,SOCK_STREAM)  #Creates TCP welcoming socket
serverSocket.setblocking(False)
serverSocket.bind(("",serverPort))
serverSocket.listen(25)                     #Begins listening to incoming TCP requests
print("Will wait for connections at Port: " + str(serverPort))

###Lists to contain all users and sockets###
socketList = [serverSocket]
clientList = []                             #clientList format is now a list of user objs.
fileList = []                            #List of fileInfo objs waiting to be broadcast.


### A Class to contain all the information in a file. ###
#       Contains:
#           FileName
#           Sender
#           file Tags
#           Size(in bytes) of file.
class fileInfo:
    def __init__(self,sender,fileName,terms,size):
        self.fileName = fileName
        self.sender = sender
        self.terms = terms.split(" ")
        self.size = size

### A class for users/clients connecting to the server. ###
#       Contains the Socket, username they registered
#       Handle, and the list of terms they each follow
#
#       I probably should have made different methods
#           for each one but ¯\_(ツ)_/¯
###########################################################        
class user:
    #Init for a user
    def __init__(self,socket,username):
        self.socket = socket
        self.username = username
        self.handle = "@" + username
        self.followList = ["@all",self.handle]

    ###Commands### 
    def command(self,cmdLine):
        cmd = cmdLine.split("!")[1]

        ###Follow List Command###
        if(cmd == "follow?"):
            print(self.handle + " has requested his follow List")
            return self.followList

        ###Shows all users handles###
        elif(cmd == "users"):
            return getUserList()

        ###exit Command###
        elif(cmd == "exit"):
            disconnect(self.username)
            return("DISCONNECT CHAT/1.0")
        
        try:
            cmd = cmdLine.split(" ",1)[0]
            term = cmdLine.split(" ",1)[1]
            
        except(IndexError):
            print(self.handle + " Entered an unfinished or unknown Command")
            return ("Invalid Command")

        ###Follow a Term Command###
        if(cmd == "!follow"):
            for x in self.followList:
                if x == term:
                    print(self.handle + " attempted to follow an existing term")
                    return ("You are already following this Term")
                
            self.followList.append(str(term))
            print(self.handle + " has followed " + "'" + term + "'")
            return ("Now Following: " + "'" + term + "'")
        
        ###Unfollow Command###    
        elif(cmd == "!unfollow"):
            try:
                for x in self.followList:
                    if (term == "@all" or term == self.handle):
                        print(self.handle + " tried to unfollow " + "'" + term + "'")
                        return("Cannot unfollow " + term)
                    
                    elif x == term:
                        self.followList.remove(x)
                        print(self.handle + "has unfollowed " + "'" + term + "'")
                        return ("No Longer Following " + "'" + term + "'")
                else:
                    return("You are not following this Term")
                    
            except(ValueError):
                print("Error Removing" + "'" + term + "'" + "from" + self.handle)
                return("You are not following this Term")

        ####Attaching a file command###
        elif(cmd == "!attach"):
            if len(cmdLine.split(" ")) < 4:
                print("Missing Arguments")
                return("Missing Arguments")
            else:
                fileName = cmdLine.split(" ")[1]
                term = cmdLine.split(" ",2)[2]
                size = cmdLine.split(" ")[3]

            
            tempFile = fileInfo(self.handle,fileName,term,size)
            getFileData(self,tempFile)
            return("Server Has Received File")

        #if it isn't any of these commands, then it's an unknown command
        else:
            return("Invalid Command")

###Getting file Data from the client
#It takes in the name, size, and sender info
#and makes a copy of it serverside
def getFileData(client,fileInfo):
    fileName = fileInfo.fileName
    fileSize = fileInfo.size
    sender = fileInfo.sender

    total = 0
    
    file = open(fileName , 'wb')
    data = client.socket.recv(2048)

    total = len(data)
    while(data):
        print("Receiving File from " + fileInfo.sender)
        file.write(data)
        
        if(str(total) != fileSize):
            print("Attempting to Recieve")
            data = client.socket.recv(2048)
            total += len(data)
            
        if(int(total) >= int(fileSize)):
            break
        
    file.close()
    fileList.append(fileInfo)

    print("Done Recieving File from " + client.handle)
###Sends the above file back to the clients
#   they will only recieve if they are tagged
def sendFileData(client,fileInfo):
    fileName = fileInfo.fileName
    fileSize = fileInfo.size
    sender = fileInfo.sender

    try:
        file = open(fileName, 'rb')
        data = file.read(2048)
        while(data):
            print("Sending...")
            client.socket.send(data)
            data=file.read(2048)

        file.close()
        print("File Broadcast")

    except IOError:
        print("Error Opening File")

###A function I did for !users
#shows who's online/connected
def getUserList():
    userList = []
    for user in clientList:
        userList.append(user.handle)
    return userList


###Function for recieving messages from the specified socket
#   Takes the socket, receives any input, decodes the msg,
#       If there's no input, return false, else return
#       the decoded string.
#   Watches for the error caused by socket.setblocking(0)
#       when blocking occurs.
def receiveMsg(clientSocket):
    try:
        msg = clientSocket.recv(2048)
        if msg == False:
            return False
        return msg.decode()
    
    except(BlockingIOError):
        return False
    
###Function for sending messages to the specified socket###
#   Takes the Socket, sends the msg encoded message to
#       that socket. 
#   Watches for the error caused by socket.setblocking(0)
#       when blocking occurs.
def sendMsg(client,msg):
    try:
        client.socket.send(msg.encode())
    except(BlockingIOError):
        return False

    
###Function for finding the username given, and removing them###
#   Takes in the username, finds the corresponding client
#       in the client. Removes them from the clientList,
#       socketList, and prints out the Disconnecting Msg
def disconnect(UN):
    for client in clientList:
        if client.username == UN:
            socketList.remove(client.socket)
            clientList.remove(client)
            print("Disconnecting user " + UN)
            break;



###Checks if the message from a client is the Disconnect Mesasge###
#   If so, then return the username of the client
#   If Not, then return false
def isExit(msg):
    words = msg.split(" ")
    if words[0] == "DISCONNECT" and words[2] == "CHAT/1.0":
        return words[1]
    else:
        return False


###Handles the Ctrl+c interrupt
#   Prints out the Interrupt Message, and sends out
#       A message to all the clients that it is being Disconnected###
#       then Exits.
def signalHandler(sig,fram):
    print("Interrupt Received, Shutting Down ...")
    for s in socketList:
        if s != serverSocket:
            s.send(("DISCONNECT CHAT/1.0").encode())
    sys.exit(0)



#Signal Catcher for CTRL+C
signal.signal(signal.SIGINT, signalHandler)


###Loop for checking Clients
#   Continue to update and iterate through the read and write lists
#       for the sockets
while True:
    #Read, Write, and Error selectLists to iterate through
    rSocket,wSocket,eSocket = select.select(socketList,socketList,[])

    ###If the current Socket we're looking at is the server,
    #   then Check for any new connections,
    #       If there is a connection, get the username from the Client
    #           and check if they already exist.
    #           Print and Send the corresponding message if there is an Error
    #       IF they do not already Exist, Send them the successful
    #           registration message and add them to the socketList and
    #           clientList
    for curSocket in rSocket:
        if curSocket == serverSocket:
            #initial Connection
            clientSocket, addr = serverSocket.accept()
            name = receiveMsg(clientSocket).split(" ")[1]
            print('Connection from: ' + str(addr) + ', User: ' + str(name))

            newUser = user(clientSocket,name)

            #checking if they Exist
            for x in clientList:
                if newUser.username == False:
                    sendMsg(newUser,"400 Invalid Registration")
                    print("Disconnecting user " + userName)
                    break;
                if newUser.username == x.username:
                    sendMsg(newUser,"401 Client Already Registered")
                    print("Disconnecting user " + userName)
                    break;
                
            #If they don't exist, then add the user to the lists
            #   (Yes For: Else: is a thing)
            else:
                sendMsg(newUser, "200 Registration Successful")
                clientList.append(newUser)
                socketList.append(newUser.socket)
                

        ###If the current Socket is not the Server, meanns it is a client
        #   Check for any messages. If there is a message, print out
        #       who has send the message.
        #   Check if it is an exit message,
        #       If it is, then disconnect that user.
        #   Also check if the input is empty.
        #       If it is, then means no client connection anymore.
        #       So remove the client from the lists
        #   If it is non of these, then broadcast the message to all
        #       Other clients
        else:
            #receiving Message and Parsing it. Some black magic stuff
            #   that involves stings since I was too lazy to optimize.
            #   (Takes the first word, which is "@username:", and
            #       removes the ":" so when someone follows another
            #       user, they don't need to add the ":")
            tempMsg = receiveMsg(curSocket)
            splitMsg = tempMsg.split(" ", 1)
            words = tempMsg.split(" ")
            fixHandle = words[0].replace(words[0],words[0].strip(":"))
            words.remove(words[0])
            words.append(fixHandle)

            
            #Checks which user it is currently looking at
            for client in clientList:
                if client.socket == curSocket:
                    curUser = client
                    break;
                
            #Checks if it is Exit Message
            if isExit(tempMsg):
                disconnect(isExit(tempMsg))

            #Checks if it is empty message    
            elif tempMsg == '':
                print("Closed connection from:" + str(addr))
                socketList.remove(curUser.socket)
                clientList.remove(curUser)
            
            #Check First Letter is after the "@Username" is a "!",
            #       if it is, then it's a command and call command()
            elif splitMsg[1][0] == "!":
                cmdMsg = curUser.command(splitMsg[1])
                sendMsg(curUser,str(cmdMsg))

                if len(fileList) > 0:
                    for client in clientList:
                        sentFile = False
                        for term in client.followList:
                            for file in fileList:
                                for tag in file.terms:
                                    if term.lower() == tag.lower() and client.handle != file.sender:
                                        sendMsg(client,"FILEINFO," + file.fileName + "," + file.size + "," + file.sender)
                                        sendFileData(client,file)
                                        sentFile = True
                                        break;
                                if sentFile:
                                    break;
                            if sentFile:
                                break;
                                
                    while(len(fileList) > 0):
                        del fileList[0];

            else:    
                finalMsg = ("Received Message from user " + curUser.username + ": " + tempMsg)
                print(finalMsg)

                #broadcasts to other clients if they are following the contents
                #   of the msg
                for client in clientList:
                    sentMsg = False
                    for term in client.followList:
                        for word in words:
                            if term.lower() == word.lower() and curUser.handle != client.handle:
                                sendMsg(client,tempMsg)
                                sentMsg = True
                                break;
                        if sentMsg == True:
                            break;
                    
