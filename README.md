# Show exposed ports from all docker containers

Running this Flask application will serve a webpage showing all exposed TCP ports from all running docker containers, with hyperlinks to connect to them via HTTP.

I use this as a form of automatically updating home lab dashboard, so I can quickly connect to anything I'm running.

Normally, obviously, I use a proper reverse proxy. This is strictly for finding those things that I don't expose, and can never remember which port they use (*arr, looking at you here!).

## Usage

```bash
HOSTNAME=$(hostname -f) docker compose up -d  # Note that without the `HOSTNAME` environment variable, the application will not be able to generate the correct URLs to connect to the exposed ports.
```

Then visit http://localhost:80/ to see the list of exposed ports.
