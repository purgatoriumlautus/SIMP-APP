import sys
import socket
from enum import Enum
import time
import threading
from simp_client import build_header as build_client_header
from simp_client import MessageType

MAX_HEADER_SIZE = 39
MIN_HEADER_SIZE = 35
DATAGRAM_TYPE_SIZE = 1
OPERATION_TYPE_SIZE = 1
SEQUENCE = 1
MAX_USERNAME_SIZE = 32
LENGTH_FIELD_SIZE = 4
MAX_PAYLOAD_SIZE = 2048

clients = []
messages = []
pending_requests = []

# datagram type class used to identify the type of the message (\x00 -> control, \x01 -> chat)


class DatagramType(Enum):
    CONTROL = 0
    CHAT = 1
    UNKNOWN = 2

    def to_bytes(self):
        if self == DatagramType.CONTROL:
            return int(1).to_bytes(1, byteorder='big')
        elif self == DatagramType.CHAT:
            return int(2).to_bytes(1, byteorder='big')


# operation type class used to identify the operation of the control datagram type,
# when either control or chat datagrams need to transmit a message it takes operationtype = \x01 for both of them
class OperationType(Enum):
    MESSAGE = 1
    SYN = 2
    ACK = 4
    FIN = 8
    UNKNOWN = 9

    def to_bytes(self):
        if self == OperationType.MESSAGE:
            return int(1).to_bytes(1, byteorder='big')
        elif self == OperationType.SYN:
            return int(2).to_bytes(1, byteorder='big')
        elif self == OperationType.ACK:
            return int(4).to_bytes(1, byteorder='big')
        elif self == OperationType.FIN:
            return int(8).to_bytes(1, byteorder='big')
        else:
            return int(9).to_bytes(1, byteorder="big")


# error type used to identify errors found in datagrams
class ErrorType(Enum):
    WRONG_PAYLOAD_SIZE = 0  # payload_size field in header does not match the actual payload size
    UKNOWN_DATAGRAM_TYPE = 1  # datagramtype field is not in (\x010,\x01)
    UKNOWN_OPERATION_TYPE = 2  # operationtype is not in (\x01,\x02,\x04,x\08)
    USERNAME_ERROR = 3  # username could not be converted to a string or found in header
    LOST_DATAGRAM = 4  # datagram is lost
    MSG_TOO_LONG = 5  # message is too long
    MSG_TOO_SHORT = 6  # message is too short
    NO_PAYLOAD_EXPECTED = 7  # DATAGRAM TYPE = CONTROL AND OPERATION IS NOT ERROR -> NO PAYLOAD SHOULD BE TRANSMITTED
    WRONG_LENGTH_SIZE = 8  # LENGTH FIELD IN HEADER IS TOO BIG OR NOT AN INTEGER
    WRONG_SEQUENCE_NUMBER = 9  # SEQUENCE NUMBER IS NOT IN ("\x00,\x01")
    WRONG_PAYLOAD = 10  # payload couldn't be extracted


# HEADER class, used to create headers from messages, errors list will contain all the errors found in header, is_ok indicates if the header contains errors.
class HeaderInfo:
    is_ok = False
    type: DatagramType
    operation: OperationType
    seq = None
    payload_size = None
    username = None

    def __init__(self):
        self.is_ok = False
        self.type = DatagramType.UNKNOWN
        self.operation = OperationType.UNKNOWN
        self.seq = None
        self.payload_size = None
        self.username = None
        self.errors = []


# fucntion to retrieve a datagram type from header
def get_datagram_type(msg):
    indicator = msg[0]
    if indicator == 1:
        return DatagramType.CONTROL
    elif indicator == 2:
        return DatagramType.CHAT
    return DatagramType.UNKNOWN


# function to get operation type from header
def get_operation_type(msg):
    dtype = get_datagram_type(msg)

    if dtype == DatagramType.CHAT:
        return OperationType.MESSAGE

    # if datagram type is not known than the operation type can't be related.
    elif dtype == DatagramType.UNKNOWN:
        return OperationType.UNKNOWN

    else:
        op = msg[1]
        if op == 1:
            return OperationType.MESSAGE
        elif op == 2:
            return OperationType.SYN
        elif op == 4:
            return OperationType.ACK
        elif op == 8:
            return OperationType.FIN
        elif op == 6:
            return OperationType.SYN.value | OperationType.ACK.value
        else:
            return OperationType.UNKNOWN


# get the sequence number from a message
def get_sequence_number(msg):
    # if the seq number is '\x01' -> lost datagram and needs to be retransmitted.
    seq = msg[2]

    if seq not in (0, 1):
        return ErrorType.WRONG_SEQUENCE_NUMBER
    return seq


# function to encode any username to a 32 bytearray
def encode_username(username: str) -> bytes:
    # Convert to ASCII and ensure fixed size of 32 bytes
    encoded = username.encode('ascii')
    if len(encoded) > MAX_USERNAME_SIZE:
        return encoded[:MAX_USERNAME_SIZE]  # cut up to 32 bytes

    return encoded.ljust(MAX_USERNAME_SIZE, b'\x00')  # fill with null bytes the rest


# just for tests


# function to retrieve the username from header,
def get_username(msg):
    try:
        username = msg[3:MAX_USERNAME_SIZE + 4]
        return username.decode('ascii').rstrip('\x00')  # cuts the additional zeros from right
    except:
        return ErrorType.USERNAME_ERROR


# function to get the payload length
def get_msg_length(msg):
    try:
        length = msg[36:39]
        length = int().from_bytes(length, byteorder='big')
        if length > MAX_PAYLOAD_SIZE:  # NOW SET TO 2048 could be be greater or less.
            return ErrorType.WRONG_LENGTH_SIZE
        return length
    except:
        return ErrorType.WRONG_LENGTH_SIZE


# function to extract the payload from the message, since the 39 bytes are fixed for header, we can just take the rest of the bytes from the messages
def get_msg_payload(msg):
    try:
        payload = msg[MAX_HEADER_SIZE:]
        return payload
    except:
        return ErrorType.WRONG_PAYLOAD


# fucntion which creates header class object, using other functions that extract all the header fields from message, if errors found -> added to header and then,
# when the reply is generated it checks whether the header was fine, if no -> control(error) datagram is generated with all the errors found in header.
def build_header(msg):
    header = HeaderInfo()
    if len(msg) < MIN_HEADER_SIZE:  # HEADER CAN'T BE LESS THAN 35 BYTES [1 byte - datagram type, 1 byte - op.type, 1 byte - seq. number, 32bytes - username]
        header.errors.append(ErrorType.MSG_TOO_SHORT)

    # datagram type of the message
    dtype = get_datagram_type(msg)
    # if datagram type is now known append an error to the header object
    if dtype == DatagramType.UNKNOWN:
        header.errors.append(ErrorType.UKNOWN_DATAGRAM_TYPE)
    else:
        header.type = dtype

    # operation type of the message
    operation = get_operation_type(msg)
    # if operation type is not known -> append an error to the header object
    if operation == OperationType.UNKNOWN:
        header.errors.append(ErrorType.UKNOWN_OPERATION_TYPE)
    else:
        header.operation = operation

    # sequence number of the message
    seq = get_sequence_number(msg)
    # if not in (0,1) -> append an error to a header
    if seq == ErrorType.WRONG_SEQUENCE_NUMBER:
        header.errors.append(ErrorType.WRONG_SEQUENCE_NUMBER)
    else:
        header.seq = seq

    # get the username of the message transmittor
    username = get_username(msg)
    # if any problems with the username -> append an error to the header object
    if username == ErrorType.USERNAME_ERROR:
        header.errors.append(ErrorType.USERNAME_ERROR)
    else:
        header.username = username

    # get the payload size of the message
    payload_size = get_msg_length(msg)
    # if any error with the payload size -> append an error
    if payload_size == ErrorType.WRONG_LENGTH_SIZE:
        header.errors.append(ErrorType.WRONG_LENGTH_SIZE)
    else:
        header.payload_size = payload_size

    # get the payload of the message
    payload = get_msg_payload(msg)
    # if any problems with getting a payload -> append an error
    if payload == ErrorType.WRONG_PAYLOAD:
        header.errors.append(ErrorType.WRONG_PAYLOAD)

        # if payload should be there, but it is -> append an error
    elif payload and header.type == DatagramType.CONTROL and header.operation != OperationType.MESSAGE:
        header.errors.append(ErrorType.NO_PAYLOAD_EXPECTED)

    # if payload size does not match the actual payload -> append an error
    else:
        if len(payload) != payload_size:
            header.errors.append(ErrorType.WRONG_PAYLOAD_SIZE)

            # if no errors found -> header is correct
    if len(header.errors) == 0:
        header.is_ok = True

    # debug statements
    print(f"Length of message: {len(msg)}")
    print(f"DatagramType: {header.type}")
    print(f"OperationType: {header.operation}")
    print(f"Sequence: {header.seq}")
    print(f"Username: {header.username}")
    print(f"Payload_size: {header.payload_size}")
    print(f"Errors: {header.errors}")
    print(f"Payload: {payload}")
    return header


# function to generate the error messages
def build_error_message(header):
    error_msg = ''
    # iterate through all the errors in header object. for different error types generate corresponding answer
    for error in header.errors:
        if error == ErrorType.MSG_TOO_SHORT:
            error_msg += "ERROR: MESSAGE IS TOO SHORT\n"
        elif error == ErrorType.UKNOWN_DATAGRAM_TYPE:
            error_msg += "ERROR: UNKNOWN DATAGRAM TYPE IN HEADER (01 - CONTROL DATAGRAM, 02 - CHAT DATAGRAM)\n"
        elif error == ErrorType.UKNOWN_OPERATION_TYPE:
            error_msg += "ERROR: UNKNOWN OPERATION TYPE IN HEADER (01 - ERROR, 02 - SYN, 04 - ACK, 08 - FIN)\n"
        elif error == ErrorType.WRONG_SEQUENCE_NUMBER:
            error_msg += "ERROR: WRORG SEQUENCE NUMBER IN HEADER (00 - NO LOSS, 01 - LOST DATAGRAMS)\n"
        elif error == ErrorType.USERNAME_ERROR:
            error_msg += "ERROR: USERNAME ERROR IN HEADER (should be 1-32 bytes ascii decoded string)\n"
        elif error == ErrorType.WRONG_LENGTH_SIZE:
            error_msg == "ERROR: LENGTH HEADER FIELD SHOULD BE 4 BYTES LONG INDICATING PAYLOAD SIZE\n"
        elif error == ErrorType.NO_PAYLOAD_EXPECTED:
            error_msg += "ERROR: NO PAYLOAD EXPECTED\n"
        elif error == ErrorType.WRONG_PAYLOAD_SIZE:
            error_msg += "ERROR: PAYLOAD SIZE DOES NOT MATCH LENGTH FIELD\n"
        elif error == ErrorType.WRONG_PAYLOAD:
            error_msg += "ERROR: SOMETHING WRONG WITH MESSAGE\n"

    return error_msg


# function to build a reply for the message
# it takes the message, extracts the header from it, if any errors found -> it will generate a reply containing the errors found in the header.
# if no errors are found -> just generate the message with acknowledgement
def build_reply(msg, host=None, port=None):
    global clients
    client_name = clients[0][0]
    header = build_header(msg)
    dtype = None
    operation = None

    # if errors in header, build error message and send
    if not header.is_ok:
        dtype = DatagramType.CONTROL.to_bytes()
        operation = OperationType.MESSAGE.to_bytes()
        error_msg = build_error_message(header).encode(encoding='ascii')
        seq = int(0).to_bytes(1, byteorder='big')
        username = client_name
        length = len(error_msg).to_bytes(4, byteorder='big')
        reply = b''.join([dtype, operation, seq, username, length, error_msg])
    else:
        dtype = DatagramType.CONTROL.to_bytes()
        operation = OperationType.ACK.to_bytes()
        seq = int(0).to_bytes(1, byteorder='big')
        username = client_name
        reply = b''.join([dtype, operation, seq, username])
    return reply


#function to build a chat message
def build_chat_message(payload, seq):
    global clients
    dtype = DatagramType.CHAT.to_bytes()
    operation = OperationType.MESSAGE.to_bytes()
    seq_byte = seq.to_bytes(1, byteorder='big')
    username = encode_username(clients[0][0])
    msg = payload
    payload_size = len(msg).to_bytes(length=4, byteorder='big')
    datagram = b''.join([dtype, operation, seq_byte, username, payload_size, msg])
    return datagram


#function to build a fin message
def build_fin_message(seq):
    global clients
    dtype = DatagramType.CONTROL.to_bytes()
    operation = OperationType.FIN.to_bytes()
    seq_byte = seq.to_bytes(1, byteorder="big")
    username = encode_username(clients[0][0])
    datagram = b''.join([dtype, operation, seq_byte, username])
    return datagram

def build_ack_message(seq):
    dtype = DatagramType.CONTROL.to_bytes()
    operation = OperationType.ACK.to_bytes()
    seq_byte = seq.to_bytes(1, byteorder='big')
    username = encode_username(clients[0][0])
    datagram = b''.join([dtype, operation, seq_byte, username])
    return datagram

#function that handles reciving of chat messages from another daemon
def receive_chat_message():
    global clients, daemon_socket, client_socket, messages, t1, t2
    client_name = clients[0][0]
    while True:
        daemon_socket.settimeout(None)
        msg, sender_addr = daemon_socket.recvfrom(1024)
        header = build_header(msg)
        #if the datagram type is CHAT and operation type is MESSAGE, sends the message to the client
        if header.type == DatagramType.CHAT and header.operation == OperationType.MESSAGE:
            message = get_msg_payload(msg)
            print(f"{server_name}: Received message from {sender_addr}: {message.decode('ascii')}")
            msg_type = MessageType.CHAT.to_bytes()
            usrname = encode_username(header.username)
            msg = b''.join([msg_type, usrname, message])
            client_socket.sendto(msg, clients[0][1])
        #if the datagram type is CONTROL and operation type is FIN, sends DISCONNECT_REQUEST to the client
        # and stops receiving messages
        elif header.type == DatagramType.CONTROL and header.operation == OperationType.FIN:
            print('received FIN request, closing the connection')
            clients.pop(1)
            msg_type = MessageType.DISCONNECT_REQUEST.to_bytes()
            username = encode_username(header.username)
            client_socket.sendto(msg_type, clients[0][1])
            client_commands()
            break


#function that handles sending of chat messages
def send_chat_message(message='', type=True):
    global clients, daemon_socket, client_socket, messages
    #if the message is not a fin message it builds a chat message, if a fin builds a fin message
    #if there is more than one client sends a message

    if len(clients) > 1:
        if type:
            message = build_chat_message(message, seq=0)
            daemon_socket.sendto(message, clients[1][1])
            print(f"sending message to {clients[1][1]} {message}")
        else:
            message = build_fin_message(0)
            daemon_socket.sendto(message, clients[1][1])
            print(f"sending message to {clients[1][1]} {message}")
            return False
    else:
        print("cant reach, discarding")
        return False


#function to request connection to another daemon using tree-way handshake
def request_connection(host, port):
    global clients, daemon_socket, client_socket, t1, t2
    client_name = clients[0][0]
    client_addr = clients[0][1]

    daemon_socket.settimeout(30)
    dtype = DatagramType.CONTROL.to_bytes()
    operation = OperationType.SYN.to_bytes()
    seq = int(0).to_bytes(1, byteorder='big')
    username = encode_username(client_name)
    msg = b''.join([dtype, operation, seq, username])
    #Sends SYN
    print(f"{server_name}: Sending SYN to {host}:{port}.")
    daemon_socket.sendto(msg, (host, port))

    response, server_address = daemon_socket.recvfrom(1024)
    print(f"{server_name}: Received response from {server_address}")
    header = build_header(response)
    #checks if datagram type is CONTROL and operation type is a combination of SYN + ACK
    if header.type == DatagramType.CONTROL and header.operation == (OperationType.SYN.value | OperationType.ACK.value):

        print(f"{server_name}: SYN+ACK received. Sending final ACK")
        dtype1 = DatagramType.CONTROL.to_bytes()
        operation1 = OperationType.ACK.to_bytes()
        ack_msg = b''.join([dtype1, operation1, seq, username])
        #Sends ACK
        daemon_socket.sendto(ack_msg, (host, port))

        msg_type = MessageType.ACCEPT.to_bytes()
        username = encode_username(header.username)
        client_socket.sendto(b''.join([msg_type, username]), client_addr)
        clients.append((header.username, server_address))
        #Start receiving chat messages from another daemon
        print(f"{server_name}: Connection established")
        t1 = threading.Thread(target=receive_chat_message, daemon=True)
        t1.start()
        #Start chat with client
        t2 = threading.Thread(target=chat_with_client(False))
        t2.start()
        return True
    #if received operation type is FIN connection is declined
    elif header.type == DatagramType.CONTROL and header.operation == OperationType.FIN:
        msg_type = MessageType.DECLINE.to_bytes()
        username = encode_username(header.username)
        client_socket.sendto(b''.join([msg_type, username]), client_addr)
        print(f"{server_name}: FIN received. Connection declined")
        return False
    else:
        #if message type is DECLINE wait for client commands
        msg_type = MessageType.DECLINE.to_bytes()

        client_socket.sendto(msg_type, client_addr)
        print(f"{server_name}: FIN received. Connection declined")
        client_commands()


#function to check pending requests
def check_pending():
    global clients, client_socket, daemon_socket, t1, t2

    print(f"{server_name}: Check for pending requests")
    daemon_socket.settimeout(5)
    try:
        response, server_address = daemon_socket.recvfrom(1024)
        header = build_header(response)
        print(header.username)
        #if there is a request append pending_requests
        if header.type == DatagramType.CONTROL and header.operation == OperationType.SYN and len(clients) != 2:
            pending_requests.append((header, server_address))
    except socket.timeout:
        print("No requests came, going back to client commands")


#function to handle pending requests
def handle_pending(header, server_address):
    global clients, client_socket, daemon_socket, t1, t2
    client_name = clients[0][0]
    client_addr = clients[0][1]
    msg_type = MessageType.REQUEST.to_bytes()

    username_end = encode_username(header.username)
    orig_endname = header.username
    msg = b''.join([msg_type, username_end])

    client_socket.sendto(msg, client_addr)
    daemon_socket.settimeout(60)
    user_respond, _ = client_socket.recvfrom(1024)
    print(f'{server_name}: received decision,{user_respond}')

    header = build_client_header(user_respond)
    print(header.type)
    #if the message type is ACCEPT, sends SYN + ACK
    if header.type == MessageType.ACCEPT:
        dtype = DatagramType.CONTROL.to_bytes()
        operation = (OperationType.SYN.value | OperationType.ACK.value).to_bytes(1, byteorder='big')
        seq = int(0).to_bytes(1, byteorder='big')
        username = encode_username(client_name)
        msg = b''.join([dtype, operation, seq, username])
        daemon_socket.sendto(msg, server_address)

        final_ack, server_address = daemon_socket.recvfrom(1024)
        ack_header = build_header(final_ack)
        #if the ACK is received start receiving chat messages from another daemon and start chat with client
        if ack_header.type == DatagramType.CONTROL and ack_header.operation == OperationType.ACK:
            print(f"{server_name}: Final ACK received. Connection established")
            clients.append((orig_endname, server_address))
            t1 = threading.Thread(target=receive_chat_message, daemon=True)
            t1.start()
            t2 = threading.Thread(target=chat_with_client(True))
            t2.start()
        #if ACK is not received waits for client commands and send error messages
        else:
            print(f"{server_name}: Unexpected response. Connection setup failed")
            msg_type = MessageType.ERROR.to_bytes()
            client_socket.sendto(msg_type, client_addr)
            client_commands()
   #if message type is DECLINE, sends FIN and waits for client commands
    elif header.type == MessageType.DECLINE:
        dtype = DatagramType.CONTROL.to_bytes()
        op = OperationType.FIN.to_bytes()
        seq = int(0).to_bytes(1, byteorder='big')
        username = encode_username(client_name)
        msg = b''.join([dtype, op, seq, username])
        daemon_socket.sendto(msg, server_address)
        client_commands()


#function to wait for the connections
def wait_for_connection():
    global clients, client_socket, daemon_socket, t1, t2
    client_name = clients[0][0]
    client_addr = clients[0][1]

    print(f"{server_name}: Waiting for connections for 60 seconds")
    #set timout to 1 minute
    daemon_socket.settimeout(60)
    response, server_address = daemon_socket.recvfrom(1024)
    header = build_header(response)
    try:
        #if the response is received and operation type is SYN sends REQUEST and waits for decision
        if header.type == DatagramType.CONTROL and header.operation == OperationType.SYN and len(clients) != 2:
            print(f"{server_name}: SYN received from {server_address}. Need client's decision.")
            msg_type = MessageType.REQUEST.to_bytes()

            username_end = encode_username(header.username)
            orig_endname = header.username
            msg = b''.join([msg_type, username_end])

            client_socket.sendto(msg, client_addr)
            daemon_socket.settimeout(60)
            user_respond, _ = client_socket.recvfrom(1024)
            print(f'{server_name}: received decision,{user_respond}')

            header = build_client_header(user_respond)
            print(header.type)
            # if the message type is ACCEPT, sends SYN + ACK
            if header.type == MessageType.ACCEPT:
                dtype = DatagramType.CONTROL.to_bytes()
                operation = (OperationType.SYN.value | OperationType.ACK.value).to_bytes(1, byteorder='big')
                seq = int(0).to_bytes(1, byteorder='big')
                username = encode_username(client_name)
                msg = b''.join([dtype, operation, seq, username])
                daemon_socket.sendto(msg, server_address)
                final_ack, server_address = daemon_socket.recvfrom(1024)
                ack_header = build_header(final_ack)
                # if the ACK is received start receiving chat messages from another daemon and start chat with client
                if ack_header.type == DatagramType.CONTROL and ack_header.operation == OperationType.ACK:
                    print(f"{server_name}: Final ACK received. Connection established")
                    clients.append((orig_endname, server_address))
                    t1 = threading.Thread(target=receive_chat_message, daemon=True)
                    t1.start()
                    t2 = threading.Thread(target=chat_with_client(True))
                    t2.start()
                # if ACK is not received waits for client commands and send error messages
                else:
                    print(f"{server_name}: Unexpected response. Connection setup failed")
                    msg_type = MessageType.ERROR.to_bytes()
                    client_socket.sendto(msg_type, client_addr)
                    client_commands()
            # if message type is DECLINE, sends FIN and waits for client commands
            elif header.type == MessageType.DECLINE:
                dtype = DatagramType.CONTROL.to_bytes()
                op = OperationType.FIN.to_bytes()
                seq = int(0).to_bytes(1, byteorder='big')
                username = encode_username(client_name)
                msg = b''.join([dtype, op, seq, username])
                daemon_socket.sendto(msg, server_address)
                client_commands()
        else:
            #if response is not SYN send error message
            print(f"{server_name}: Unexpected or invalid SYN message. Connection setup aborted.")
            msg_type = MessageType.ERROR.to_bytes()
            client_socket.sendto(msg_type, client_addr)
            client_commands()
    except socket.timeout:
        print("No requests came, going back to client commands")
        client_commands()


#function to decline connection
def decline_connection():
    global clients, daemon_socket, client_socket
    client_name = clients[0][0]

    response, server_address = daemon_socket.recvfrom(1024)
    header = build_header(response)
    # if the response is received and operation type is SYN sends FIN
    if header.type == DatagramType.CONTROL and header.operation == OperationType.SYN:
        print(f"{server_name}: SYN received from {server_address}. Sending FIN")
        dtype = DatagramType.CONTROL.to_bytes()
        operation = OperationType.FIN.to_bytes()
        seq = int(0).to_bytes(1, byteorder='big')
        username = client_name
        msg = b''.join([dtype, operation, seq, username])
        print(msg)
        daemon_socket.sendto(msg, server_address)

        final_ack, _ = daemon_socket.recvfrom(1024)
        ack_header = build_header(final_ack)
        #receive final ACK
        if ack_header.type == DatagramType.CONTROL and ack_header.operation == OperationType.ACK:
            print(f"{server_name}: Final ACK received. Connection declined")
        else:
            print(f"{server_name}: Unexpected response. Connection setup failed")
    else:
        print(f"{server_name}: Unexpected or invalid SYN message. Connection setup aborted")


#function for daemon client communication
def wait_for_client():
    global clients, client_socket
    print(f"{server_name}: Daemon is waiting for client connections...")
    while True:
        msg, addr = client_socket.recvfrom(1024)
        header = build_client_header(msg)
        if len(clients) == 0:
            #if message type is CONNECTION, check for pending requests
            if header.type == MessageType.CONNECTION:

                username = msg[1:].decode('ascii').rstrip('\x00')
                clients.append((username, addr))

                check_pending()
                #if there is no pending requests wait for client commands
                if len(pending_requests) == 0:
                    msg_type = MessageType.CONNECTION.to_bytes()
                    client_socket.sendto(msg_type, addr)
                    print(f"Established connection with client: {clients[0][0]} address {addr}")
                    client_commands()
                #if there are pending requests ask client if he wants to accept or decline first request
                else:
                    msg_type = MessageType.WAIT.to_bytes()
                    client_socket.sendto(msg_type, addr)
                    print(f"Established connection with client: {clients[0][0]} address {addr}")
                    print(pending_requests)
                    handle_pending(pending_requests[0][0],pending_requests[0][1])
        #if there is already client connected, reject connection
        else:
            print(f"THE DAEMON IS ALREADY OCCUPIED BY {clients[0][0]} {addr}, rejecting the conncetion")
            msg_type = MessageType.ERROR.to_bytes()
            payload = "This daemon is already occupied".encode('ascii')
            client_socket.sendto(b''.join([msg_type, payload]), addr)


#function to handle client command
def client_commands():
    global clients, client_socket, server_name

    client_name = clients[0][0]
    client_addr = clients[0][1]
    while True:
        print(f"{server_name}: Daemon is waiting for client commands...")
        msg, addr = client_socket.recvfrom(1024)
        header = build_client_header(msg)
        #if the client send DISCONNECTION message, daemon returns to wait for client state
        if header.type == MessageType.DISCONNECTION:
            msg_type = MessageType.DISCONNECTION.to_bytes()
            print(f"{server_name}: Received termination request from {client_name}")
            client_socket.sendto(msg_type, client_addr)
            del clients[0]
            wait_for_client()
        #if the client sends REQUEST for chat, daemon requests connection with provided ip address
        if header.type == MessageType.REQUEST:
            ip = msg[1:].decode()
            print(f"{server_name}: Starting connection handshake with {ip}")
            request_connection(ip, 7777)
        #if the client sends WAIT message, daemon starts waiting for the connections
        elif header.type == MessageType.WAIT:
            print(f'{server_name}: Received wait request from client')
            wait_for_connection()


#this function needed to communicate between client and daemon, and then use send_chat_message and receive_chat_message to communicate between daemons
def chat_with_client(flag=True):
    global clients, client_socket, server_name, daemon_socket, messages, t1, t2
    client_name = clients[0][0]
    client_addr = clients[0][1]
    print('started receiving messages from client')
    #recieves messages from the client and sends messages to another daemon
    while True:

        msg, _ = client_socket.recvfrom(1024)
        header = build_client_header(msg)
        if header.type == MessageType.CHAT:
            print('received message from client', msg[1:])
            send_chat_message(msg, type=True)
        #if daemon receives DISCONNECT_REQUEST from the client sends disconnect message to another daemon and stops receiving messages from the client
        elif header.type == MessageType.DISCONNECT_REQUEST:
            print("received disconnection request from client")
            send_chat_message(type=False)
            t1.join()
            t2.join()
            print('notified another daemon, notyfying the client')
            client_commands()
            break


#function that starts the server and calls function to wait for the client
def start_server(address):
    global server_name, daemon_socket, client_socket
    server_name = "Server" + str(time.time())[-1]
    daemon_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    daemon_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    daemon_socket.bind((address, 7777))
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_socket.bind((address, 7778))
    wait_for_client()


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("Usage: python daemon.py <server_ip>")
        sys.exit(1)

    server_thread = threading.Thread(target=start_server, args=(sys.argv[1],))

    server_thread.start()
