from flask import Flask, render_template, request, Response
import subprocess

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/subprocess', methods=['POST'])
def execute():
    def generate():
        process = subprocess.Popen(['ping', '-t', 'google.com'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in iter(process.stdout.readline, ''):
            yield line
    return Response(generate(), mimetype='text/plain')

if __name__ == '__main__':
    app.run(debug=True)
