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
