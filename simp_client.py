import socket
import sys
import threading
import time
from enum import Enum


USERNAME_LENGHT = 32
MAX_HEADER_SIZE = 33
client_name = None
client_addr = None
in_chat = False


#class to identify message types
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


#header class
class Header:
    type: MessageType
    username: str
    def __init__(self):
        self.type = None
        self.username = None


#function to identify message type
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

    
#function to extract the username
def extract_username(message):
    try:
        username = message[1:USERNAME_LENGHT+1]
        return username.decode('ascii').rstrip('\x00')
    except:
        return False


#function to get payload from header
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


#function that build a header
def build_header(msg):
    header = Header()

    header.type = get_message_type(msg)

    if header.type in (MessageType.CHAT,MessageType.REQUEST, MessageType.CONNECTION,MessageType.DECLINE) :
        
        header.username = extract_username(msg)
    elif header.type == MessageType.ACCEPT and len(msg) > 1:
        header.username = extract_username(msg)
    return header


#function to get username from input field
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
                sys.exit(0)
                break
            return username.encode('ascii').ljust(USERNAME_LENGHT,b"\x00")
        except Exception as e:
            print('Username username has to be between 1:32 latin characters long', e)
            username = ""
            continue


#function that builds connection with a daemon
def connect(host) -> str:
    global server_socket
    server_socket.settimeout(60)
    username = get_username()
    msg_type = MessageType.CONNECTION.to_bytes()
    msg = b"".join([msg_type,username])
    print(f"requesting connection to {host}")

    try:
        server_socket.sendto(msg, (host, 7778))
        # server_socket.settimeout(3)

        reply, _ = server_socket.recvfrom(1024)
        header = build_header(reply)
        #if message type is CONNECTION, proceed to menu
        if header.type == MessageType.CONNECTION:
            print("Connected to the daemon, entering the menu...")
            menu()
        #if message type is WAIT,decide on accepting or declining connection
        elif header.type == MessageType.WAIT:
            print("Connected to the daemon")
            pending(host)
            menu()
        #if message type is ERROR then the daemon is already occupied
        elif header.type == MessageType.ERROR:
            print("Daemon is already occupied, try another one")
            sys.exit(0)
        else:
            print('Wrong daemon IP, try another one')
            sys.exit(0)
    except socket.timeout:
        print('no reply from daemon,try another one')
        sys.exit(0)
   

#functon that handles decision to accept or decline connection
def pending(host):
    global server_socket, t2,in_chat
    try:
        print("For next 60 seconds will be opened for connections")
        server_socket.settimeout(60)
        reply, addr = server_socket.recvfrom(1024)
        header = build_header(reply)
        #if message type is REQUEST, make desicion and send to the daemon
        if header.type == MessageType.REQUEST:
            username = header.username
            decision = ""
            print(f"Connection request from {username}")
            while decision not in ('y', 'yes', 'ye', 'n', 'no', 'nein'):
                decision = input("Accept Connection Y/N: ").lower()
                #if the decision is yes send ACCEPT message
                if decision == 'y' or decision == 'yes' or decision == 'ye':
                    msg_type = MessageType.ACCEPT.to_bytes()
                    server_socket.sendto(msg_type, addr)
                    print(f'Connection with {username} established')
                    in_chat = True
                    t2 = threading.Thread(target=receive_messages)
                    t2.start()
                    
                    send_messages(host)
                    
                    return
                # if the decision is no send DECLINE message
                elif decision in ('n', 'no', 'nein'):
                    msg_type = MessageType.DECLINE.to_bytes()
                    server_socket.sendto(msg_type, addr)
                    print('Conncection declined, going back to main menu')
                    return
                
    except socket.timeout:
        print("No requests came, going back to menu")
        return
    
    except ConnectionResetError:
        print("Lost connection with daemon. Please restart an app")
        sys.exit(0)


#function that waits for the connection
def wait_for_connection(host):
    global server_socket, t2, in_chat
    try:
        print("For next 60 seconds will be opened for connections")
        server_socket.settimeout(60)
        #send WAIT message to daemon
        msg_type=MessageType.WAIT.to_bytes()
        server_socket.sendto(msg_type,(host,7778))
        reply,addr = server_socket.recvfrom(1024)
        header = build_header(reply)

        # if message type is REQUEST, make desicion and send to the daemon
        if header.type == MessageType.REQUEST:
            username = header.username
            decision = ""
            print(f"Connection request from {username}")
            while decision not in ('y','yes','ye','n','no','nein'):
                decision = input("Accept Connection Y/N: ").lower()
                # if the decision is yes send ACCEPT message
                if decision == 'y' or decision == 'yes' or decision == 'ye':
                    msg_type = MessageType.ACCEPT.to_bytes()
                    server_socket.sendto(msg_type,addr)
                    print(f'Connection with {username} established')
                    in_chat = True
                    t2 = threading.Thread(target=receive_messages)
                    t2.start()
                    
                    send_messages(host)
                    
                    return
                # if the decision is no send DECLINE message
                elif decision in ('n','no','nein'):
                    msg_type= MessageType.DECLINE.to_bytes()
                    server_socket.sendto(msg_type,addr)
                    print('Conncection declined, going back to main menu')
                    return
        else: 
            print('got unexpcted message type, going back to menu')
            return
    except socket.timeout:
        print("No requests came, going back to menu")
        return
    except ConnectionResetError:
        print("Lost connection with daemon. Please restart an app")
        sys.exit(0)
        

#function that asks to choose option
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
        else:
            print("Invalid option. Please try again.")
            continue


#function to request the chat
def request_chat(host):
    global server_socket,t2,in_chat
    while True:
        ip = input("Provide IP for chat request: ").encode()
        try:
            #send REQUEST message to daemon
            msg_type = MessageType.REQUEST.to_bytes()
            msg = b''.join([msg_type,ip])
            server_socket.sendto(msg,(host, 7778))
            server_socket.settimeout(60)
            print(f'Connection request to {ip.decode()} was send. Waiting for 60 seconds to reply')
            reply,_ = server_socket.recvfrom(1024)
            header = build_header(reply)
            #if receive message is ACCEPT start receiving messages and send message with host and username
            if header.type == MessageType.ACCEPT:
                print(f'successfully connected to {header.username}')
                in_chat = True
                t2 = threading.Thread(target=receive_messages)
                t2.start()
                
                send_messages(host)
                
                return
            #if received message is DECLINE proceed to menu
            elif header.type == MessageType.DECLINE:
                print(f"Connection was not accepted by {header.username}")
                print("try again later")
                return 
            
            elif header.type == MessageType.ERROR:
                print(f"User is busy in other chat")
                return
            else: raise ValueError
            
        except socket.timeout:
            print(f"Timeout expired, no reply from {ip}, try again later")
            return
        
        except ConnectionResetError:
            print("Lost connection with daemon. Please restart an app")
            sys.exit(0)


#function to send messages to the daemon
def send_messages(host):
    global server_socket, username,in_chat
    
    while in_chat:
        
        try:
            #if client is the one who is going to send the message, he is the one if he was the one requesting the chat,but not waiting

            msg = input()
            #if message is q send DISCONNECT_REQUEST to daemon and stop sending messages
            if msg.lower() == "q":
                msg_type = MessageType.DISCONNECT_REQUEST.to_bytes()     
                server_socket.sendto(msg_type,(host,7778))
                print("Disconnect request sent...")
                in_chat = False

                return
            msg = msg.encode('ascii')
                
            msg_type = MessageType.CHAT.to_bytes()
            msg = b''.join([msg_type,msg])
            server_socket.sendto(msg,(host,7778))
            continue
        except UnicodeEncodeError:
            print("only latin characters")
            continue
        except ConnectionResetError:
            print("Lost connection with daemon. Please restart an app")
            sys.exit(0)
    else:
        return
    

#function to receive a message
def receive_messages():
    global server_socket, username, in_chat
    server_socket.settimeout(1)
    
    while True:
        if in_chat:
            try:
                msg,_ = server_socket.recvfrom(1024)
                header = build_header(msg)
                #if message type is CHAT print message
                if header.type == MessageType.CHAT:
                    print(header.username,">",get_payload(msg))
                    continue

                #if message type is DISCONNECT_REQUEST proceed to menu and stop receiving mesages
                elif header.type == MessageType.DISCONNECT_REQUEST:
                    print("companion left the chat, returning to menu")
                    print("type anything to be able to choose an option")
                    in_chat = False
                    return
                    menu()
                    break
                #if message type is DISCONNECTION proceed to menu and stop receiving mesages
                elif header.type == MessageType.DISCONNECTION:
                    print("received confirmation")
                    in_chat = False
                    return
                #if message type is ERROR disconnect person from chat
                elif header.type == MessageType.ERROR:
                    print('got an error message from the server')
                    print(get_payload(msg))
                    in_chat = False
                    return

            except socket.timeout:
                continue

            except ConnectionResetError:
                print("Daemon does not respond, forcibly quitting... an application")
                sys.exit(0)
        else:
            return


#function to quite the daemon
def quit_daemon(host) -> None:
    global server_socket,daemon_ip
    #send DISCONNECTION message to the daemon
    msg_type = MessageType.DISCONNECTION.to_bytes()
    server_socket.sendto(msg_type,(host,7778))
    server_socket.settimeout(10)
    while True:
        try:
            msg, addr = server_socket.recvfrom(1024)
            header = build_header(msg)
            print('received confirmation from daemon',msg)
            #if mesage type is DISCONNECTION quit the daemon
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
        
        except ConnectionResetError:
            print("Daemon does not respond, forcibly quitting...")
            sys.exit(0)



if __name__ == "__main__":
    import random
    global server_socket,daemon_ip
    
    if len(sys.argv) != 2:
        print("Usage: python client.py <daemon_ip>")
        sys.exit(1)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('127.0.'+str(random.randint(1,192))+'.'+str(time.time_ns())[random.randint(10,15)], 7778)) #generate random ip
    daemon_ip = sys.argv[1]

    connect(daemon_ip)
