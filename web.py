
import argparse
from web import create_app

app = create_app()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile dashboard web server")
    parser.add_argument("--port", type=int, default=1234, help="Port (default: 1234)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (default: 127.0.0.1)")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=False)
