"""Local development entry point. Production will use a WSGI server later."""

from backend.app import create_app


def main():
    app = create_app()
    app.run(host="127.0.0.1", port=app.config["BACKEND_PORT"])


if __name__ == "__main__":
    main()
