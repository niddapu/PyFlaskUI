from flask import Flask, render_template, request
import subprocess

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('main/index.html')

@app.route('/execute', methods=['POST'])
def execute_script():
    try:
        user_input = [request.form.get('fname'), request.form.get('lname')]  # Add many inputs
        print(user_input)
        result = subprocess.run(['python', 'src/script.py'] + user_input, capture_output=True, text=True)
        return render_template('result/result.html', output=result.stdout, error=result.stderr)
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

