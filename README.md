# CHATROOM
School work and additional add-ons to the school project that I had implemented (UDP functions with multiple Clients).

Was tasked to create a chat room using python and no usage of threads. 
Was to include commands usable for user, follow list, graceful exits, and error handling. 

UDP and TCP connections using Python's Sockets library and Selectors Library.

TCP Connection version had error handling done in a very primitive way,
by sending a message to the server and responding in kind

UDP COnnection version implemented a simple RDT3.0 with Stop-and-wait protocol.
Did not need to implement pipelining since it was harder to test with what I had. 

TODO: Implement pipelining and buffer, User Login, Having a UI
