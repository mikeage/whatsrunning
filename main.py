# pylint: disable=missing-module-docstring,missing-function-docstring
import os
import logging
import asyncio
import aiohttp

import docker
from flask import Flask, render_template_string, request

if os.getenv("VERBOSE"):
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

CLIENT = docker.DockerClient(
    base_url=os.getenv("DOCKER_HOST", "unix://var/run/docker.sock")
)

CURRENT_CONTAINER_ID = os.getenv("HOSTNAME")
HOSTNAME = os.getenv("HOST_HOSTNAME")
VERSION = os.getenv("VERSION", "unknown")

LOGGER.info(
    "Running as container ID: %s on external host %s",
    CURRENT_CONTAINER_ID,
    HOSTNAME,
)

app = Flask(__name__)


async def check_port_protocol(hostname, port):
    async with aiohttp.ClientSession() as session:
        for protocol in ["http", "https"]:
            url = f"{protocol}://{hostname}:{port}"
            headers = {"x-whatsrunning-probe": "true"}
            try:
                async with session.get(
                    url, allow_redirects=False, headers=headers, timeout=2
                ) as response:
                    LOGGER.debug("url %s returned %s", url, response.status)
                    return protocol
            except aiohttp.ClientError:
                pass
            except asyncio.TimeoutError:
                LOGGER.warning("Timeout waiting for %s", url)

    return None


async def process_container(container, hostname, current_container_id):
    LOGGER.debug("Processing container %s", container.name)

    response = None

    if current_container_id and container.id.startswith(current_container_id):
        LOGGER.debug("Skipping (current) container %s", container.name)
        return None  # Skip the current container

    ports = []
    if container.attrs["NetworkSettings"]["Ports"]:
        # Gather ports that are published via TCP
        for name, value in container.attrs["NetworkSettings"]["Ports"].items():
            if not name.endswith("/tcp"):
                continue
            if not value:
                continue
            candidate_ports = {v["HostPort"] for v in value if "HostPort" in v}

            LOGGER.debug(
                "Container %s has published ports %s", container.name, candidate_ports
            )

            check_protocol_tasks = [
                check_port_protocol(hostname, port) for port in candidate_ports
            ]
            protocols = await asyncio.gather(*check_protocol_tasks)

            for port, protocol in zip(candidate_ports, protocols):
                if protocol and protocol in ["http", "https"]:
                    ports.append((protocol, port))

    if ports:
        response = {"name": container.name, "ports": ports}

    LOGGER.debug("For container %s, found %s", container.name, response)

    return response


async def process_containers(containers, hostname, current_container_id):
    tasks = [
        process_container(container, hostname, current_container_id)
        for container in sorted(containers, key=lambda c: c.name)
    ]

    # Run all tasks concurrently and filter out None results
    results = await asyncio.gather(*tasks)
    container_data = [result for result in results if result]

    return container_data


@app.route("/about")
def about():
    return f"Version: {VERSION}"


@app.route("/")
def list_ports():
    if request.headers.get("x-whatsrunning-probe"):
        LOGGER.debug("Ignoring probe request")
        return "Alive"

    containers = CLIENT.containers.list()

    html_template = """
    <html>
    <head><title>Running Containers</title></head>
    <body>
        <h1>Published Ports for Running Containers</h1>
        {% for container in containers %}
            <h2>{{ container.name }}</h2>
            <ul>
            {% for (prefix, port) in container.ports %}
                <li><a href="{{ prefix }}://{{ hostname }}:{{ port }}">{{ prefix }}://{{ hostname }}:{{ port }}</a></li>
            {% endfor %}
            </ul>
        {% endfor %}
        </ul>
        <p>Version: {{ app_version }}</p>
    </body>
    </html>
    """

    container_data = asyncio.run(
        process_containers(containers, HOSTNAME, CURRENT_CONTAINER_ID)
    )

    return render_template_string(
        html_template,
        containers=container_data,
        hostname=HOSTNAME,
        app_version=VERSION,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", "5000")))
