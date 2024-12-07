import sys
import socket
from enum import Enum

MAX_HEADER_SIZE = 39
MIN_HEADER_SIZE = 8# constant size (in bytes) of header
DATAGRAM_TYPE_SIZE = 1
OPERATION_TYPE_SIZE = 1
SEQUENCE = 1
MAX_USERNAME_SIZE = 32
LENGHT_FIELD_SIZE = 4



class DatagramType(Enum):
    CONTROL = 0
    CHAT = 1
    UNKNOWN = 2
    
    def to_bytes(self):
        if self == DatagramType.CONTROL:
            return int(1).to_bytes(1, byteorder='big')
        elif self == DatagramType.CHAT:
            return int(2).to_bytes(1, byteorder='big')


class OperationType(Enum):
    ERROR = 1
    SYN = 2
    ACK = 4
    FIN = 8
    UNKNOWN = 9
    
    def to_bytes(self):
        if self == OperationType.ERROR:
            return int(1).to_bytes(1, byteorder='big')
        elif self == OperationType.SYN:
            return int(2).to_bytes(1, byteorder='big')
        elif self == OperationType.ACK:
            return int(4).to_bytes(1, byteorder='big')
        elif self == OperationType.FIN:
            return int(8).to_bytes(1, byteorder='big')
        else:
            return int(9).to_bytes(1,byteorder="big")
        
        
class ErrorType(Enum):
    WRONG_PAYLOAD_SIZE = 0
    UKNOWN_DATAGRAM_TYPE = 1
    UKNOWN_OPERATION_TYPE = 2
    USERNAME_ERROR = 3
    LOST_DATAGRAM = 4
    MSG_TOO_LONG = 5
    MSG_TOO_SHORT = 6
    NO_PAYLOAD_EXPECTED = 7
    WRONG_LENGHT_SIZE = 8
    WRONG_SEQUENCE_NUMBER = 9


class HeaderInfo:
    is_ok = False
    type: DatagramType
    operation: OperationType
    errors: list[ErrorType]

    def __init__(self):
        self.is_ok = False
        self.type = DatagramType.UNKNOWN
        self.operation = OperationType.UNKNOWN
        self.errors = []



def get_datagram_type(msg):
    
    indicator = msg[0]
    
    if indicator == 1:
        return DatagramType.CONTROL
    elif indicator == 2:
        return DatagramType.CHAT
    return DatagramType.UNKNOWN

        

def get_operation_type(msg):
    
    dtype = get_datagram_type(msg)
    
    if dtype == DatagramType.CHAT:
        return int(1).to_bytes(1,byteorder='big')
    
    elif dtype == DatagramType.UNKNOWN:
        return OperationType.UNKNOWN
    
    else:
        op = msg[1]
        if op == 1:
            return OperationType.ERROR
        elif op == 2:
            return OperationType.SYN
        elif op == 4:
            return OperationType.ACK
        elif op == 8:
            return OperationType.FIN
        else:
            return OperationType.UNKNOWN


def get_sequence_number(msg):
    
    seq = msg[2]
    
    if seq == 0:
        return ErrorType.OK
    elif seq == 1:
        return ErrorType.LOST_DATAGRAM
    else:
        return ErrorType.WRONG_SEQUENCE_NUMBER

def get_username(msg):
    
    try:
        username = msg[3:MAX_USERNAME_SIZE+4].decode('ascii')
        return username
    except:
        return ErrorType.USERNAME_ERROR
    
    
def get_msg_lenght(msg):
    try:
        lenght = msg[36:MAX_HEADER_SIZE+1]
        return int().from_bytes(lenght,byteorder='big')
    except:
        return ErrorType.WRONG_LENGHT_SIZE


def get_msg_payload(msg):
    
    dtype = get_datagram_type(msg)
    operation = get_operation_type(msg)

    if dtype == 1 and operation == 1:
        payload = msg[MAX_HEADER_SIZE+1:]
        return payload
    elif dtype == 2 and operation == 1:
        payload = msg[MAX_HEADER_SIZE+1:]
        return payload
    else:
        return ErrorType.NO_PAYLOAD_EXPECTED

    
def check_header(msg):
    
    header = HeaderInfo()
    if len(msg) < MIN_HEADER_SIZE:
        header.errors.append(ErrorType.MSG_TOO_SHORT)
    
    dtype = get_datagram_type(msg)
    if dtype == DatagramType.UNKNOWN:
        header.erors.append(ErrorType.UKNOWN_DATAGRAM_TYPE)
    else:
        header.type = dtype
        
    operation = get_operation_type(msg)
    if operation == OperationType.UNKNOWN:
        header.errors.append(ErrorType.UKNOWN_OPERATION_TYPE)
    else:
        header.operation = operation
        
    seq = get_sequence_number(msg)
    if seq == ErrorType.WRONG_SEQUENCE_NUMBER:
        header.errors.append(ErrorType.WRONG_SEQUENCE_NUMBER)
        
    username = get_username(msg)
    if username == ErrorType.USERNAME_ERROR:
        header.errors.append(ErrorType.USERNAME_ERROR)
    
    payload_size = get_msg_lenght(msg)
    if payload_size == ErrorType.WRONG_LENGHT_SIZE:
        header.errors.append(ErrorType.WRONG_LENGHT_SIZE)
    
    payload = get_msg_payload(msg)
    if len(payload) != payload_size:
        header.errors.append(ErrorType.WRONG_PAYLOAD_SIZE) 
    elif payload == ErrorType.NO_PAYLOAD_EXPECTED:
        header.errors.append(ErrorType.NO_PAYLOAD_EXPECTED)
    
    if len(header.errors) == 0:
        header.is_ok = True
    
    return header



        

    
    
        
    
    
    

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
            
            response_message = f"Received: {data}"
            print(f"Sending response to {client_addr}: {response_message}")
            s.sendto(response_message.encode("utf-8"), client_addr)




if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python daemon.py <server_ip>")
        sys.exit(1)

    server_ip = sys.argv[1]
    wait_for_client(server_ip)