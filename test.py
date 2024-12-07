import sys
import socket
from enum import Enum

MAX_HEADER_SIZE = 39
MIN_HEADER_SIZE = 8# constant size (in bytes) of header
DATAGRAM_TYPE_SIZE = 1
OPERATION_TYPE_SIZE = 1
SEQUENCE = 1
MAX_USERNAME_SIZE = 32
LENGTH_FIELD_SIZE = 4



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
        
        
class ErrorType(Enum):
    WRONG_PAYLOAD_SIZE = 0
    UKNOWN_DATAGRAM_TYPE = 1
    UKNOWN_OPERATION_TYPE = 2
    USERNAME_ERROR = 3
    LOST_DATAGRAM = 4
    MSG_TOO_LONG = 5
    MSG_TOO_SHORT = 6
    NO_PAYLOAD_EXPECTED = 7
    WRONG_LENGTH_SIZE = 8
    WRONG_SEQUENCE_NUMBER = 9
    WRONG_PAYLOAD = 10


class HeaderInfo:
    is_ok = False
    type: DatagramType
    operation: OperationType
    seq = None
    payload_size = None
    username = None
    size = 0
    errors: list[ErrorType]
    

    def __init__(self):
        self.is_ok = False
        self.type = DatagramType.UNKNOWN
        self.operation = OperationType.UNKNOWN
        self.seq = None
        self.payload_size = None
        self.username = None
        self.size = 0
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
        return OperationType.MESSAGE
    
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
        else:
            return OperationType.UNKNOWN


def get_sequence_number(msg):
    
    seq = msg[2]
    if seq == 0:
        return seq
    elif seq == 1:
        return ErrorType.LOST_DATAGRAM
    else:
        return ErrorType.WRONG_SEQUENCE_NUMBER


def encode_username(username: str) -> bytes:
    # Convert to ASCII and ensure fixed size of 32 bytes
    encoded = username.encode('ascii')
    if len(encoded) > MAX_USERNAME_SIZE:
        return encoded[:MAX_USERNAME_SIZE]  # Truncate to 32 bytes
    return encoded.ljust(MAX_USERNAME_SIZE, b'\x00')  # Pad with null bytes







def get_username(msg):
    
    try:
        username = msg[3:MAX_USERNAME_SIZE+4]
        return username.decode('ascii').rstrip('\x00')
    except:
        return ErrorType.USERNAME_ERROR
    
    
def get_msg_length(msg):
    
    try:
        length = msg[36:39]
        return int().from_bytes(length,byteorder='big')
    except:
        return ErrorType.WRONG_LENGTH_SIZE


def get_msg_payload(msg, header: HeaderInfo):
    try:
        # Calculate where the payload starts
        payload_offset = MAX_HEADER_SIZE
       
        if header.type == DatagramType.CHAT and header.operation == OperationType.MESSAGE:
            # Extract payload based on calculated offset and payload size
            payload = msg[payload_offset: ]
            return payload
        elif header.type == DatagramType.CONTROL and header.operation == OperationType.MESSAGE:
            # Extract payload for CONTROL datagrams (similar logic)
            payload = msg[payload_offset: ]
            return payload
        else:
            return ErrorType.NO_PAYLOAD_EXPECTED
    except:
        return ErrorType.WRONG_PAYLOAD
    

def build_header(msg):
    payload = get_msg_payload(msg)
    print(payload)
    header = HeaderInfo()
    if len(msg) < MIN_HEADER_SIZE:
        header.errors.append(ErrorType.MSG_TOO_SHORT)
    
    dtype = get_datagram_type(msg)
    if dtype == DatagramType.UNKNOWN:
        header.errors.append(ErrorType.UKNOWN_DATAGRAM_TYPE)
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
    else:
        header.seq = seq
        
        
    username = get_username(msg)
    if username == ErrorType.USERNAME_ERROR:
        header.errors.append(ErrorType.USERNAME_ERROR)
    else:
        header.username = username
        
    payload_size = get_msg_length(msg)
    if payload_size == ErrorType.WRONG_LENGTH_SIZE:
        header.errors.append(ErrorType.WRONG_LENGTH_SIZE)
    else:
        header.payload_size=payload_size
    
    
    payload = get_msg_payload(msg)
    print(payload)
    if payload == ErrorType.WRONG_PAYLOAD:
        header.errors.append(ErrorType.WRONG_PAYLOAD) 
        
    elif payload == ErrorType.NO_PAYLOAD_EXPECTED:
        header.errors.append(ErrorType.NO_PAYLOAD_EXPECTED)
    else: 
        if len(payload) != payload_size:
            header.errors.append(ErrorType.WRONG_PAYLOAD_SIZE) 
        
    
    if len(header.errors) == 0:
        header.is_ok = True
    
    
    print(f"DatagramType: {header.type}")
    print(f"OperationType: {header.operation}")
    print(f"Sequence: {header.seq}")
    print(f"Username: {header.username}")
    print(f"Payload_size: {header.payload_size}")
    print(f"Errors: {header.errors}")
    print(f"Payload: {payload}")
    return header


def build_error_message(header):
    error_msg = ''
    for error in header.errors:
        if error == ErrorType.MSG_TOO_SHORT:
            error_msg += " ERROR: MESSAGE IS TOO SHORT\n"
        elif error == ErrorType.MSG_TOO_LONG:
            error_msg += " ERROR: MESSAGE IS TOO LONG\n"
        elif error == ErrorType.UKNOWN_DATAGRAM_TYPE:
            error_msg += " ERROR: UNKNOWN DATAGRAM TYPE IN HEADER (01 - CONTROL DATAGRAM, 02 - CHAT DATAGRAM)\n"
        elif error == ErrorType.UKNOWN_OPERATION_TYPE:
            error_msg += " ERROR: UNKNOWN OPERATION TYPE IN HEADER (01 - ERROR, 02 - SYN, 04 - ACK, 08 - FIN)\n"
        elif error == ErrorType.WRONG_SEQUENCE_NUMBER:
            error_msg += " ERROR: WRORG SEQUENCE NUMBER IN HEADER (00 - NO LOSS, 01 - LOST DATAGRAMS)\n"
        elif error == ErrorType.USERNAME_ERROR:
            error_msg += " ERROR: USERNAME ERROR IN HEADER (should be 1-32 bytes ascii decoded string)\n"
        elif error == ErrorType.WRONG_LENGTH_SIZE:
            error_msg == " ERROR: LENGTH HEADER FIELD SHOULD BE 4 BYTES LONG INDICATING PAYLOAD SIZE\n"
        elif error == ErrorType.NO_PAYLOAD_EXPECTED:
            error_msg += " ERROR: NO PAYLOAD EXPECTED\n"
        elif error == ErrorType.WRONG_PAYLOAD_SIZE:
            error_msg += " ERROR: PAYLOAD SIZE DOES NOT MATCH LENGTH FIELD\n"
        elif error == ErrorType.WRONG_PAYLOAD:
            error_msg += " ERROR: SOMETHING WRONG WITH MESSAGE\n"
            
    return error_msg
        
        

def build_reply(msg,host=None,port=None):
    header = build_header(msg)
    dtype = None
    operation = None
    
    if not header.is_ok:
        dtype = DatagramType.CONTROL.to_bytes()
        operation = OperationType.MESSAGE.to_bytes()
        error_msg = build_error_message(header).encode(encoding='ascii')
        seq = int(0).to_bytes(1,byteorder='big')
        username = "Admin".encode(encoding='ascii')
        length   = len(error_msg).to_bytes(4,byteorder='big')
        reply = b''.join([dtype,operation,seq,username,length,error_msg])
        # print(error_msg.decode('ascii'))
     
        
        
# build_reply(msg="\x01\x01\x03\x42\x12\x14\x04\x01\x06")


dtype = DatagramType.CONTROL.to_bytes()
operation = OperationType.ACK.to_bytes()
error_msg = "Test error"
seq = int(0).to_bytes(1,byteorder='big')
username = encode_username('Admin_replica')

error_msg_length = len(error_msg)

error_msg = "Test error".encode(encoding='ascii')
length = error_msg_length.to_bytes(4, byteorder='big')

final = b''.join([dtype, operation, seq, username])

build_header(final)
