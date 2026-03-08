# Barcode_scanner

## 1. Generate certificates
```
./generate_cert.sh
```

If the script is not executable, run:
```
chmod +x generate_cert.sh
```


## 2. Run the Docker container
```
docker compose up -d
```

To run in development mode instead, run:
```
source venv/bin/activate
python3 app.py
```



## 3. View the website

When running the application in a Docker container, the website is accessible via ```localhost``` or ```127.0.0.1``` on your local machine. If the container is deployed on a remote server, use the server's IP address instead
