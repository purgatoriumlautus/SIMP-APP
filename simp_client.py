import socket
import sys

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

def chat(host) :
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(5)
        while True:
            try:
                reply, _ = s.recvfrom(1024)
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

def quit_daemon(host) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto("q".encode("utf-8"), (host, 7778))
        print("Disconnected from daemon.")
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
            option = input("Choose an option: ").strip()

            if option == "1":
                request_chat(daemon_ip)
            elif option == "2":
                print("Waiting for incoming chat requests...")
                chat(daemon_ip)
            elif option.lower() == "q":
                quit_daemon(daemon_ip)
            else:
                print("Invalid option. Please try again.")
