import socket
import sys
import threading
import time
from multiprocessing import Process
from enum import Enum
import atexit


USERNAME_LENGHT = 32
MAX_HEADER_SIZE = 33

client_name = None
client_addr = None

class MessageType(Enum):
    CHAT = 0
    CONNECTION = 1
    DISCONNECTION = 2 
    REQUEST = 3
    WAIT = 4
    DISCONNECT_REQUEST = 5
    ACCEPT = 6
    DECLINE = 7
    ERROR = 8 
    def to_bytes(self):
        if self == MessageType.CHAT:
            return int(0).to_bytes(1, byteorder='big')
        elif self == MessageType.CONNECTION:
            return int(1).to_bytes(1, byteorder='big')
        elif self == MessageType.DISCONNECTION:
            return int(2).to_bytes(1, byteorder='big')
        elif self == MessageType.REQUEST:
            return int(3).to_bytes(1, byteorder='big')
        elif self == MessageType.WAIT:
            return int(4).to_bytes(1, byteorder='big')
        elif self == MessageType.DISCONNECT_REQUEST:
            return int(5).to_bytes(1, byteorder='big')
        elif self == MessageType.ACCEPT:
            return int(6).to_bytes(1, byteorder='big')
        elif self == MessageType.DECLINE:
            return int(7).to_bytes(1, byteorder='big')
        else:
            return int(8).to_bytes(1,byteorder="big")


class Header:
    type:MessageType
    username:str
    def __init__(self):
        self.type = None
        self.username = None


def get_message_type(msg):
    indicator = msg[0]
    
    if indicator == 0:
        return MessageType.CHAT
    elif indicator == 1:
        return MessageType.CONNECTION
    elif indicator == 2:
        return MessageType.DISCONNECTION
    elif indicator == 3:
        return MessageType.REQUEST
    elif indicator == 4:
        return MessageType.WAIT
    elif indicator == 5:
        return MessageType.DISCONNECT_REQUEST
    elif indicator == 6:
        return MessageType.ACCEPT
    elif indicator == 7:
        return MessageType.DECLINE
    return MessageType.ERROR
    

def extract_username(message):
    try:
        username = message[1:USERNAME_LENGHT+1]
        return username.decode('ascii').rstrip('\x00')
    except:
        return False


def get_payload(msg):
    try:
        header = build_header(msg)
        if header.type == MessageType.CHAT: 
            payload = msg[USERNAME_LENGHT+2:].decode('ascii')
            return payload
        elif header.type == MessageType.ERROR:
            payload = msg[1:].decode('ascii')
            return payload
    except:
        return False


def build_header(msg):
    header = Header()

    header.type = get_message_type(msg)

    if header.type in (MessageType.CHAT,MessageType.REQUEST, MessageType.CONNECTION,MessageType.DECLINE) :
        
        header.username = extract_username(msg)
    elif header.type == MessageType.ACCEPT and len(msg) > 1:
        header.username = extract_username(msg)
    return header

       


def get_username():
    global username
    username = ""
    while len(username) == 0:    
        try:
            username = input('Enter your name or q to quit: ')
            if len(username) > USERNAME_LENGHT or len(username) == 0:
                username = ""
                print('username has to be between 1:32 characters long')
                continue
            elif username.lower() == "q":
                print("Quitting. Bye...")
                break
            
            return username.encode('ascii').ljust(USERNAME_LENGHT,b"\x00")
        except:
            print('Username username has to be between 1:32 latin characters long')
            username = ""
            continue


def connect(host) -> str:
    global server_socket
    
    username = get_username()
    msg_type = MessageType.CONNECTION.to_bytes()
    msg = b"".join([msg_type,username])
    print(f"requesting connection to {host}")
    tries = 3
    while tries > 0:
        try:
            server_socket.sendto(msg, (host, 7778))
            server_socket.settimeout(3)
            
            reply, _ = server_socket.recvfrom(1024)
            header = build_header(reply)

            if header.type == MessageType.CONNECTION:
                print("Connected to the daemon, entering the menu...")
                menu()
            elif header.type == MessageType.ERROR:
                print("Daemon is already occupied, try another one")
                sys.exit(0)
            else:
                print('Wrong daemon IP, try another one')
                sys.exit(0)
        except socket.timeout:
            tries -= 1
            continue
    else:
        print("No reply from daemon, try another one")


def wait_for_connection(host):
    global server_socket,t2
    try:
        print("For next 60 seconds will be opened for connections")
        server_socket.settimeout(60)
        msg_type=MessageType.WAIT.to_bytes()
        server_socket.sendto(msg_type,(host,7778))
        reply,addr = server_socket.recvfrom(1024)
        header = build_header(reply)
        if header.type == MessageType.REQUEST:
            username = header.username
            decision = ""
            print(f"Connection request from {username}")
            while decision not in ('y','yes','ye','n','no','nein'):
                decision = input("Accept Connection Y/N: ").lower()

                if decision == 'y' or decision == 'yes' or decision == 'ye':
                    msg_type = MessageType.ACCEPT.to_bytes()
                    server_socket.sendto(msg_type,addr)
                    print(f'Connection with {username} established')
                    
                    t2 = threading.Thread(target=receive_messages)
                    t2.start()
                    send_messages(host,header.username)
                elif decision in ('n','no','nein'):
                    msg_type= MessageType.DECLINE.to_bytes()
                    server_socket.sendto(msg_type,addr)
                    print('Conncection declined, going back to main menu')


    except socket.timeout:
        print("No requests came, going back to menu")
        menu()
            


def menu():
    
    while True:
        print("\nYou can:")
        print("1. Start a new chat")
        print("2. Wait for requests")
        print("q. Quit")
        option = input("\nChoose an option:").strip()

        if option == "1":
            request_chat(daemon_ip)
        elif option == "2":
            wait_for_connection(daemon_ip)

        elif option.lower() == "q":
            quit_daemon(daemon_ip)
            break
        else:
            print("Invalid option. Please try again.")
            continue




def request_chat(host) :
    global server_socket,t2
    while True:
        ip = input("Provide IP for chat request: ").encode()
        try:
            
            msg_type = MessageType.REQUEST.to_bytes()
            msg = b''.join([msg_type,ip])
            server_socket.sendto(msg,(host, 7778))
            server_socket.settimeout(60)
            print(f'Connection request to {ip.decode()} was send. Waiting for 60 seconds to reply')
            reply,_ = server_socket.recvfrom(1024)
            header = build_header(reply)
            if header.type == MessageType.ACCEPT:
                print(f'successfully connected to {header.username}')
                t2 = threading.Thread(target=receive_messages)
                t2.start()
                send_messages(host,header.username)
                break
            elif header.type == MessageType.DECLINE:
                print(f"Connection was not accepted by {header.username}")
                print("try again later")
                menu() 
            else: raise ValueError
        
        except socket.timeout:
            print(f"Timeout expired, no reply from {ip}, try again later")
            menu()




def send_messages(host,endhost_name) :
    global server_socket, username
    
    while True:
        try:
            #if client is the one who is going to send the message, he is the one if he was the one requesting the chat,but not waiting
        
            msg = input()
            
            if msg.lower() == "q":
                msg_type = MessageType.DISCONNECT_REQUEST.to_bytes()     
                server_socket.sendto(msg_type,(host,7778))
                print("Disconnect request sent...")
                menu()
                break
            msg = msg.encode('ascii')
                
            msg_type = MessageType.CHAT.to_bytes()
            msg = b''.join([msg_type,msg])
            server_socket.sendto(msg,(host,7778))
            
                
        except UnicodeEncodeError:
            print("only latin characters")
            continue


def receive_messages():
    global server_socket, username
    server_socket.settimeout(None)
    while True:
        try:
            msg,_ = server_socket.recvfrom(1024)
            header = build_header(msg)
            if header.type == MessageType.CHAT:
                print('\n')
                print(header.username,">",get_payload(msg))
                
                continue    
            elif header.type == MessageType.DISCONNECT_REQUEST:
                print("companion left the chat, returning to menu")
                print("type anything to be able to choose an option")
                
                menu()
                break
            elif header.type == MessageType.DISCONNECTION:
                print("received confirmation")
                menu()
                break
        except:
            print("Error on the server side occured, connection lost. Returning to menu")
            menu()
            break


    



def quit_daemon(host) -> None:
    global server_socket,daemon_ip
    msg_type = MessageType.DISCONNECTION.to_bytes()
    server_socket.sendto(msg_type,(host,7778))
    server_socket.settimeout(10)
    while True:
        try:
            msg, addr = server_socket.recvfrom(1024)
            header = build_header(msg)
            
            if header.type == MessageType.DISCONNECTION:
                print("Daemon notified.Disconnecting from daemon.")
                sys.exit(0)
            elif header.type == MessageType.ERROR:
                payload = get_payload(msg)
                print(f"Error occured: {payload},trying again")
                server_socket.sendto(msg_type,host)
                continue
                
        except socket.timeout:
            print("Timeout expired, forcibly clossing the connection with daemon.")
            sys.exit(0)




# atexit.register(quit_daemon(daemon_ip))




if __name__ == "__main__":
    import random
    global server_socket,daemon_ip
    
    if len(sys.argv) != 2:
        print("Usage: python client.py <daemon_ip>")
        sys.exit(1)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('127.0.0.'+str(random.randint(1,192)), 7778))
    daemon_ip = sys.argv[1]

    connect(daemon_ip)
