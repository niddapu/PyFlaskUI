import os
import re
import http.server
import socketserver
import webbrowser
import sys
import chardet

# Get the BOARDS_PATH and board information from command-line arguments
BOARDS_PATH = sys.argv[1]
board = sys.argv[2]

# Get the current working directory
current_dir = os.getcwd()
print(f"Current directory: {current_dir}")

# Search for directories in the current directory
directories = [d for d in os.listdir(current_dir) if os.path.isdir(os.path.join(current_dir, d))]
architecture = directories[0] if directories else "No directory found"

# Initialize lists to store paths of .sum and .log files
sum_file_paths = []
log_file_paths = []

# Walk through the directory to find .sum and .log files

for root, dirs, files in os.walk(current_dir):
    for file_name in files:
        print(f"Checking file: {file_name}")
        if file_name.startswith('dev') and file_name.endswith('.sum'):
            sum_file_path = os.path.join(root, file_name)
            sum_file_paths.append(sum_file_path)
            print(f"Found .sum file: {sum_file_path}")
        elif file_name.endswith('.log'):
            log_file_path = os.path.join(root, file_name)
            log_file_paths.append(log_file_path)
            print(f"Found .log file: {log_file_path}")

if not sum_file_paths or not log_file_paths:
    raise FileNotFoundError("Required .sum or .log file not found in the current directory or its subdirectories.")

# Initialize counters and lists for each .sum file
summary_data = {}
for sum_file_path in sum_file_paths:
    file_name = os.path.basename(sum_file_path).replace('.sum', '.suite')
    summary_data[file_name] = {
        "expected_passes": 0,
        "unexpected_failures": 0,
        "unresolved_testcases": 0,
        "untested_testcases": 0,
        "passes_files": [],
        "failures_files": [],
        "unresolved_files": [],
        "untested_files": [],
        "all_data": [],
        "path": sum_file_path
    }
    # Read the content of the .sum file
    with open(sum_file_path, 'r') as file:
        lines = file.readlines()

    # Process each line to extract the required information if '/tmp' is present in the line
    for line in lines:
        if '/tmp' not in line:
            continue
        status = None
        match = re.search(r'(\S+\.sh)', line)
        if 'PASS' in line:
            summary_data[file_name]["expected_passes"] += 1
            status = 'PASS'
            if match:
                summary_data[file_name]["passes_files"].append(match.group(1))
        elif 'FAIL' in line:
            summary_data[file_name]["unexpected_failures"] += 1
            status = 'FAIL'
            if match:
                summary_data[file_name]["failures_files"].append(match.group(1))
        elif 'UNRESOLVED' in line:
            summary_data[file_name]["unresolved_testcases"] += 1
            status = 'UNRESOLVED'
            if match:
                summary_data[file_name]["unresolved_files"].append(match.group(1))
        elif 'UNTESTED' in line:
            summary_data[file_name]["untested_testcases"] += 1
            status = 'UNTESTED'
            if match:
                summary_data[file_name]["untested_files"].append(match.group(1))
        if match:
            summary_data[file_name]["all_data"].append((match.group(1), status))
def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)  # Read a portion of the file
    result = chardet.detect(raw_data)
    return result['encoding']

def extract_log_data(file_name, status):
    extracted_data = []
    for log_file_path in log_file_paths:
        encoding = detect_encoding(log_file_path)  # Detect encoding dynamically
        with open(log_file_path, 'r', encoding=encoding, errors='replace') as log_file:
            log_lines = log_file.readlines()
        start_pattern = f'# loadmon {file_name}'
        end_pattern = f'# {status}: {file_name}'
        extracting = False
        for log_line in log_lines:
            if start_pattern in log_line:
                extracting = True
            if extracting:
                extracted_data.append(log_line)
            if end_pattern in log_line and extracting:
                break
    return ''.join(extracted_data)
    
# Generate HTML content for each .sum file's data
summary_html_rows = ""
all_data_html_sections = ""

# Initialize totals for each status
total_files = 0
total_passes = 0
total_failures = 0
total_unresolved = 0
total_untested = 0

for file_name, data in summary_data.items():
    total_sh_files = len(data["passes_files"]) + len(data["failures_files"]) + len(data["unresolved_files"]) + len(data["untested_files"])

    # Update the overall totals
    total_files += total_sh_files
    total_passes += data["expected_passes"]
    total_failures += data["unexpected_failures"]
    total_unresolved += data["unresolved_testcases"]
    total_untested += data["untested_testcases"]

    # Calculate percentages
    pass_percentage = (data["expected_passes"] / total_sh_files) * 100 if total_sh_files > 0 else 0
    fail_percentage = (data["unexpected_failures"] / total_sh_files) * 100 if total_sh_files > 0 else 0
    unresolved_percentage = (data["unresolved_testcases"] / total_sh_files) * 100 if total_sh_files > 0 else 0
    untested_percentage = (data["untested_testcases"] / total_sh_files) * 100 if total_sh_files > 0 else 0

    
    # Generate the data for the new HTML sections with clickable statuses to toggle visibility
    all_data_html = ''.join(
        f'<tr><td><a href="javascript:void(0);" onclick="openLogWindow(\'{file.replace("/tmp/", "")}_{status}\', \'{file}\')">{file}</a></td><td style="background-color: {"green" if status == "PASS" else "red" if status == "FAIL" else "orange"}; color: white; cursor: pointer;" onclick="openLogWindow(\'{file.replace("/tmp/", "")}_{status}\', \'{file}\')">{status}</td></tr>'
        for file, status in data["all_data"]
    )

    # Generate HTML content for the log data sections
    log_data_html_sections = ''.join(
        f'<div id="{file.replace("/tmp/", "")}_{status}" class="hidden log-section"><h3>{file} - {status}</h3><pre>{extract_log_data(file, status)}</pre></div>'
        for file, status in data["all_data"])

    summary_html_rows += f"""
    <tr>
        <td><b>{file_name}</b></td>
        <td>{total_sh_files}</td>
        <td>{data["expected_passes"]}</td>
        <td>{data["unexpected_failures"]}</td>
        <td>{data["unresolved_testcases"]}</td>
        <td>{data["untested_testcases"]}</td>
        <td>{pass_percentage:.2f}%</td>
        <td>{fail_percentage:.2f}%</td>
        <td>{unresolved_percentage:.2f}%</td>
        <td>{untested_percentage:.2f}%</td>
        <td><a href="javascript:void(0);" onclick="toggleSection('{file_name}_allDataSection')" style="font-weight: bold;"><i>Log</i></a></td>
    </tr>
    <tr id="{file_name}_allDataSection" class="hidden">
        <td colspan="11">
            <table>
                <tr><th>Files</th><th>Status</th></tr>
                {all_data_html}
            </table>
            {log_data_html_sections}
        </td>
    </tr>
    """
# Calculate overall percentages
total_pass_percentage = (total_passes / total_files) * 100 if total_files > 0 else 0
total_fail_percentage = (total_failures / total_files) * 100 if total_files > 0 else 0
total_unresolved_percentage = (total_unresolved / total_files) * 100 if total_files > 0 else 0
total_untested_percentage = (total_untested / total_files) * 100 if total_files > 0 else 0

# Add the totals row
summary_html_rows += f"""
<tr style="font-weight: bold; background-color: #f0f0f0;">
    <td>Total</td>
    <td>{total_files}</td>
    <td>{total_passes}</td>
    <td>{total_failures}</td>
    <td>{total_unresolved}</td>
    <td>{total_untested}</td>
    <td>{total_pass_percentage:.2f}%</td>
    <td>{total_fail_percentage:.2f}%</td>
    <td>{total_unresolved_percentage:.2f}%</td>
    <td>{total_untested_percentage:.2f}%</td>
    <td></td>
</tr>
"""

output_file_name = os.path.basename(current_dir) + '.html'
output_file_path = os.path.join(current_dir, output_file_name)

# Get the last word of the current directory path for the title and heading
page_title = os.path.basename(current_dir)

# Read BSP_NAME from common.mk
bsp_name = "Unknown BSP : Add BSP_Name in common.mk"
common_mk_path = os.path.join(current_dir, 'common.mk')
if os.path.exists(common_mk_path):
    with open(common_mk_path, 'r') as common_mk_file:
        for line in common_mk_file:
            if line.startswith('BSP_Name'):
                bsp_name = line.split('=')[1].strip()
                break

html_content = f"""
<html>
<head>
    <meta charset="UTF-8">
    <title>{page_title}</title>
    <style>
        body {{ background-color: white; }} 
        table {{ width: 50%; border-collapse: collapse; }}
        table, th, td {{ border: 0.5px solid black; }}
        th, td {{ padding: 15px; text-align: left; }}
        .hidden {{ display: none; }}
        a {{ color: blue; text-decoration: none; font-weight: bold; }}
        h2 {{ text-align: center; font-size: 2.5em; text-decoration: underline; }}
        .info {{ text-align: left; margin-bottom: 20px; }}
        tr:first-child {{ background-color: white; }} 
    </style>
    <script>
        function toggleSection(sectionId) {{
            var section = document.getElementById(sectionId);
            if (section.classList.contains('hidden')) {{
                section.classList.remove('hidden');
            }} else {{
                section.classList.add('hidden');
            }}
        }}
        function openLogWindow(sectionId, fileName) {{
            var section = document.getElementById(sectionId);
            var logContent = section.innerHTML;
            var newWindow = window.open("", "_blank");
            newWindow.document.write("<html><head><title>" + fileName + "</title></head><body>" + logContent + "</body></html>");
        }}
    </script>
</head>
<body>
    <div>
        <h2>BSP TEST REPORT</h2>
        <div class="info">
            <p><b>BSP Name:</b> {bsp_name}</p>
            <p><b>Target Name:</b> {page_title}</p>
            <p><b>Architecture:</b> {architecture}</p>
        </div>
        <table>
            <tr>
                <th rowspan="1">Component</th>
                <th colspan="5">Test Executions</th>
                <th colspan="4">Percentages</th>
            </tr>
            <tr>
                <th>MODULE</th>
                <th>TOTAL</th>
                <th>PASSES</th>
                <th>FAILURES</th>
                <th>BLOCKED</th>
                <th>NOT EXECUTED</th>
                <th>PASS%</th>
                <th>FAIL%</th>
                <th>BLOCKED%</th>
                <th>NOT EXECUTED%</th>
                <th>SUMMARY</th>
            </tr>
            {summary_html_rows}
        </table>
    </div>
</body>
</html>
"""

# Write the main HTML content to a file
with open(output_file_path, 'w') as output_file:
    output_file.write(html_content)

# Start a simple HTTP server with automatic port selection
Handler = http.server.SimpleHTTPRequestHandler
# Change the directory to the location of the HTML files
os.chdir(current_dir)

def find_free_port():
    with socketserver.TCPServer(("localhost", 0), Handler) as s:
        return s.server_address[1]

PORT = find_free_port()

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at port {PORT}")
    webbrowser.open(f'http://localhost:{PORT}/{output_file_name}')
    httpd.serve_forever()
