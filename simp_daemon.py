import sys
import socket


def wait_for_client(host: str):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind((host, 7778))
        print("Daemon is waiting for client connections...")
        while True:
            data, client_addr = s.recvfrom(1024)
            print(f"Received data from {client_addr}: {data.decode('utf-8')}")
            response_message = f"Received: {data.decode('utf-8')}"
            print(f"Sending response to {client_addr}: {response_message}")
            s.sendto(response_message.encode("utf-8"), client_addr)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python daemon.py <server_ip>")
        sys.exit(1)

    server_ip = sys.argv[1]
    wait_for_client(server_ip)