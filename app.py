import re
import struct
import socket
import random
from io import BytesIO
from typing import List, Tuple
import smtplib
from dataclasses import dataclass

# DNS-related classes and constants
TYPE_MX = 15
CLASS_IN = 1

@dataclass
class DNSHeader:
    id: int
    flags: int
    num_questions: int = 0
    num_answers: int = 0
    num_authorities: int = 0
    num_additionals: int = 0

@dataclass
class DNSQuestion:
    name: bytes
    type_: int
    class_: int

@dataclass
class DNSRecord:
    name: bytes
    type_: int
    class_: int
    ttl: int
    data: bytes

@dataclass
class DNSPacket:
    header: DNSHeader
    questions: List[DNSQuestion]
    answers: List[DNSRecord]
    authorities: List[DNSRecord]
    additionals: List[DNSRecord]

# DNS encoding functions
def header_to_bytes(header: DNSHeader) -> bytes:
    return struct.pack("!HHHHHH", *dataclasses.astuple(header))

def question_to_bytes(question: DNSQuestion) -> bytes:
    return question.name + struct.pack("!HH", question.type_, question.class_)

def encode_dns_name(domain_name: str) -> bytes:
    encoded = b""
    for part in domain_name.encode("ascii").split(b"."):
        encoded += bytes([len(part)]) + part
    return encoded + b"\x00"

# DNS query building
def build_query(domain_name: str, record_type: int) -> bytes:
    name = encode_dns_name(domain_name)
    id_ = random.randint(0, 65535)
    recursion_desired = 1 << 8
    header = DNSHeader(id=id_, num_questions=1, flags=recursion_desired)
    question = DNSQuestion(name=name, type_=record_type, class_=CLASS_IN)
    return header_to_bytes(header) + question_to_bytes(question)

# DNS response parsing functions
def decode_name(reader: BytesIO) -> bytes:
    parts = []
    while (length := reader.read(1)[0]) != 0:
        if length & 0b1100_0000:
            parts.append(decode_compressed_name(length, reader))
            break
        else:
            parts.append(reader.read(length))
    return b".".join(parts)

def decode_compressed_name(length: int, reader: BytesIO) -> bytes:
    pointer_bytes = bytes([length & 0b0011_1111]) + reader.read(1)
    pointer = struct.unpack("!H", pointer_bytes)[0]
    current_pos = reader.tell()
    reader.seek(pointer)
    result = decode_name(reader)
    reader.seek(current_pos)
    return result

def parse_header(reader: BytesIO) -> DNSHeader:
    items = struct.unpack("!HHHHHH", reader.read(12))
    return DNSHeader(*items)

def parse_question(reader: BytesIO) -> DNSQuestion:
    name = decode_name(reader)
    data = reader.read(4)
    type_, class_ = struct.unpack("!HH", data)
    return DNSQuestion(name, type_, class_)

def parse_record(reader: BytesIO) -> DNSRecord:
    name = decode_name(reader)
    data = reader.read(10)
    type_, class_, ttl, data_len = struct.unpack("!HHIH", data)
    record_data = reader.read(data_len)
    return DNSRecord(name, type_, class_, ttl, record_data)

def parse_dns_packet(data: bytes) -> DNSPacket:
    reader = BytesIO(data)
    header = parse_header(reader)
    questions = [parse_question(reader) for _ in range(header.num_questions)]
    answers = [parse_record(reader) for _ in range(header.num_answers)]
    authorities = [parse_record(reader) for _ in range(header.num_authorities)]
    additionals = [parse_record(reader) for _ in range(header.num_additionals)]
    return DNSPacket(header, questions, answers, authorities, additionals)

# Parse MX data from record
def parse_mx_data(data: bytes) -> Tuple[int, str]:
    preference, = struct.unpack("!H", data[:2])
    reader = BytesIO(data[2:])
    exchange = decode_name(reader)
    return preference, exchange.decode('utf-8')

# Get MX records for a domain
def get_mx_records(domain: str) -> List[Tuple[int, str]]:
    query = build_query(domain, TYPE_MX)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(query, ("8.8.8.8", 53))  # Using Google's public DNS resolver
    data, _ = sock.recvfrom(1024)
    packet = parse_dns_packet(data)
    mx_records = []
    for answer in packet.answers + packet.authorities:  # Check answers and authorities
        if answer.type_ == TYPE_MX:
            pref, exchange = parse_mx_data(answer.data)
            mx_records.append((pref, exchange))
    return mx_records

# Email validation function
def validate_email(email: str) -> Tuple[bool, str]:
    # Step 1: Syntax check
    match = re.match(r'^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email.lower())
    if not match:
        return False, "Invalid syntax"

    # Step 2: Split and get MX records
    _, domain = email.split('@')
    try:
        mx_records = get_mx_records(domain)
        if not mx_records:
            return False, "No MX records found for domain"
        
        # Sort by preference (lowest number first)
        mx_records.sort(key=lambda x: x[0])
        
        # Step 3: SMTP verification on each MX
        local_host = socket.gethostname()
        for _, mx_host in mx_records:
            try:
                server = smtplib.SMTP(mx_host, timeout=10)
                server.set_debuglevel(0)  # Set to 1 for verbose output
                server.helo(local_host)
                server.mail('do-not-reply@validator.com')  # Neutral sender; adjust if needed
                code, _ = server.rcpt(email)
                server.quit()
                if code == 250:
                    return True, "Valid email"
            except Exception as e:
                continue  # Try next MX
        return False, "Mailbox does not exist or connection failed"
    except Exception as e:
        return False, f"Validation error: {str(e)}"

# Example usage
if __name__ == "__main__":
    emails_to_test = [
        "test@gmail.com",
        "invalid@nonexistentdomain.xyz",
        "bad_syntax_email",
    ]
    for email in emails_to_test:
        is_valid, message = validate_email(email)
        print(f"{email}: {is_valid} - {message}")
        