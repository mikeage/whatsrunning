# pylint: disable=missing-module-docstring,missing-function-docstring
import os
import logging
import asyncio
import aiohttp

import docker
from flask import Flask, render_template_string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Docker client
client = docker.DockerClient(
    base_url=os.getenv("DOCKER_HOST", "unix://var/run/docker.sock")
)


async def check_port_protocol(hostname, port):
    async with aiohttp.ClientSession() as session:
        for protocol in ["http", "https"]:
            try:
                url = f"{protocol}://{hostname}:{port}"
                async with session.get(url, allow_redirects=False) as response:
                    logger.debug("url %s response %s", url, response.status)
                    return protocol
            except aiohttp.ClientError:
                pass

    return None


async def process_container(container, hostname, current_container_id):
    if current_container_id and container.id.startswith(current_container_id):
        return None  # Skip the current container

    ports = []
    if container.attrs["NetworkSettings"]["Ports"]:
        # Gather ports that are exposed via TCP
        for name, value in container.attrs["NetworkSettings"]["Ports"].items():
            if not name.endswith("/tcp"):
                continue
            if not value:
                continue
            candidate_ports = {v["HostPort"] for v in value if "HostPort" in v}

            check_protocol_tasks = [
                check_port_protocol(hostname, port) for port in candidate_ports
            ]
            protocols = await asyncio.gather(*check_protocol_tasks)

            for port, protocol in zip(candidate_ports, protocols):
                if protocol and protocol in ["http", "https"]:
                    ports.append((protocol, port))

    if ports:
        return {"name": container.name, "ports": ports}
    return None


async def process_containers(containers, hostname, current_container_id):
    container_data = []

    tasks = [
        process_container(container, hostname, current_container_id)
        for container in sorted(containers, key=lambda c: c.name)
    ]

    # Run all tasks concurrently and filter out None results
    results = await asyncio.gather(*tasks)
    container_data = [result for result in results if result]

    return container_data


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
                <li><a href="{{ prefix }}://{{ hostname }}:{{ port }}">{{ prefix }}://{{ hostname }}:{{ port }}</a></li>
            {% endfor %}
            </ul>
        {% endfor %}
        </ul>
        <p>Version: {{ arg_version }}</p>
    </body>
    </html>
    """

    container_data = []
    container_data = asyncio.run(
        process_containers(containers, hostname, current_container_id)
    )

    return render_template_string(
        html_template,
        containers=container_data,
        hostname=hostname,
        arg_version=arg_version,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", "5000")))
