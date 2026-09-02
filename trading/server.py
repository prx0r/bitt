"""TAO Trading API — serves subnet data from oracle.db."""
import sqlite3
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler

DB_PATH = "/root/bitt/oracle.db"

class TradingAPI(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/subnets':
            self.serve_subnets()
        elif self.path == '/api/subnet':
            self.serve_subnets()
        else:
            self.send_error(404)

    def serve_subnets(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            'SELECT data FROM subnet_snapshots WHERE scanned_at = (SELECT MAX(scanned_at) FROM subnet_snapshots)'
        ).fetchall()
        
        subs = []
        for row in rows:
            data = json.loads(row['data'])
            subs.append({
                "netuid": data.get("netuid", 0),
                "name": data.get("name", f"SN{data.get('netuid', 0)}"),
                "alpha_price": data.get("alpha_price", 0),
                "tao_equiv_day": data.get("tao_equiv_day", 0),
                "neuron_count": data.get("neuron_count", 0),
                "active_count": data.get("active_count", 0),
                "hhi": data.get("hhi", 0),
                "tempo": data.get("tempo", 0),
            })
        
        conn.close()
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(subs).encode())

    def log_message(self, format, *args):
        pass  # Suppress logging

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8081), TradingAPI)
    print('TAO Trading API running on http://localhost:8081')
    server.serve_forever()
