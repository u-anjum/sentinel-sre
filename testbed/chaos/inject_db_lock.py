import time
import threading
import urllib.request
import urllib.error
import psycopg

DB_URL = "postgresql://app:app@localhost:5433/store"

def hold_lock():
    with psycopg.connect(DB_URL, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM inventory WHERE sku = 'SKU-00001' FOR UPDATE;")
            print(f"[CHAOS] Row lock acquired on SKU-00001 (backend PID: {conn.info.backend_pid}). Holding for 90s...")
            time.sleep(90)

def hammer_api():
    time.sleep(2)
    for i in range(15):
        try:
            req = urllib.request.Request("http://localhost:8001/orders?sku=SKU-00001&qty=1", method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"[TRAFFIC] Request {i+1} failed as expected: {e}")

        time.sleep(1)

if __name__ == "__main__":
    t1 = threading.Thread(target=hold_lock, daemon=True)
    t2 = threading.Thread(target=hammer_api, daemon=True)
    t1.start()
    t2.start()
    t1.join()