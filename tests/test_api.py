import urllib.request
import urllib.error
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def test_endpoint(path, method="GET", payload=None):
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode('utf-8') if payload else None
    headers = {"Content-Type": "application/json"} if payload else {}
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=2.0) as response:
            status = response.getcode()
            body = json.loads(response.read().decode('utf-8'))
            print(f"✅ {method} {path} - Status: {status}")
            return body
    except urllib.error.HTTPError as e:
        print(f"❌ {method} {path} - Failed with status {e.code}")
        print(e.read().decode('utf-8'))
        sys.exit(1)
    except Exception as e:
        print(f"❌ {method} {path} - Connection error: {e}")
        sys.exit(1)

def run_tests():
    print("⏳ Waiting for backend server to boot...")
    time.sleep(2)
    
    # 1. Health check
    test_endpoint("/health")
    
    # 2. Ingest mock event
    event_payload = {
        "eventId": "e932b130-1c39-44d4-9d51-4099496a798f",
        "eventType": "STORE_ENTRY",
        "timestamp": "2026-06-01T23:15:00",
        "customerId": "81a1795c-9c59-450f-90db-33cb397bdf01",
        "zoneName": "Entrance",
        "x": 150.0,
        "y": 600.0,
        "metadata": {"test": True}
    }
    test_endpoint("/events/ingest", method="POST", payload=event_payload)
    
    # 3. Fetch metrics
    metrics = test_endpoint("/metrics")
    assert "todayFootfall" in metrics, "Missing todayFootfall in metrics"
    
    # 4. Fetch funnel
    funnel = test_endpoint("/funnel")
    assert "stages" in funnel, "Missing stages in funnel"
    
    # 5. Fetch heatmap
    test_endpoint("/heatmap")
    
    # 6. Fetch anomalies
    test_endpoint("/anomalies")
    
    print("\n🎉 ALL FastAPI ENDPOINT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
