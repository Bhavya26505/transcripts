import socket

def check_port(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False

ports = [1234, 8080, 5000, 11434, 8000]
print("Checking local ports for LLM server:")
for p in ports:
    res = check_port("127.0.0.1", p)
    print(f"Port {p}: {'OPEN' if res else 'CLOSED'}")
