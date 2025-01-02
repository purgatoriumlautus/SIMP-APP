# SIMP Protocol Implementation

**Authors:** Beztsinna Alisa, Kobelianskyi Arsenii

## Introduction
SIMP protocol is a messaging protocol for chat applications built on top of UDP. The protocol ensures reliable connection between two users for chatting. Functional abilities of an application provide users with options:

1. Request a connection, by entering the IP address of the message recipient.
2. Wait for connection for 60 seconds. When the request comes, the user has to accept or decline it.
3. When connection established, the communication channel is created until one of the users decides to terminate the connection. If a user gets a new request for connection, while in chat, the request is automatically declined.

This documentation is created to describe the most important aspects of SIMP protocol and explain how different components work with each other. Next parts of the document explain client and daemon components of SIMP protocol, their purposes, and functionalities. Describe classes created in both daemon and client code. Elaborate API’s of the application (implementation of client to daemon communication and daemon to daemon communication).

## Components

### Application Code
Application code consists of two separate files, a client and a daemon (**simp_daemon.py** and **simp_client.py**).

#### Daemon
A daemon is a server-program that runs in the background and serves the user it is connected to. When started, the daemon idles until it gets a connection request from a user. When a connection with a user is established, the daemon handles the commands which the user provides. Every user is linked to a particular daemon. When chatting, users do not communicate with each other directly. Instead, the daemon interacts with a user, and daemons communicate with another daemon.

The daemon program can be started by using an IP address as a command line parameter. Communication between daemons always occurs on **port 7777**, while communication between a daemon and its client takes place on **port 7778**.

#### Client
A program that interacts with a user via command line. Connects with a daemon, whose IP is passed at the start of the program as a command line parameter. The main purpose of the client program is to provide a reliable connection and communication between user and daemon. It takes inputs from a user and sends them to the daemon using a different, from daemon-to-daemon communication, protocol. The client program shows the user the messages from the daemon in an understandable and user-friendly manner.

The client program can be started from the command line with a daemon IP passed as a parameter.

## Classes

### Classes in simp_daemon.py (Daemon to Daemon Protocols)
Classes are used to implement the protocols, in order to improve reusability, reduce redundancy, and improve consistency.

1. **DatagramType**: Enum class used to map the bitwise value to the type of the message (\x00 → control, \x01 → chat).
2. **OperationType**: Enum class used to map the bitwise value to the type of the operation. Control datagram from the previous class can have the following operations:
   - \x02 → SYN (request a connection)
   - \x04 → ACK (acknowledge the received message)
   - \x08 → FIN (terminate the connection)
   - Chat datagrams operation is always \x01 → MESSAGE operation.
3. **ErrorType**: Used to identify errors in datagrams:
   - **WRONG_PAYLOAD_SIZE**: Payload size field in header does not match the actual payload size.
   - **UKNOWN_DATAGRAM_TYPE**: Datagram type field is not in (\x00, \x01).
   - **UKNOWN_OPERATION_TYPE**: Operation type is not in (\x01, \x02, \x04, \x08).
   - **USERNAME_ERROR**: Username could not be converted to a string or found in header.
   - **LOST_DATAGRAM**: Datagram is lost.
   - **MSG_TOO_LONG**: Message is too long.
   - **MSG_TOO_SHORT**: Message is too short.
   - **NO_PAYLOAD_EXPECTED**: If datagram type is control and operation is not error, no payload has to be transmitted.
   - **WRONG_LENGTH_SIZE**: Length header is too big or is not an integer.
   - **WRONG_SEQUENCE_NUMBER**: Sequence number is not (“\x00, \x01”).
   - **WRONG_PAYLOAD**: Payload couldn't be extracted.
4. **HeaderInfo**: Main implementation of the protocol. Used to extract headers, that contain all the necessary metadata, from messages. HeaderInfo class object has attributes that specify the type of datagram, operation type, sequence number, payload, and username. It includes an errors list containing all the errors found in the header, and an is_ok attribute indicating if the header contains errors.

### Classes in simp_client.py (Client to Daemon Communication Protocol)
1. **MessageType**: Used to identify message types for the messages sent from client and daemon and the other way around.
   - **CHAT**: Standard chat message exchanged between clients.
   - **CONNECTION**: Establishing a connection to the daemon.
   - **DISCONNECTION**: Termination of the connection from the daemon.
   - **REQUEST**: Request to start a new chat session.
   - **WAIT**: Status indicating the client is waiting for chat requests.
   - **DISCONNECT_REQUEST**: Request to terminate an active chat session.
   - **ACCEPT**: Approval of a chat request.
   - **DECLINE**: Rejection of a chat request.
   - **ERROR**: Message indicating an error or issue occurred.
2. **Header**: Contains message type and the username of the sender from the message.

## Communication

### Communication Between Client and Daemon
To connect to the daemon, the client sends the “CONNECTION” message type with their username to the daemon. If the daemon accepts the request, it sends the “CONNECTION” message type in response. If the daemon is already occupied, it sends the “ERROR” message indicating it is already occupied.

After the connection is established:
- If the daemon has pending chat requests, it asks if the client wants to accept the connection, and then the chat starts.
- Otherwise, the daemon waits for the client’s commands.

**Starting a New Chat**: The user chooses an option to request a chat and provides an IP address. The client program sends a “REQUEST” type message with the recipient’s IP address to the daemon. If the connection request is accepted by the recipient, the daemon sends an “ACCEPT” type message with the username of the recipient, and the chat starts. Otherwise, the daemon sends a “DECLINE” type message with the recipient’s username to the user. The user is redirected to the main menu, and the daemon waits for new commands.

**Waiting for a Chat Request**: The user picks an option to wait for a request. The client program sends a “WAIT” type message to the daemon. The daemon listens for a connection request for 60 seconds. If a request from another daemon comes, the daemon sends a “REQUEST” type message with the requester’s username to the user, asking if they want to accept the connection. If the user accepts, the client sends an “ACCEPT” type message to the daemon, and it continues a three-way handshake with the requesting daemon. Otherwise, the user sends a “DECLINE” type message, and the daemon sends a “FIN” datagram to the requesting daemon, meaning the user did not accept the connection.

If no connection request comes in 60 seconds, the user is notified and redirected to the menu, and the daemon waits for their commands.

**Chat**: When a connection is established, the client program has two threads:
1. One thread takes inputs from the user and sends “MESSAGE” type messages with the payload to the daemon. If the user decides to terminate the connection, they type “q”, and the “DISCONNECTION_REQUEST” type message is sent to the daemon. The daemon sends a “FIN” control datagram to the recipient daemon, and the connection is terminated. The user is redirected to the menu, and the daemon waits for their commands.
2. The second thread listens for messages from the daemon and shows them to the user. “MESSAGE” type messages are printed with the sender’s username in front. “DISCONNECTION_REQUEST” type message indicates that the other member of the chat has disconnected. The client program notifies the user, redirects them to the main menu, and the daemon waits for client commands.

### Daemon to Daemon Communication

#### Three-Way Handshake
When the client of the daemon sends a “REQUEST” type message, the daemon starts a three-way handshake with the daemon whose IP was provided in the message by sending a “SYN” control datagram. Then it waits for another daemon to reply. After the client of the other daemon sends a “WAIT” request, the daemon receives that “SYN” and, if it is busy in another chat, replies with an “ERROR” message. Otherwise, it lets its client decide whether to accept or decline the chat request. If it receives an “ACCEPT” message from the client, it sends a “SYN+ACK” control datagram to the sender daemon. If it receives a “DECLINE” message, it sends a “FIN” control datagram. In case the connection is accepted, the sender sends a final “ACK”, and the chat starts.

#### Chat Using Stop-and-Wait Strategy
After establishing a connection, both daemons can send and receive chat messages. If one of the daemons sends a datagram “CHAT” with operation type “MESSAGE”, it waits 5 seconds for the “ACK” with the sequence number of the sent datagrams to come from the receiver. In case no “ACK” is received, the daemon retransmits the message with the next sequence number (0 or 1). If during the chat session the daemon receives a “FIN” datagram, it sends an “ACK” for that “FIN”, disconnects from the chat, and waits for client commands.

## Conclusion
During the implementation of the SIMP protocol, we learned how UDP works at a lower level. We also gained experience in designing and building protocols, handling datagrams, headers, and payloads. We understood the importance of reliability while implementing the three-way handshake and stop-and-wait strategy. The implemented protocol is very simple, which is why it cannot handle multiple users in a chat or multiple chats for a single user. It also lacks reliability (compared to TCP) and encryption.

