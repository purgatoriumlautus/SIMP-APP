import subprocess

# Define the commands to run in each terminal
commands = [
    'python .\\simp_daemon.py 127.0.0.1',
    'python .\\simp_daemon.py 127.0.0.2',
    'python .\\simp_client.py 127.0.0.1',
    'python .\\simp_client.py 127.0.0.2'
]

# Open a new terminal for each command
for cmd in commands:
    subprocess.Popen(['start', 'cmd', '/k', cmd], shell=True)