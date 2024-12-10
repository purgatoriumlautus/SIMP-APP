import sys
import socket
from enum import Enum
import time
import threading
MAX_HEADER_SIZE = 39
MIN_HEADER_SIZE = 35
DATAGRAM_TYPE_SIZE = 1
OPERATION_TYPE_SIZE = 1
SEQUENCE = 1
MAX_USERNAME_SIZE = 32
LENGTH_FIELD_SIZE = 4
MAX_PAYLOAD_SIZE = 2048


#datagram type class used to identify the type of the message (\x00 -> control, \x01 -> chat)

class DatagramType(Enum):
    CONTROL = 0
    CHAT = 1
    UNKNOWN = 2
    
    def to_bytes(self):
        if self == DatagramType.CONTROL:
            return int(1).to_bytes(1, byteorder='big')
        elif self == DatagramType.CHAT:
            return int(2).to_bytes(1, byteorder='big')


#operation type class used to identify the operation of the control datagram type,
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
            return int(9).to_bytes(1,byteorder="big")
        

#error type used to identify errors found in datagrams
class ErrorType(Enum):
    WRONG_PAYLOAD_SIZE = 0 #payload_size field in header does not match the actual payload size
    UKNOWN_DATAGRAM_TYPE = 1 #datagramtype field is not in (\x010,\x01)
    UKNOWN_OPERATION_TYPE = 2 #operationtype is not in (\x01,\x02,\x04,x\08)
    USERNAME_ERROR = 3 #username could not be converted to a string or found in header
    LOST_DATAGRAM = 4 #datagram is lost
    MSG_TOO_LONG = 5 #message is too long
    MSG_TOO_SHORT = 6 #message is too short
    NO_PAYLOAD_EXPECTED = 7 #DATAGRAM TYPE = CONTROL AND OPERATION IS NOT ERROR -> NO PAYLOAD SHOULD BE TRANSMITTED
    WRONG_LENGTH_SIZE = 8 #LENGTH FIELD IN HEADER IS TOO BIG OR NOT AN INTEGER
    WRONG_SEQUENCE_NUMBER = 9 #SEQUENCE NUMBER IS NOT IN ("\x00,\x01")
    WRONG_PAYLOAD = 10 #payload couldn't be extracted


#HEADER class, used to create headers from messages, errors list will contain all the errors found in header, is_ok indicates if the header contains errors.
class HeaderInfo:
    is_ok = False
    type: DatagramType
    operation: OperationType
    seq = None
    payload_size = None
    username = None
    errors: list[ErrorType]
    

    def __init__(self):
        self.is_ok = False
        self.type = DatagramType.UNKNOWN
        self.operation = OperationType.UNKNOWN
        self.seq = None
        self.payload_size = None
        self.username = None
        self.errors = []



#fucntion to retrieve a datagram type from header
def get_datagram_type(msg):
    
    indicator = msg[0]
    if indicator == 1:
        return DatagramType.CONTROL
    elif indicator == 2:
        return DatagramType.CHAT
    return DatagramType.UNKNOWN

        
#function to get operation type from header
def get_operation_type(msg):
    
    dtype = get_datagram_type(msg)
    
    if dtype == DatagramType.CHAT:
        return OperationType.MESSAGE
    
    #if datagram type is not known than the operation type can't be related.
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


#get the sequence number from a message
def get_sequence_number(msg):
    #if the seq number is '\x01' -> lost datagram and needs to be retransmitted.
    seq = msg[2]
   
    
    if seq not in (0,1):
        return ErrorType.WRONG_SEQUENCE_NUMBER
    return seq

#function to encode any username to a 32 bytearray
def encode_username(username: str) -> bytes:
    # Convert to ASCII and ensure fixed size of 32 bytes
    encoded = username.encode('ascii')
    if len(encoded) > MAX_USERNAME_SIZE:
        return encoded[:MAX_USERNAME_SIZE]  # cut up to 32 bytes
    
    return encoded.ljust(MAX_USERNAME_SIZE, b'\x00')  #fill with null bytes the rest


#just for tests
client_name = encode_username("Arsen")




#function to retrieve the username from header,
def get_username(msg):
    
    try:
        username = msg[3:MAX_USERNAME_SIZE+4]
        return username.decode('ascii').rstrip('\x00') #cuts the additional zeros from right
    except:
        return ErrorType.USERNAME_ERROR
    

#function to get the payload length
def get_msg_length(msg):
    try:
        length = msg[36:39]
        length = int().from_bytes(length,byteorder='big')
        if length > MAX_PAYLOAD_SIZE: #NOW SET TO 2048 could be be greater or less.
            return ErrorType.WRONG_LENGTH_SIZE
        return length
    except:
        return ErrorType.WRONG_LENGTH_SIZE


#function to extract the payload from the message, since the 39 bytes are fixed for header, we can just take the rest of the bytes from the messages
def get_msg_payload(msg):
    try:
        payload = msg[MAX_HEADER_SIZE : ]
        return payload
    except:
        return ErrorType.WRONG_PAYLOAD
    


#fucntion which creates header class object, using other functions that extract all the header fields from message, if errors found -> added to header and then,
#when the reply is generated it checks whether the header was fine, if no -> control(error) datagram is generated with all the errors found in header.
def build_header(msg):
    
    header = HeaderInfo()
    if len(msg) < MIN_HEADER_SIZE: #HEADER CAN'T BE LESS THAN 35 BYTES [1 byte - datagram type, 1 byte - op.type, 1 byte - seq. number, 32bytes - username]
        header.errors.append(ErrorType.MSG_TOO_SHORT)
    
    #datagram type of the message
    dtype = get_datagram_type(msg)
    #if datagram type is now known append an error to the header object
    if dtype == DatagramType.UNKNOWN:
        header.errors.append(ErrorType.UKNOWN_DATAGRAM_TYPE)
    else:
        header.type = dtype
    
    #operation type of the message
    operation = get_operation_type(msg)
    #if operation type is not known -> append an error to the header object
    if operation == OperationType.UNKNOWN:
        header.errors.append(ErrorType.UKNOWN_OPERATION_TYPE)
    else:
        header.operation = operation
        
    #sequence number of the message 
    seq = get_sequence_number(msg)
    #if not in (0,1) -> append an error to a header
    if seq == ErrorType.WRONG_SEQUENCE_NUMBER:
        header.errors.append(ErrorType.WRONG_SEQUENCE_NUMBER)
    else:
        header.seq = seq
        
    #get the username of the message transmittor    
    username = get_username(msg)
    #if any problems with the username -> append an error to the header object
    if username == ErrorType.USERNAME_ERROR:
        header.errors.append(ErrorType.USERNAME_ERROR)
    else:
        header.username = username
        
    #get the payload size of the message
    payload_size = get_msg_length(msg)
    #if any error with the payload size -> append an error
    if payload_size == ErrorType.WRONG_LENGTH_SIZE:
        header.errors.append(ErrorType.WRONG_LENGTH_SIZE)
    else:
        header.payload_size=payload_size
    
    #get the payload of the message
    payload = get_msg_payload(msg)
    #if any problems with getting a payload -> append an error
    if payload == ErrorType.WRONG_PAYLOAD:
        header.errors.append(ErrorType.WRONG_PAYLOAD) 
    
    #if payload should be there, but it is -> append an error
    elif payload and header.type == DatagramType.CONTROL and header.operation != OperationType.MESSAGE:
        header.errors.append(ErrorType.NO_PAYLOAD_EXPECTED)
    
    #if payload size does not match the actual payload -> append an error
    else: 
        if len(payload) != payload_size:
            header.errors.append(ErrorType.WRONG_PAYLOAD_SIZE) 
        
    #if no errors found -> header is correct
    if len(header.errors) == 0:
        header.is_ok = True
    
    #debug statements
    print(f"Length of message: {len(msg)}")
    print(f"DatagramType: {header.type}")
    print(f"OperationType: {header.operation}")
    print(f"Sequence: {header.seq}")
    print(f"Username: {header.username}")
    print(f"Payload_size: {header.payload_size}")
    print(f"Errors: {header.errors}")
    print(f"Payload: {payload}")
    return header


#function to generate the error messages
def build_error_message(header):
    error_msg = ''
    #iterate through all the errors in header object. for different error types generate corresponding answer
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
        
        
#function to build a reply for the message
#it takes the message, extracts the header from it, if any errors found -> it will generate a reply containing the errors found in the header.
#if no errors are found -> just generate the message with acknowledgement
def build_reply(msg,host=None,port=None):
    header = build_header(msg)
    dtype = None
    operation = None
    
    #if errors in header, build error message and send
    if not header.is_ok:
        dtype = DatagramType.CONTROL.to_bytes()
        operation = OperationType.MESSAGE.to_bytes()
        error_msg = build_error_message(header).encode(encoding='ascii')
        seq = int(0).to_bytes(1,byteorder='big')
        username = client_name
        length   = len(error_msg).to_bytes(4,byteorder='big')
        reply = b''.join([dtype,operation,seq,username,length,error_msg])
    else:
        dtype = DatagramType.CONTROL.to_bytes()
        operation = OperationType.ACK.to_bytes()
        seq = int(0).to_bytes(1,byteorder='big')
        username = client_name
        reply = b''.join([dtype,operation,seq,username])
    return reply


def send_chat_message(client_address, message, seq):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        dtype = DatagramType.CHAT.to_bytes()
        operation = OperationType.MESSAGE.to_bytes()
        seq_byte = seq.to_bytes(1, byteorder='big')
        msg = message.encode()
        datagram = b''.join([dtype, operation, seq_byte, msg])
        retries = 3
        while retries > 0:
            try:
                print(f"Sending message to {client_address}: {message}")
                s.sendto(datagram, client_address)
                s.settimeout(5)
                response, _ = s.recvfrom(1024)
                ack_header = build_header(response)

                if ack_header.type == DatagramType.CONTROL and ack_header.operation == OperationType.ACK:
                    ack_seq = int.from_bytes(response[2:3], byteorder='big')
                    if ack_seq == seq:
                        print(f"ACK received for sequence {seq}")
                        return
                    else:
                        print(f"Unexpected ACK sequence: {ack_seq}")
                else:
                    print(f"Unexpected response: {response}")
            except socket.timeout:
                print("Timeout reached. Retransmitting message")
                retries -= 1
            except Exception as e:
                print(f"Error: {e}. Retransmitting message")
                retries -= 1

        print("Failed to send message")

def receive_chat_message(server_address):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(server_address)
        expected_seq = 0
        while True:
            data, sender_addr = s.recvfrom(1024)
            header = build_header(data)

            if header.type == DatagramType.CHAT and header.operation == OperationType.MESSAGE:
                seq = int.from_bytes(data[2:3], byteorder='big')
                message = data[3:].decode('utf-8')
                print(f"Received message from {sender_addr}: {message}")

                if seq == expected_seq:
                    dtype = DatagramType.CONTROL.to_bytes()
                    operation = OperationType.ACK.to_bytes()
                    seq_byte = seq.to_bytes(1, byteorder='big')
                    ack = b''.join([dtype, operation, seq_byte])
                    s.sendto(ack, sender_addr)
                    print(f"Acknowledgment sent for sequence {seq}.")
                    expected_seq = (expected_seq + 1) % 2

                else:
                    print(f"Unexpected sequence number: {seq}. Discarding message")

            elif header.type == DatagramType.CONTROL and header.operation == OperationType.FIN:
                print(f"FIN received from {sender_addr}. Sending ACK")
                dtype = DatagramType.CONTROL.to_bytes()
                operation = OperationType.ACK.to_bytes()
                seq_byte = data[2:3]
                ack = b''.join([dtype, operation, seq_byte])
                s.sendto(ack, sender_addr)
                print("Connection terminated.")
                break


def request_connection(host, port, client_name):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(5)
        dtype = DatagramType.CONTROL.to_bytes()
        operation = OperationType.SYN.to_bytes()
        seq = int(0).to_bytes(1, byteorder='big')
        username = client_name.encode()
        msg = b''.join([dtype, operation, seq, username])

        print(f"Sending SYN to {host}:{port}.")
        s.sendto(msg, (host, port))

        try:
            response, server_address = s.recvfrom(1024)
            print(f"Received response from {server_address}")

            header = build_header(response)
            if header.type == DatagramType.CONTROL and header.operation == (OperationType.SYN.value | OperationType.ACK.value):
                print("SYN+ACK received. Sending final ACK")
                dtype1 = DatagramType.CONTROL.to_bytes()
                operation1 = OperationType.ACK.to_bytes()
                ack_msg = b''.join([dtype1, operation1, seq, username])
                s.sendto(ack_msg, server_address)
                print("Connection established")
                return server_address
            elif header.type == DatagramType.CONTROL and header.operation == OperationType.FIN:
                print("FIN received. Connection declined")
            else:
                print("Unexpected response")
                # Respond with error message and FIN
                dtype1 = DatagramType.CONTROL.to_bytes()
                operation1 = OperationType.ERR.to_bytes()
                err_msg = "User already in another chat".encode()
                err_datagram = b''.join([dtype1, operation1, seq, err_msg, OperationType.FIN.to_bytes()])
                s.sendto(err_datagram, server_address)
        except socket.timeout:
            print("Connection timed out. No response from the server")


def accept_connection(host, port, client_name):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((host, port))
        print(f"Waiting for connection from {host}:{port}")
        response, server_address = s.recvfrom(1024)

        header = build_header(response)
        if header.type == DatagramType.CONTROL and header.operation == OperationType.SYN:
            print(f"SYN received from {server_address}. Sending SYN+ACK")
            dtype = DatagramType.CONTROL.to_bytes()
            operation = (OperationType.SYN.value | OperationType.ACK.value).to_bytes(1, byteorder='big')
            seq = int(0).to_bytes(1, byteorder='big')
            username = client_name.encode()
            msg = b''.join([dtype, operation, seq, username])
            print(msg)
            s.sendto(msg, server_address)

            final_ack, server_address = s.recvfrom(1024)
            ack_header = build_header(final_ack)

            if ack_header.type == DatagramType.CONTROL and ack_header.operation == OperationType.ACK:
                print("Final ACK received. Connection established")
                return (host,port)
            else:
                print("Unexpected response. Connection setup failed")
        else:
            print("Unexpected or invalid SYN message. Connection setup aborted.")


def decline_connection(host, port, client_name):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((host, port))
        response, server_address = s.recvfrom(1024)

        header = build_header(response)
        if header.type == DatagramType.CONTROL and header.operation == OperationType.SYN:
            print(f"SYN received from {server_address}. Sending FIN")
            dtype = DatagramType.CONTROL.to_bytes()
            operation = OperationType.FIN.to_bytes()
            seq = int(0).to_bytes(1, byteorder='big')
            username = client_name.encode()
            msg = b''.join([dtype, operation, seq, username])
            print(msg)
            s.sendto(msg, server_address)

            final_ack, _ = s.recvfrom(1024)
            ack_header = build_header(final_ack)

            if ack_header.type == DatagramType.CONTROL and ack_header.operation == OperationType.ACK:
                print("Final ACK received. Connection declined")
            else:
                print("Unexpected response. Connection setup failed")
        else:
            print("Unexpected or invalid SYN message. Connection setup aborted")

def wait_for_client(host: str):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((host, 7778))
        print("Daemon is waiting for client connections...")
        while True:
            data, client_addr = s.recvfrom(1024)
            data = data.decode('utf-8')
            print(f"Received data from {client_addr}: {data}")

            if data == 'q':
                response_message = f"Received termination request: {data}"
                s.sendto(response_message.encode("utf-8"), client_addr)
                continue

            if data.startswith("start"):
                host1 = data.split(":")[1]
                print(f"Starting connection handshake with {host1}")
                request_connection(host1, 7777, "Daemon")

            elif data.startswith("wait"):
                host1 = data.split(":")[1]
                print(f"Waiting for a connection request from {host1}")
                accept_connection(host1, 7777, "Daemon")

            response_message = f"Received: {data}"
            print(f"Sending response to {client_addr}: {response_message}")
            s.sendto(response_message.encode("utf-8"), client_addr)


#for demonstration
def start_server():
    host = '127.0.0.1'
    port = 7777
    client_name = "Server"

    client_address = accept_connection(host, port, client_name)
    if client_address:
        receive_chat_message(client_address)


def start_client():
    host = '127.0.0.1'
    port = 7777
    client_name = "Client1"
    server_address = request_connection(host, port, client_name)

    messages = ["Hello", "Bye"]
    if server_address:
       send_chat_message(server_address, messages[0], seq=0)
       send_chat_message(server_address, messages[1], seq=1)

if __name__ == "__main__":

    server_thread = threading.Thread(target=start_server, daemon=True)
    client_thread = threading.Thread(target=start_client, daemon=True)

    server_thread.start()
    client_thread.start()

    server_thread.join()
    client_thread.join()

    print("[Main] Testing completed.")

'''
if __name__ == "__main__":
    
    if len(sys.argv) != 2:
        print("Usage: python daemon.py <server_ip>")
        sys.exit(1)
    server_ip = sys.argv[1]
    wait_for_client(server_ip)
    '''


