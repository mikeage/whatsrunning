FROM python:3.12-alpine

# Set the working directory inside the container
WORKDIR /app

# Install the required dependencies
RUN pip install --no-cache-dir flask docker aiohttp gunicorn

# Copy the current directory contents into the container at /app
COPY . /app

EXPOSE 5000

ARG VERSION

ENV VERSION=${VERSION}

CMD ["gunicorn", "main:app", "-b", "0.0.0.0:5000", "--access-logfile=-", "--error-logfile=-"]
