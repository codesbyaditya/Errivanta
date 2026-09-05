# User Service (ServiceWatch Ecosystem)

A lightweight user management microservice configured with the ServiceWatch monitoring SDK.

## Features
- **FastAPI** REST endpoints (`POST /users`, `GET /users`, `GET /users/{id}`)
- **Failure Simulation** (`POST /users/simulate-failure`)
- **ServiceWatch SDK Integration**: Automatically reports requests, latencies, and 500 errors to `monitoring-api`.
