# pylint: disable=missing-module-docstring,missing-function-docstring
import os
import logging
import requests

import docker
from flask import Flask, render_template_string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Docker client
client = docker.DockerClient(
    base_url=os.getenv("DOCKER_HOST", "unix://var/run/docker.sock")
)


def check_port_protocol(host, port):
    try:
        response = requests.get(f"http://{host}:{port}", timeout=5)
        if response.status_code:
            return "http"
    except requests.RequestException:
        pass

    try:
        response = requests.get(f"https://{host}:{port}", verify=False, timeout=5)
        if response.status_code:
            return "https"
    except requests.RequestException:
        pass

    return None


@app.route("/")
def list_ports():
    # Get the ID of the current container
    current_container_id = os.getenv("HOSTNAME")
    hostname = os.getenv("HOST_HOSTNAME")
    arg_version = os.getenv("VERSION", "unknown")
    logger.info("Running as container ID: %s on %s", current_container_id, hostname)
    containers = client.containers.list()

    html_template = """
    <html>
    <head><title>Running Containers</title></head>
    <body>
        <h1>Exposed Ports for Running Containers</h1>
        {% for container in containers %}
            <h2>{{ container.name }}</h2>
            <ul>
            {% for (prefix, port) in container.ports %}
                <li><a href="{{ prefix }}://{{ hostname }}:{{ port }}">{{ container.name }}:{{ port }}</a></li>
            {% endfor %}
            </ul>
        {% endfor %}
        </ul>
        <p>Version: {{ arg_version }}</p>
    </body>
    </html>
    """

    container_data = []
    for container in sorted(containers, key=lambda c: c.name):
        if current_container_id and container.id.startswith(current_container_id):
            continue  # Skip the current container

        # Get exposed ports (if any) in the format host_port
        ports = []
        if container.attrs["NetworkSettings"]["Ports"]:
            for name, value in container.attrs["NetworkSettings"]["Ports"].items():
                if not name.endswith("/tcp"):
                    continue
                candidate_ports = {v["HostPort"] for v in value if "HostPort" in v}
                for port in candidate_ports:
                    protocol = check_port_protocol(hostname, port)
                    if protocol and protocol in ["http", "https"]:
                        ports.append((protocol, port))

        if ports:
            container_data.append({"name": container.name, "ports": ports})

    return render_template_string(
        html_template,
        containers=container_data,
        hostname=hostname,
        arg_version=arg_version,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", "5000")))
