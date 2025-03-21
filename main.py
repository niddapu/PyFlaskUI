from flask import Flask, render_template, request, Response
import subprocess

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('main/index.html')

@app.route('/subprocess', methods=['POST'])
def execute():
    def generate():
        user_input = request.form.get('url', 'google.com')
        
        if not user_input.replace('.', '').isalnum():  
            return "Invalid input", 400

        cmd = ["ping", "-n", "4", user_input] if subprocess.os.name == "nt" else ["ping", "-c", "4", user_input]

        process = subprocess.Popen(['ping', '-t', 'google.com'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(process.stdout.readline, ''):
            yield line
    return Response(generate(), mimetype='text/plain')

@app.route('/execute', methods=['POST'])
def execute_script():
    try:
        user_input = [request.form.get('fname'), request.form.get('lname')]  # Add many inputs
        result = subprocess.run(['python', 'src/execute/script.py'] + user_input, capture_output=True, text=True)
        return render_template('execute/result.html', output=result.stdout, error=result.stderr)
    except Exception as e:
        return {'error': str(e)}
    
@app.route('/list', methods=['POST'])
def execute_list():
    try:
        # user_input = [request.form.get('fname'), request.form.get('lname')]  # Add many inputs
        result = subprocess.run(['python', 'src/execute/list.py'], capture_output=True, text=True)
        return render_template('execute/result.html', output=result.stdout, error=result.stderr)
    except Exception as e:
        return {'error': str(e)}
    
@app.route('/dbx-job-list', methods=['POST'])
def execute_dbx_job_list():
    try:
        # user_input = [request.form.get('fname'), request.form.get('lname')]  # Add many inputs
        result = subprocess.run(['python', 'src/tds/dbx-job-list.py'], capture_output=True, text=True)
        return render_template('tds/result.html', output=result.stdout, error=result.stderr)
    except Exception as e:
        return {'error': str(e)}
    

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

