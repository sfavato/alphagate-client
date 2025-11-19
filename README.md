# AlphaGate Client

The AlphaGate Client is a secure and robust application designed to act as a "black box" for executing trading signals on the Bitget exchange. It is distributed as a Docker image and is designed to be run by end-users without exposing the internal logic of the trading strategy.

## Features

- **Secure Webhook:** A single `POST /webhook` endpoint for receiving and processing trading signals.
- **HMAC Signature Validation:** All incoming requests are verified using HMAC-SHA256 signatures to ensure their authenticity.
- **Discreet Logging:** Logging is intentionally minimal to prevent the exposure of sensitive information from the trading signals.
- **Multi-Architecture Docker Image:** The application is containerized using a multi-architecture Dockerfile, supporting both `linux/amd64` and `linux/arm64` platforms.

## Security

The AlphaGate Client is designed with security as a top priority. The following security measures are in place:

- **No Hardcoded Secrets:** There are no API keys or other secrets hardcoded in the source code.
- **Environment Variables:** All secrets are loaded from environment variables at runtime. The application will fail to start if any of the required environment variables are missing.

### Required Environment Variables

The following environment variables must be set before running the application:

- `BITGET_API_KEY`: Your Bitget API key.
- `BITGET_SECRET_KEY`: Your Bitget secret key.
- `BITGET_PASSPHRASE`: Your Bitget API passphrase.
- `ALPHAGATE_HMAC_SECRET`: The shared secret used to verify the authenticity of incoming webhook requests.

## Getting Started

To get started with the AlphaGate Client, you will need to have Docker installed on your system.

### Building the Docker Image

To build the Docker image, run the following command from the root of the project directory:

```bash
docker build -t alphagate-client .
```

### Running the Docker Container

To run the Docker container, you will need to provide the required environment variables. You can do this by creating a `.env` file in the root of the project directory with the following content:

```
BITGET_API_KEY=your_api_key
BITGET_SECRET_KEY=your_secret_key
BITGET_PASSPHRASE=your_passphrase
ALPHAGATE_HMAC_SECRET=your_hmac_secret
```

Once you have created the `.env` file, you can run the Docker container with the following command:

```bash
docker run --env-file .env -p 8000:8000 alphagate-client
```

The application will then be running and accessible at `http://localhost:8000`.
