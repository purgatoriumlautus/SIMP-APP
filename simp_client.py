import socket
import sys
from threading import Thread
import time
from multiprocessing import Process

def connect(host) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        username = input("Provide username: ")
        s.sendto(username.encode("utf-8"), (host, 7778))
        reply, _ = s.recvfrom(1024)
        response = reply.decode("utf-8")
        print(response)
        return response


def request_chat(host) :
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        ip = input("Provide IP for chat request: ")
        message = f"start:{ip}"
        s.sendto(message.encode("utf-8"), (host, 7778))


def timeout_notifier(wait_time):
    flip = 1
    if wait_time > 0:
        while wait_time > 0:
            print(".",end="\n")
            flip += 1
            wait_time -= 1
            time.sleep(1)
        return True
    return False



def chat(host) :
    '''with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        timeout = 5
        timeout_printer = Process(target=timeout_notifier, args=(timeout,))
        timeout_printer.start()     
        s.settimeout(timeout)
        
        while True:
            try:
                reply, _ = s.recvfrom(1024)
                timeout_printer.terminate()
                    
                response = reply.decode("utf-8")
                print(f"Received message: {response}")

                if response.lower() == "quit":
                    print("Other user has ended the chat.")
                    break

                message = input("Enter your message: ")
                if message.lower() == "quit":
                    s.sendto("quit".encode("utf-8"), (host, 7778))
                    break
                s.sendto(message.encode("utf-8"), (host, 7778))

            except socket.timeout:
                print("Timeout occurred, no response received.")
                break
            except OSError as e:
                print(f"Error receiving data: {e}")
                break
    '''
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        ip = input("Provide IP to wait for: ")
        message = f"wait:{ip}"
        s.sendto(message.encode("utf-8"), (host, 7778))
def quit_daemon(host) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto("q".encode("utf-8"), (host, 7778))
        s.settimeout(10)
        while True:
            try:
                reply, _ = s.recvfrom(1024)
                if reply:
                    print("Daemon notified.Disconnecting from daemon.")
                    sys.exit(0)
            
            except socket.timeout:
                print("Timeout expired, forcibly clossing the connection with daemon.")
                sys.exit(0)




if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python client.py <daemon_ip>")
        sys.exit(1)

    daemon_ip = sys.argv[1]
    response = connect(daemon_ip)

    if response == "Pending":
        chat(daemon_ip)
    else:
        while True:
            print("\nYou can:")
            print("1. Start a new chat")
            print("2. Wait for requests")
            print("q. Quit")
            option = input("\nChoose an option:").strip()

            if option == "1":
                request_chat(daemon_ip)
            elif option == "2":
                print("Waiting for incoming chat requests...")
                chat(daemon_ip)
            elif option.lower() == "q":
                quit_daemon(daemon_ip)
            else:
                print("Invalid option. Please try again.")
