```
docker build --tag="local/cdd-shim" .
docker run -d -p 80:80 -m 128m \
    -v=/home/pjay/git/cdd-shim/output:/output:rw \
    --restart=always \
    --name=cdd-shim local/cdd-shim \
    python /opt/cdd-shim/cdd-shim.py \
        "-p 80" \
        "-o /output"
```
