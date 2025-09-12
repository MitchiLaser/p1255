import socket

# ----- Configuration -----
HOST = '172.23.167.5'  # Replace with the device's IP
PORT = 42002            # Replace with the device's port
OUTPUT_FILE = 'received.bmp'
TIMEOUT = 5  # seconds

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.settimeout(TIMEOUT)  # avoid hanging forever
    s.connect((HOST, PORT))

    s.sendall(b'STARTBMP')
    print("Sent STARTBMP command.")

    # Receive 12-byte custom header
    header = s.recv(12)
    if len(header) < 12:
        raise ValueError("Received incomplete header")

    file_size = int.from_bytes(header[0:4], byteorder='little')
    print(f"Reported BMP size: {file_size} bytes (excluding header)")

    # Receive exactly file_size bytes
    bmp_data = bytearray()
    total_received = 0

    while total_received < file_size:
        try:
            chunk = s.recv(min(4096, file_size - total_received))
        except socket.timeout:
            print("\nSocket timeout: no more data received.")
            break
        if not chunk:
            print("\nConnection closed by server.")
            break
        bmp_data.extend(chunk)
        total_received += len(chunk)
        print(f"Received {total_received}/{file_size} bytes...", end='\r')

print(f"\nTotal received: {total_received} bytes")

# Save only the data received
with open(OUTPUT_FILE, 'wb') as f:
    f.write(bmp_data)

print(f"BMP saved to {OUTPUT_FILE} ({len(bmp_data)} bytes)")