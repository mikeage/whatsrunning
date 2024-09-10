FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Install the required dependencies
RUN pip install --no-cache-dir flask docker aiohttp

# Copy the current directory contents into the container at /app
COPY . /app

EXPOSE 5000

ARG VERSION

ENV VERSION=${VERSION}

CMD ["python", "-u", "main.py"]
