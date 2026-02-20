# 1. Use a lightweight Python base image
FROM python:3.11-slim

# 2. Install OpenSSL in the Linux container
RUN apt-get update && apt-get install -y openssl && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory
WORKDIR /app

# 4. Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy your project files
COPY . .

# 6. GENERATE THE SSL CERTIFICATES AUTOMATICALLY
# The -subj flag fills in the required details silently so the build doesn't freeze
RUN openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj "/C=DK/ST=Nordjylland/L=Aalborg/O=AAU/CN=aau-rental"

# 7. Expose the port
EXPOSE 5000

# 8. Start Gunicorn with the newly generated certificates
CMD ["gunicorn", "--certfile=cert.pem", "--keyfile=key.pem", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
