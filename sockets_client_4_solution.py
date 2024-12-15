#!/usr/bin/env python3

import socket
import sys
import string
import struct





def send(host, port, message_type, message) -> string:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        payload_size = 0
        if message_type == 1:
            payload_size = 4
        elif message_type == 2:
            payload_size = len(message)
        elif message_type == 3:
            payload_size = 8
        type_bytes = message_type.to_bytes(1, byteorder='big')
        payload_size_bytes = payload_size.to_bytes(4, byteorder='big')

        message_send = message.encode(encoding='ascii')
        if message_type == 1:
            message_send = int(message).to_bytes(4, byteorder='big')
        elif message_type == 3:
            message_send = struct.pack('>d', float(message))

        data_send = b''.join([type_bytes, payload_size_bytes, message_send])
        s.sendto(data_send, (host, port))
        reply = s.recv(1024)
        return repr(reply)


def show_usage():
    print('Usage parameters: <host> <port> <message_type> <message>')


if __name__ == "__main__":
    if len(sys.argv) != 5:
        show_usage()
        exit(1)

    data = send(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
    print('Received', data)
