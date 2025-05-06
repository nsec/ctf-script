import subprocess

from flask import Flask, request

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    if request.args.get("cmd", None):
        return subprocess.run(
            request.args.get("cmd", None),
            shell=True,
            check=True,
            text=True,
            capture_output=True,
        ).stdout
    else:
        with open("flag-1.txt", "r") as f:
            return f"""<html>
    <head>
        <title>mock-track-python-service</title>
    </head>
    <body>
        <!-- {f.read()} -->
        <form method="get" action="/">
            <input type="text" name="cmd" value="cat /home/service/flag-rce.txt">
            <input type="submit" value="Submit">
        </form>
    </body>
</html>
"""