import http.server
import socketserver
from urllib.parse import parse_qs
import subprocess
import threading
import socket
import webbrowser

# Predefined servers
SERVERS = {
    "Server 1": "10.123.14.21",  # Replace with actual IP addresses
    "Server 2": "10.123.14.22"
}

# HTML templates
HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
    <title>SSH Login</title>
</head>
<body>
    <h1>SSH Login</h1>
    <form method="POST" action="/login">
        <label for="server">Select Server:</label>
        <select id="server" name="server" required>
            {server_options}
        </select><br><br>
        <label for="username">Username:</label>
        <input type="text" id="username" name="username" required><br><br>
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" required><br><br>
        <button type="submit">Login</button>
    </form>
</body>
</html>
"""

HTML_RESPONSE = """
<!DOCTYPE html>
<html>
<head>
    <title>SSH Login Result</title>
</head>
<body>
    <h1>{status}</h1>
    <pre>{message}</pre>
    {paths}
    <a href="/">Go Back</a>
</body>
</html>
"""

class SSHRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            server_options = "\n".join(
                [f'<option value="{name}">{name}</option>' for name in SERVERS.keys()]
            )
            html_form = HTML_FORM.format(server_options=server_options)
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(html_form.encode("utf-8"))
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        global username, password, hostname, selected_path
        
        if self.path == "/login":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length).decode("utf-8")
            form_data = parse_qs(post_data)

            server_name = form_data.get("server", [None])[0]
            username = form_data.get("username", [None])[0]
            password = form_data.get("password", [None])[0]
            hostname = SERVERS.get(server_name)

            if not server_name or not username or not password or not hostname:
                self.respond("Error", "All fields are required!")
                return

            try:
                ssh_command = f"sshpass -p {password} ssh -o StrictHostKeyChecking=no {username}@{hostname} 'find /home/{username} -type d -name \"hwlab*\"'"
                result = subprocess.run(
                    ssh_command, shell=True, text=True, capture_output=True
                )

                if result.returncode == 0:
                    hwlab_paths = result.stdout.strip().split("\n")
                    if hwlab_paths:
                        paths_html = """
                        <h2>Select HWLab Path:</h2>
                        <form method="POST" action="/navigate">
                            <label for="path">Choose a path:</label>
                            <select id="path" name="path" required>
                        """
                        for path in hwlab_paths:
                            paths_html += f'<option value="{path}">{path}</option>'
                        paths_html += """
                            </select>
                            <br><br>
                            <button type="submit">Proceed</button>
                        </form>
                        """
                        self.respond("Login Successful", paths_html)
                    else:
                        self.respond("Login Successful", "No hwlab directories found.")
                else:
                    self.respond("Login Failed", result.stderr)
            except Exception as e:
                self.respond("Error", str(e))
                
        elif self.path == "/navigate":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length).decode("utf-8")
            form_data = parse_qs(post_data)

            selected_path = form_data.get("path", [None])[0]
            if selected_path:
                try:
                    # Execute the afos.py script with the selected path as an argument
                    print(f"Selected path: {selected_path}")  # Just for logging
                    result = subprocess.run(
                        ["python3", "Main.py", selected_path],  # Pass selected_path as an argument
                        text=True,
                        capture_output=True
                    )
                    
                    if result.returncode == 0:
                        self.respond("Success", f"afos.py executed successfully with path: {selected_path}")
                    else:
                        self.respond("Error Executing afos.py", result.stderr)
                except Exception as e:
                    self.respond("Error", str(e))
            else:
                self.respond("Error", "No path selected.")
                
        else:
            self.send_error(404, "File Not Found")

    def respond(self, status, message, paths=""):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(HTML_RESPONSE.format(status=status, message=message, paths=paths).encode("utf-8"))

def start_server():
    with socketserver.TCPServer(("0.0.0.0", 0), SSHRequestHandler) as httpd:
        port = httpd.server_address[1]
        threading.Thread(target=open_browser, args=("127.0.0.1", port), daemon=True).start()
        httpd.serve_forever()

def open_browser(ip, port):
    webbrowser.open(f"http://{ip}:{port}")

if __name__ == "__main__":
    start_server()