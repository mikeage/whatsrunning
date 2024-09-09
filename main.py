# pylint: disable=missing-module-docstring,missing-function-docstring
import os
import logging

import docker
from flask import Flask, render_template_string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Docker client
client = docker.DockerClient(base_url="unix://var/run/docker.sock")


@app.route("/")
def list_ports():
    # Get the ID of the current container
    current_container_id = os.getenv("HOSTNAME")
    hostname = os.getenv("HOST_HOSTNAME")
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
            {% for port in container.ports %}
                <li><a href="http://{{ hostname }}:{{ port }}">{{ container.name }}:{{ port }}</a></li>
            {% endfor %}
            </ul>
        {% endfor %}
        </ul>
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
            for _, value in container.attrs["NetworkSettings"]["Ports"].items():
                if value and "HostPort" in value[0]:
                    ports.append(value[0]["HostPort"])

        if ports:
            container_data.append({"name": container.name, "ports": ports})

    return render_template_string(
        html_template, containers=container_data, hostname=hostname
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
