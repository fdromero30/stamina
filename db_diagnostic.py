import socket
import ssl
import struct

def pg_probe(host, port, user, db, timeout=20):
    """Full PostgreSQL SSL+auth probe."""
    results = []
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        results.append("  TCP OK")

        ssl_request = struct.pack("!II", 8, 80877103)
        sock.sendall(ssl_request)
        response = sock.recv(1)
        if response != b"S":
            sock.close()
            return ["  SSL rejected"]
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        sock = ctx.wrap_socket(sock, server_hostname=host)
        results.append("  TLS OK")

        params = {"user": user, "database": db}
        body = struct.pack("!II", 196608, 0)
        for k, v in params.items():
            body += k.encode() + b"\x00" + v.encode() + b"\x00"
        body += b"\x00"
        startup = struct.pack("!I", len(body) + 4) + body
        sock.sendall(startup)

        auth_type = sock.recv(1)
        if auth_type == b"R":
            code_data = sock.recv(4)
            code = struct.unpack("!I", code_data)[0] if len(code_data) == 4 else -1
            if code == 10:
                results.append("  SCRAM challenge (tenant EXISTS)")
            elif code == 0:
                results.append("  Auth OK (tenant EXISTS)")
            else:
                results.append(f"  Auth code {code} (tenant EXISTS)")
        elif auth_type == b"E":
            rest = sock.recv(4096)
            err = rest.decode("utf-8", errors="replace")
            if "tenant/user" in err:
                results.append("  tenant not found")
            elif "password" in err.lower():
                results.append("  tenant EXISTS - password rejected")
            else:
                results.append("  ERROR: " + err[:200])
        else:
            results.append("  Unexpected: " + repr(auth_type))
        sock.close()
    except Exception as e:
        results.append("  ERROR: " + str(e))
    return results

db = "postgres"
user = "postgres.ifbrxvkmeiburqagskjs"
out = []

# The pooler verified in DBeaver
out.append("=== Transaction Pooler (aws-1-us-west-2) ===")
out.append("Host: aws-1-us-west-2.pooler.supabase.com")
out.append("Port: 6543")
out.append("User: " + user)
out.append("DB: " + db)
try:
    ip = socket.gethostbyname("aws-1-us-west-2.pooler.supabase.com")
    out.append("DNS OK: " + ip)
except Exception as e:
    out.append("DNS FAILED: " + str(e))
out.extend(pg_probe("aws-1-us-west-2.pooler.supabase.com", 6543, user, db))

with open("/Users/fabianromero/Documents/stamina/stamina_db_check.txt", "w") as f:
    f.write("\n".join(out))
print("done")