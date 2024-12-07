#!/usr/bin/env python3

import socket
import sys
from enum import Enum

MAX_HEADER_SIZE = 5 # constant size (in bytes) of header
MESSAGE_TYPE_SIZE = 1
PAYLOAD_SIZE = 4
MAX_STRING_PAYLOAD_SIZE = 256
INT_PAYLOAD_SIZE = 4
FLOAT_PAYLOAD_SIZE = 8


class HeaderType(Enum):
    UNKNOWN = 0
    INT = 1,
    STRING = 2,
    FLOAT = 3,
    ERROR_CODE = 4

    def to_bytes(self):
        if self == HeaderType.UNKNOWN:
            return int(0).to_bytes(1, byteorder='big')
        elif self == HeaderType.INT:
            return int(1).to_bytes(1, byteorder='big')
        elif self == HeaderType.STRING:
            return int(2).to_bytes(1, byteorder='big')
        elif self == HeaderType.FLOAT:
            return int(3).to_bytes(1, byteorder='big')
        elif self == HeaderType.ERROR_CODE:
            return int(4).to_bytes(1, byteorder='big')



class ErrorCode(Enum):
    OK = 0,
    TYPE_MISMATCH = 1,
    MESSAGE_TOO_SHORT = 2
    MESSAGE_TOO_LONG = 3
    UNKNOWN_MESSAGE = 4
    WRONG_PAYLOAD = 5





class HeaderInfo:
    is_ok = False
    type: HeaderType
    code: ErrorCode

    def __init__(self):
        self.is_ok = False
        self.type = HeaderType.UNKNOWN
        self.code = ErrorCode.OK


def get_message_type(message: bytes) -> HeaderType:
    """
    Extracts the header type from the message
    :param message: The received message
    :return: The header type
    """
    type_byte = message[0]
    if type_byte == 1:
        return HeaderType.INT
    elif type_byte == 2:
        return HeaderType.STRING
    elif type_byte == 3:
        return HeaderType.FLOAT
    return HeaderType.UNKNOWN


def get_payload_size(message: bytes):
    """
    Returns the declared payload size from the message
    :param message: The received message
    :return: The payload size in bytes
    """
    payload_size = message[1:MAX_HEADER_SIZE]
    return int.from_bytes(payload_size, byteorder='big')


def check_header(message: bytes) -> HeaderInfo:
    """
    Checks if header is correctly built
    :param message: The message to check
    :return: True if header is ok, or False otherwise
    """
    header_info = HeaderInfo()
    if len(message) <= MAX_HEADER_SIZE:
        header_info.code = ErrorCode.MESSAGE_TOO_SHORT
        return header_info

    header_info.type = get_message_type(message)
    if header_info.type is HeaderType.UNKNOWN:
        header_info.code = ErrorCode.UNKNOWN_MESSAGE
        return header_info

    payload_size = get_payload_size(message)
    if header_info.type is HeaderType.INT:
        if payload_size != INT_PAYLOAD_SIZE:
            header_info.code = ErrorCode.TYPE_MISMATCH
            return header_info
    elif header_info.type is HeaderType.STRING:
        if payload_size == 0:
            header_info.code = ErrorCode.MESSAGE_TOO_SHORT
            return header_info
        elif payload_size > MAX_STRING_PAYLOAD_SIZE:
            header_info.code = ErrorCode.MESSAGE_TOO_LONG
            return header_info
    elif header_info.type is HeaderType.FLOAT:
        if payload_size != FLOAT_PAYLOAD_SIZE:
            header_info.code = ErrorCode.TYPE_MISMATCH
            return header_info

    payload = message[MAX_HEADER_SIZE:]
    if len(payload) != payload_size:
        header_info.code = ErrorCode.WRONG_PAYLOAD
        return header_info

    header_info.code = ErrorCode.OK
    header_info.is_ok = True
    return header_info


def build_reply(header_info: HeaderInfo) -> bytes:
    """
    Builds reply message
    :param header_info: The previously extracted header information
    :return: The reply object as a sequence of bytes
    """
    message_type = HeaderType.ERROR_CODE.to_bytes()
    error_message_str = "OK"
    if header_info.code is ErrorCode.TYPE_MISMATCH:
        error_message_str = "Type mismatch"
    elif header_info.code is ErrorCode.MESSAGE_TOO_SHORT:
        error_message_str = "Message too short"
    elif header_info.code is ErrorCode.WRONG_PAYLOAD:
        error_message_str = "Wrong payload"
    elif header_info.code is ErrorCode.UNKNOWN_MESSAGE:
        error_message_str = "Unknown type of message"
    elif header_info.code is ErrorCode.MESSAGE_TOO_LONG:
        error_message_str = "Message too long"

    error_message = error_message_str.encode(encoding='ascii')
    payload_size = len(error_message).to_bytes(4, byteorder='big')
    return b''.join([message_type, payload_size, error_message])


def wait_and_receive(host, port):
    print('Waiting for connections...')
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((host, port))
            while True:
                data, host_from = s.recvfrom(1024)
                print('Connected by ', host_from)
                if not data:
                    break
                header_info = check_header(data)
                data_send = build_reply(header_info)
                print('Sending back data: ', data_send)
                s.sendto(data_send, host_from)


def show_usage():
    print('Usage: simple_socket_server.py <host> <port>')


if __name__ == "__main__":
    if len(sys.argv) != 3:
        show_usage()
        exit(1)

    wait_and_receive(sys.argv[1], int(sys.argv[2]))