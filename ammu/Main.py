import http.server
import socketserver
import webbrowser
import os
import re
import sys
import html
import json
from urllib.parse import unquote_plus
import signal
import subprocess
import threading
from queue import Queue

def get_selected_path_from_args():
    if len(sys.argv) < 2:
        print("No path provided. Please provide a valid path.")
        sys.exit(1)
    return sys.argv[1]


# Dynamically set BOARDS_PATH from the command-line argument
BOARDS_PATH = "/home/ldakamarri/hyd-qts-linux/hwlab"
#BOARDS_PATH = get_selected_path_from_args()
log_queues = {}  # A dictionary to maintain separate log queues for each test suite
lock = threading.Lock()  # Lock to synchronize access to log_queues
running_process = None

# Architecture options
architectures = ["aarch64", "armle-v7", "x86_64"]

# Variants and their respective test suites
variants = {
    "le": [
        "deva.suite", "devag.suite", "devb.suite", "devb2.suite", "devbenchmark.suite",
        "devc.suite", "devdvfs.suite", "devetfs.suite", "devf.suite", "devfinjector.suite", "devfmea.suite",
        "devg.suite", "devi.suite", "devi2c.suite", "devkernel.suite", "devkerstatic.suite", "devmme.suite",
        "devn.suite", "devnand.suite", "devp.suite", "devpacketgen.suite",
        "devpci.suite", "devsir.suite", "devsock.suite", "devspi.suite", "devqlite.suite", "devstartup.suite",
        "devsysint.suite", "devsyspage.suite", "devu.suite", "devumassenum.suite", 
        "devwifi.suite", "devwifiwpa.suite"
    ],
    "le.smp": [
        "deva.suite", "devag.suite", "devb.suite", "devb2.suite", "devbenchmark.suite",
        "devc.suite", "devdvfs.suite", "devetfs.suite", "devf.suite", "devfinjector.suite", "devfmea.suite",
        "devg.suite", "devi.suite", "devi2c.suite", "devkernel.suite", "devkerstatic.suite", "devmme.suite",
        "devn.suite", "devnand.suite", "devp.suite", "devpacketgen.suite",
        "devpci.suite", "devsir.suite", "devsock.suite", "devspi.suite", "devqlite.suite", "devstartup.suite",
        "devsysint.suite", "devsyspage.suite", "devu.suite", "devumassenum.suite", 
        "devwifi.suite", "devwifiwpa.suite"
    ],
    "o.smp": [
        "deva.suite", "devag.suite", "devb.suite", "devb2.suite", "devbenchmark.suite",
        "devc.suite", "devdvfs.suite", "devetfs.suite", "devf.suite", "devfinjector.suite", "devfmea.suite",
        "devg.suite", "devi.suite", "devi2c.suite", "devkernel.suite", "devkerstatic.suite", "devmme.suite",
        "devn.suite", "devnand.suite", "devp.suite", "devpacketgen.suite",
        "devpci.suite", "devsir.suite", "devsock.suite", "devspi.suite", "devqlite.suite", "devstartup.suite",
        "devsysint.suite", "devsyspage.suite", "devu.suite", "devumassenum.suite", 
        "devwifi.suite", "devwifiwpa.suite"
    ]
}

# Function to get list of available boards from the BOARDS_PATH directory
def get_boards():
    try:
        return sorted([board for board in os.listdir(BOARDS_PATH) if os.path.isdir(os.path.join(BOARDS_PATH, board))])
    except FileNotFoundError:
        return []

def create_makefile(directory, content):
    makefile_path = os.path.join(directory, "Makefile")
    with open(makefile_path, "w") as f:
        f.write(content)

def create_variant_directory(architecture_path, variant, testsuite):
    subfolder_name = f"{variant}.{testsuite.replace('.suite','').strip()}"
    subfolder_path = os.path.join(architecture_path,subfolder_name)
    os.makedirs(subfolder_path, exist_ok=True)
    makefile_content = f"# Makefile for {subfolder_name}\ninclude ../../common.mk\n"
    create_makefile(subfolder_path, makefile_content)

def run_make_command(board, architecture, variant, testsuite):
    """
    Runs the `make REBOOT_TARGET=0 check` command for a specific test suite and streams logs.
    """
    global log_queues, active_processes
    subfolder_name = f"{variant}.{testsuite.replace('.suite', '')}"
    board_path = os.path.join(BOARDS_PATH, board, architecture, subfolder_name)
    print(f"{board_path}")

    if not os.path.exists(board_path):
        log_queues[testsuite].put(f"Error: Directory {board_path} does not exist.")
        return
    command = f"bash -c 'cd {board_path} && rm -f nohup.out && touch nohup.out && {env_script} && nohup make REBOOT_TARGET=0 check'"
    #command = f"bash -c 'cd {board_path} && rm -f nohup.out && touch nohup.out && source ~/hyd-qts-linux/setqts-env.sh 710 && make REBOOT_TARGET=0 check'"
    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    active_processes.append(process)

    for line in process.stdout:
        log_queues[testsuite].put(line.strip())

    for line in process.stderr:
        log_queues[testsuite].put(f"[ERROR] {line.strip()}")

    process.wait()
    log_queues[testsuite].put(f"Completed test suite: {testsuite}")
    active_processes.remove(process)

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    
    def do_GET(self):
        if self.path.startswith('/get_common_mk?board='):
            board = self.path.split('=')[1]
            board_path = os.path.join(BOARDS_PATH, board)
            common_mk_path = os.path.join(board_path, "common.mk")

            # Check if common.mk exists and read its content, otherwise use default data
            if os.path.exists(common_mk_path):
                with open(common_mk_path, "r") as file:
                    data = file.read()
            else:
                data = """include qconfig.mk
include $(MKFILES_ROOT)/qmacros.mk
$(info $<span class="math-inline">PRODUCT\_ROOT is \[</span>{PRODUCT_ROOT}])
$(info $<span class="math-inline">MKFILES\_ROOT is \[</span>{MKFILES_ROOT}])
# Uncomment the following line to add a customized boot procedure
MSCRIPT=../../machines.exp  
NETPORT= 
SERIALPORT=/does/not/exist    
CSCRIPT=../../tsclear.exp
CONNECTMODE=qrawtcpip
TERMAPP=termserv
BSP_Name=
include $(PRODUCT_ROOT)/qtslab.mk
"""     

            # Send the content as plain text
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(data.encode("utf-8"))

        # Serve the main page with form if no query parameter is given
        elif self.path == '/':
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            boards = get_boards()
            html_content = f"""
            <!doctype html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>BSP Testing</title>
            </head>
            <body>
                <h1>BSP Testing</h1>
                <label for="board">Select Board:</label>
                <select id="board" onchange="loadCommonMK()">
                    <option value="">--Choose Board--</option>
                    {"".join(f'<option value="{html.escape(board)}">{html.escape(board)}</option>' for board in boards)}
                </select>
                
                <label for="architecture">Select Architecture:</label>
                <select id="architecture">
                    <option value="">--Choose Architecture--</option>
                    {"".join(f'<option value="{html.escape(arch)}">{html.escape(arch)}</option>' for arch in architectures)}
                </select>

                <label for="variant">Select Variant:</label>
                <select id="variant" onchange="updateTestsuites()">
                    <option value="">--Choose Variant--</option>
                    <option value="le">le</option>
                    <option value="le.smp">le.smp</option>
                    <option value="o.smp">o.smp</option>
                </select>
                
                <h2>Select Test Suites</h2>
                <div id="testsuites"></div>
                
                <h1>common.mk</h1>
                <textarea id="data" rows="20" cols="80"></textarea><br><br>

                <button onclick="saveChanges()">Save Changes</button>
                
                <h2>Actions</h2>
                <label for="env_script">Path to setqts-env.sh:</label>
                <input type="text" id="env_script" placeholder="e.g., source ~/hyd-qts-linux/setqts-env.sh 710" style="width: 400px;"><br><br>
                                
                <button onclick="makeClean()">make clean</button>
                <button onclick="makeCheck()">make check</button>
                <button onclick="makeRebootCheck()">make REBOOT_TARGET=0 check</button>
                <button onclick="stopTest()">Stop Test</button>

                <p id="status"></p>

                <script>
                    const variants = {str(variants).replace("'", '"')};

                    function updateTestsuites() {{
                        const variant = document.getElementById("variant").value;
                        const testsuitesDiv = document.getElementById("testsuites");
                        testsuitesDiv.innerHTML = "";

                        if (variant in variants) {{
                            variants[variant].forEach(suite => {{
                                const checkbox = document.createElement("input");
                                checkbox.type = "checkbox";
                                checkbox.name = "testsuite";
                                checkbox.value = suite;
                                checkbox.id = suite;

                                const label = document.createElement("label");
                                label.htmlFor = suite;
                                label.appendChild(document.createTextNode(suite));

                                testsuitesDiv.appendChild(checkbox);
                                testsuitesDiv.appendChild(label);
                                testsuitesDiv.appendChild(document.createElement("br"));
                            }});
                        }}
                    }}

                    function loadCommonMK() {{
                        const board = document.getElementById("board").value;
                        if (!board) {{
                            document.getElementById("data").value = "Select a board to view common.mk content.";
                            return;
                        }}

                        fetch(`/get_common_mk?board=${{encodeURIComponent(board)}}`)
                        .then(response => response.text())
                        .then(data => {{
                            document.getElementById("data").value = data;
                        }})
                        .catch(error => {{
                            document.getElementById("data").value = "Error loading common.mk: " + error;
                        }});
                    }}

                    function saveChanges() {{
                        const data = document.getElementById("data").value;
                        const board = document.getElementById("board").value;
                        const architecture = document.getElementById("architecture").value;
                        const variant = document.getElementById("variant").value;

                        if (!board || !architecture || !variant) {{
                            document.getElementById("status").innerText = "Please select all fields.";
                            return;
                        }}

                        const testsuiteElems = document.querySelectorAll("input[name='testsuite']:checked");
                        const testsuites = Array.from(testsuiteElems).map(elem => elem.value).join(", ");

                        const postData = 'data=' + encodeURIComponent(data) + 
                                         '&board=' + encodeURIComponent(board) +
                                         '&architecture=' + encodeURIComponent(architecture) + 
                                         '&variant=' + encodeURIComponent(variant) + 
                                         '&testsuites=' + encodeURIComponent(testsuites);

                        fetch('/save', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/x-www-form-urlencoded',
                            }},
                            body: postData
                        }})
                        .then(response => response.text())
                        .then(result => document.getElementById("status").innerText = result)
                        .catch(error => {{
                            document.getElementById("status").innerText = "Error: " + error;
                        }});
                    }}

                    function makeClean() {{
                        const board = document.getElementById("board").value;
                        const architecture = document.getElementById("architecture").value;
                        const variant = document.getElementById("variant").value;
                        const env_script = document.getElementById("env_script").value; // Get the path
                        const testsuiteElems = document.querySelectorAll("input[name='testsuite']:checked");
                        const testsuites = Array.from(testsuiteElems).map(elem => elem.value).join(",");

                        document.getElementById("status").innerText = "Test is in process...";
                        
                        fetch('/make_clean', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                board: board,
                                architecture: architecture,
                                variant: variant,
                                testsuites: testsuites,
                                env_script: env_script
                                
                            }})
                        }})
                        .then(() => {{
                        const eventSource = new EventSource('/get_logs');
                        eventSource.onmessage = (event) => {{
                            document.getElementById("logs").value += event.data + "\\n";
                        }};
                    }})
                    .catch(error => {{
                        document.getElementById("status").innerText = "Error: " + error;
                    }});
                }}

                    function makeCheck() {{
                        const board = document.getElementById("board").value;
                        const architecture = document.getElementById("architecture").value;
                        const variant = document.getElementById("variant").value;
                        const env_script = document.getElementById("env_script").value; // Get the path
                        const testsuiteElems = document.querySelectorAll("input[name='testsuite']:checked");
                        const testsuites = Array.from(testsuiteElems).map(elem => elem.value).join(",");

                        document.getElementById("status").innerText = "Test is in process...";
                        
                        fetch('/make_check', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                board: board,
                                architecture: architecture,
                                variant: variant,
                                testsuites: testsuites,
                                env_script: env_script
                                
                            }})
                        }})
                        .then(() => {{
                        const eventSource = new EventSource('/get_logs');
                        eventSource.onmessage = (event) => {{
                            document.getElementById("logs").value += event.data + "\\n";
                        }};
                    }})
                    .catch(error => {{
                        document.getElementById("status").innerText = "Error: " + error;
                    }});
                }}

                    function makeRebootCheck() {{
                        const board = document.getElementById("board").value;
                        const architecture = document.getElementById("architecture").value;
                        const variant = document.getElementById("variant").value;
                        const env_script = document.getElementById("env_script").value; // Get the path
                        const testsuiteElems = document.querySelectorAll("input[name='testsuite']:checked");
                        const testsuites = Array.from(testsuiteElems).map(elem => elem.value).join(",");

                        document.getElementById("status").innerText = "Test is in process...";
                        
                        fetch('/make_reboot_check', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json'
                            }},
                            body: JSON.stringify({{
                                board: board,
                                architecture: architecture,
                                variant: variant,
                                testsuites: testsuites,
                                env_script: env_script
                                
                            }})
                        }})
                        .then(() => {{
                        const eventSource = new EventSource('/get_logs');
                        eventSource.onmessage = (event) => {{
                            document.getElementById("logs").value += event.data + "\\n";
                        }};
                    }})
                }}

                    function stopTest() {{
                        fetch('/stop_test', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                            }},
                        }})
                        .then(response => response.json())
                        .then(data => {{
                            document.getElementById("status").innerText = data.message;
                        }})
                        .catch(error => {{
                            document.getElementById("status").innerText = "Error stopping test: " + error;
                        }});
                    }}

                </script>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode("utf-8"))

    def _send_response(self, status_code, message):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(message).encode())        
    

    def do_POST(self):
        if self.path == '/save':
            length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(length).decode('utf-8')
            data_dict = {}

            # Safely parse the POST data into a dictionary
            for item in unquote_plus(post_data).split("&"):
                if "=" in item:
                    key, value = item.split("=", 1)  # Split only once on the first "="
                    data_dict[key] = value

            # Assuming board, architecture, variant, testsuites, and data are passed
            board = data_dict.get("board")
            architecture = data_dict.get("architecture")
            variant = data_dict.get("variant")
            testsuites = data_dict.get("testsuites")
            common_mk_data = data_dict.get("data")

            if board and architecture and variant:
                # Create the necessary directories
                board_path = os.path.join(BOARDS_PATH, board)
                architecture_path = os.path.join(board_path, architecture)

                # Check if the architecture directory exists, if not create it
                if not os.path.exists(architecture_path):
                    os.makedirs(architecture_path)

                # Create the necessary variant directories
                for suite in testsuites.split(','):
                    create_variant_directory(architecture_path, variant, suite)

                # Write the common.mk data to the file
                common_mk_path = os.path.join(board_path, "common.mk")
                with open(common_mk_path, "w") as f:
                    f.write(common_mk_data)

                self.send_response(200)
                self.end_headers()
                self.wfile.write("Saved common.mk and created test suite directories.".encode("utf-8"))

        elif self.path == '/get_logs':
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()

            while True:
                try:
                    log_message = log_queues[testsuite].get(timeout=1)  # Adjust timeout as needed
                    self.wfile.write(f"data: {html.escape(log_message)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"Error sending log: {e}")
                    break

        
        elif self.path == '/make_clean':
            self.make_clean()

        elif self.path == '/make_check':
            self.make_check()

        elif self.path == '/make_reboot_check':
            self.make_reboot_check()

        elif self.path == '/stop_test':
            self.stop_test()

    def make_clean(self):
        global running_process, stop_event
        try:
            print(f"make start")
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            data_dict = json.loads(post_data)

            board = data_dict.get("board")
            architecture = data_dict.get("architecture")
            variant = data_dict.get("variant")
            testsuites = data_dict.get("testsuites")
            env_script = data_dict.get("env_script")
            
            if not all([board, architecture, variant, testsuites]):
                self._send_response(400, {"error": "Missing board, architecture, variant, or testsuites."})
                return
            
            
            qtslab_path = os.path.join(BOARDS_PATH, 'qtslab.mk')
            print(f"{qtslab_path}")
            
            if not os.path.exists(qtslab_path):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error: qtslab.mk does not exist at {qtslab_path}".encode("utf-8"))
                return

            selected_testsuites = testsuites.split(",")
            test_results = []

            for suite in selected_testsuites:
                suite_name = suite.strip().replace('.suite', '')
                board_path = os.path.join(BOARDS_PATH, board, architecture, f"{variant}.{suite_name}")    

                if not os.path.exists(board_path):        
                    test_results.append(f"Error: Directory {board_path} does not exist.")
                    continue
                
                command = f"bash -c 'cd {board_path} && rm -f nohup.out && touch nohup.out && {env_script} && nohup make clean'"
                #command = f"bash -c 'cd {board_path} && rm -f nohup.out && touch nohup.out && source ~/hyd-qts-linux/setqts-env.sh 710 && make clean'"
                print(f"Running command: {command}")

                process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                stdout_lines = []
                stderr_lines = []

                for line in process.stdout:
                    log_queues[suite].put(line.strip())  # Store log in the queue
                    print(line.strip())  # Log to server console
                    self.wfile.write(f"data: {html.escape(line.strip())}\n\n".encode("utf-8"))
                    self.wfile.flush()

                for line in process.stderr:
                    log_queues[suite].put(f"[ERROR] {line.strip()}")  # Store error in the queue
                    print(f"[ERROR] {line.strip()}")  # Log errors to server console
                    self.wfile.write(f"data: [ERROR] {html.escape(line.strip())}\n\n".encode("utf-8"))
                    self.wfile.flush()

                process.wait()

                test_results.append(f"Completed: {suite_name}")
                test_results.append("STDOUT:\n" + "\n".join(stdout_lines))
                test_results.append("STDERR:\n" + "\n".join(stderr_lines))    

            summary = "\n".join(test_results)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(summary.encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Server Error: {e}".encode("utf-8"))

    def make_ckeck(self):
        global running_process, stop_event
        try:
            print(f"make start")
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode("utf-8")
            data_dict = json.loads(post_data)

            board = data_dict.get("board")
            architecture = data_dict.get("architecture")
            variant = data_dict.get("variant")
            testsuites = data_dict.get("testsuites")
            env_script = data_dict.get("env_script")
            
            if not all([board, architecture, variant, testsuites]):
                self._send_response(400, {"error": "Missing board, architecture, variant, or testsuites."})
                return
            
            
            qtslab_path = os.path.join(BOARDS_PATH, 'qtslab.mk')
            print(f"{qtslab_path}")
            
            if not os.path.exists(qtslab_path):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error: qtslab.mk does not exist at {qtslab_path}".encode("utf-8"))
                return

            selected_testsuites = testsuites.split(",")
            test_results = []

            for suite in selected_testsuites:
                suite_name = suite.strip().replace('.suite', '')
                board_path = os.path.join(BOARDS_PATH, board, architecture, f"{variant}.{suite_name}")    

                if not os.path.exists(board_path):        
                    test_results.append(f"Error: Directory {board_path} does not exist.")
                    continue
                
                command = f"bash -c 'cd {board_path} && rm -f nohup.out && touch nohup.out && {env_script} && nohup make check'"
                #command = f"bash -c 'cd {board_path} && rm -f nohup.out && touch nohup.out  && source ~/hyd-qts-linux/setqts-env.sh 710 && make check'"
                print(f"Running command: {command}")

                process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

                stdout_lines = []
                stderr_lines = []

                for line in process.stdout:
                    log_queues[suite].put(line.strip())  # Store log in the queue
                    print(line.strip())  # Log to server console
                    self.wfile.write(f"data: {html.escape(line.strip())}\n\n".encode("utf-8"))
                    self.wfile.flush()

                for line in process.stderr:
                    log_queues[suite].put(f"[ERROR] {line.strip()}")  # Store error in the queue
                    print(f"[ERROR] {line.strip()}")  # Log errors to server console
                    self.wfile.write(f"data: [ERROR] {html.escape(line.strip())}\n\n".encode("utf-8"))
                    self.wfile.flush()

                process.wait()

                test_results.append(f"Completed: {suite_name}")
                test_results.append("STDOUT:\n" + "\n".join(stdout_lines))
                test_results.append("STDERR:\n" + "\n".join(stderr_lines))    

            summary = "\n".join(test_results)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(summary.encode("utf-8"))

            # Execute r.py after the make command completes
            boardpath = os.path.join(BOARDS_PATH, board, architecture, f"{variant}.{suite_name}")
            print(f'{boardpath}')
            os.chdir(boardpath)
            r = subprocess.run(["python3", "/home/ldakamarri/hyd-qts-linux/BSP_Automation_Run/report_html.py", BOARDS_PATH, board]) 
            print(f"{r}")

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Server Error: {e}".encode("utf-8"))

    def make_reboot_check(self):
        global running_process, stop_event

        try:
            print("make start")

            # Parse content length and body
            try:
                content_length = int(self.headers.get('Content-Length', 0))
            except ValueError:
                self._send_response(400, {"error": "Invalid Content-Length"})
                return

            post_data = self.rfile.read(content_length).decode("utf-8")
            data_dict = json.loads(post_data)

            board = data_dict.get("board")
            architecture = data_dict.get("architecture")
            variant = data_dict.get("variant")
            testsuites = data_dict.get("testsuites")
            env_script = data_dict.get("env_script")

            if not all([board, architecture, variant, testsuites, env_script]):
                self._send_response(400, {"error": "Missing board, architecture, variant, testsuites, or env_script."})
                return

            qtslab_path = os.path.join(BOARDS_PATH, 'qtslab.mk')
            if not os.path.exists(qtslab_path):
                self._send_response(400, {"error": f"qtslab.mk does not exist at {qtslab_path}"})
                return

            selected_testsuites = testsuites.split(",")
            test_results = []

            # Stream response headers for Server-Sent Events (SSE)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            board_p = os.path.join(BOARDS_PATH, board)
            common_mk_path = os.path.join(board_p, "common.mk")
            telnet_host, telnet_port = None, None

            if os.path.exists(common_mk_path):
                with open(common_mk_path, "r") as f:
                    for line in f:
                        match = re.match(r"^NETPORT\s*=\s*([^\s:]+):(\d+)", line.strip())
                        if match:
                            telnet_host, telnet_port = match.groups()
                            telnet_port = int(telnet_port)
                            break

            print(f"Telnet Host: {telnet_host}, Telnet Port: {telnet_port}")
            if not telnet_host or not telnet_port:
                self._send_response(400, {"error": "Missing telnet_host or telnet_port"})
                return

            # Establish Telnet connection once before tests start
            telnet_command = f"bash -c '(echo; sleep 2; echo -e '\035'; sleep 1; echo quit) | telnet {telnet_host} {telnet_port}'"
            print(f"Running Telnet reset command: {telnet_command}")

            try:
                telnet_process = subprocess.Popen(telnet_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                telnet_stdout, telnet_stderr = telnet_process.communicate()

                for line in telnet_stdout.splitlines():
                    self.wfile.write(f"data: {html.escape(line.strip())}\n\n".encode("utf-8"))
                    self.wfile.flush()
                for line in telnet_stderr.splitlines():
                    self.wfile.write(f"data: [ERROR] {html.escape(line.strip())}\n\n".encode("utf-8"))
                    self.wfile.flush()
            except Exception as e:
                self.wfile.write(f"data: Error while resetting Telnet: {html.escape(str(e))}\n\n".encode("utf-8"))
                self.wfile.flush()
                return

            # Proceed with running tests
            for suite in selected_testsuites:
                suite_name = suite.strip().replace('.suite', '')
                board_path = os.path.join(BOARDS_PATH, board, architecture, f"{variant}.{suite_name}")

                if not os.path.exists(board_path):
                    error_msg = f"Error: Directory {board_path} does not exist."
                    test_results.append(error_msg)
                    self.wfile.write(f"data: {html.escape(error_msg)}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    continue

                command = f"bash -c 'cd {board_path} && rm -f nohup.out && touch nohup.out && {env_script} && nohup make REBOOT_TARGET=0 check > nohup.out 2>&1 &'"
                print(f"Running command: {command}")

                try:
                    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    stdout, stderr = process.communicate()

                    for line in stdout.splitlines():
                        self.wfile.write(f"data: {html.escape(line.strip())}\n\n".encode("utf-8"))
                        self.wfile.flush()
                    for line in stderr.splitlines():
                        self.wfile.write(f"data: [ERROR] {html.escape(line.strip())}\n\n".encode("utf-8"))
                        self.wfile.flush()

                    test_results.append(f"Completed: {suite_name}")
                    test_results.append("STDOUT:\n" + stdout)
                    test_results.append("STDERR:\n" + stderr)
                
                except Exception as e:
                    error_msg = f"Error while executing {suite_name}: {e}"
                    test_results.append(error_msg)
                    self.wfile.write(f"data: {html.escape(error_msg)}\n\n".encode("utf-8"))
                    self.wfile.flush()

            # Send summary and execute report script
            summary = "\n".join(test_results)
            self.wfile.write(f"data: {html.escape(summary)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()

            boardpath = os.path.join(BOARDS_PATH, board)
            os.chdir(boardpath)
            try:
                resultc = subprocess.run(["python3", "/home/ldakamarri/hyd-qts-linux/BSP_Automation_Run/report_html.py", BOARDS_PATH, board], check=True)
                print(f"Running command: {resultc}")
            except subprocess.CalledProcessError as e:
                print(f"Report script failed: {e}")

        except Exception as e:
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Server Error: {e}".encode("utf-8"))

        
    def stop_test(self):
        global running_process, stop_event
        try:
            if running_process and running_process.poll() is None:
                print(f"Terminating process with PID: {running_process.pid}") 
                running_process.terminate()
                try:
                    running_process.wait(timeout=5)  # Wait for graceful termination
                except subprocess.TimeoutExpired:
                    print(f"Process {running_process.pid} did not terminate gracefully. Sending SIGKILL.")
                    running_process.kill()
                running_process = None
                self._send_response(200, {"message": "Test stopped successfully."})
                stop_event.set()  # Exit the terminal
            else:
                self._send_response(400, {"message": "No test is currently running."})
        except Exception as e:
            self._send_response(500, {"error": str(e)})
            stop_event.set()  # Exit the terminal with an error code
            

# Set up and run the server on any available port
with socketserver.TCPServer(("", 0), CustomHandler) as httpd:
    assigned_port = httpd.server_address[1]
    print(f"Serving at port {assigned_port}")
    webbrowser.open(f'http://localhost:{assigned_port}/')
    httpd.serve_forever()

if __name__ == "__main__":
    stop_event = threading.Event()
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    try:
        # Wait for the stop signal
        stop_event.wait() 
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt. Stopping server...")
        stop_event.set()
    
    socketserver.TCPServer(("", 0), CustomHandler).shutdown()
    server_thread.join() 

    print("Server stopped.")