# Contributing to WGDashboard

## Development Setup

### Prerequisites

- Node.js >= 18.0.0
- npm >= 9.0.0
- Python 3.x (for backend)

### Installing Dependencies

WGDashboard uses npm workspaces to manage multiple frontend applications. To install all dependencies:

```bash
# Install all dependencies for both app and client
npm install
```

This will install dependencies for:
- Root package management
- `src/static/app` - Main dashboard application
- `src/static/client` - Client application

### Building the Frontend

#### Build all frontend applications
```bash
npm run build
```

#### Build individual applications
```bash
# Build the main dashboard app
npm run build:app

# Build the client application
npm run build:client
```

### Development Mode

#### Run development servers
```bash
# Start the main dashboard app dev server
npm run dev:app

# Start the client app dev server
npm run dev:client
```

### Preview Built Applications

```bash
# Preview the main dashboard app
npm run preview:app

# Preview the client application
npm run preview:client
```

## Project Structure

```
WGDashboard/
├── src/
│   ├── static/
│   │   ├── app/          # Main dashboard (Vue 3 + Vite)
│   │   │   ├── package.json
│   │   │   └── ...
│   │   └── client/       # Client application (Vue 3 + Vite)
│   │       ├── package.json
│   │       └── ...
│   └── ...
├── package.json          # Root package for workspace management
└── ...
```

## Working with Workspaces

Each frontend application is a separate npm workspace. You can:

- Install a dependency in a specific workspace:
  ```bash
  npm install <package-name> --workspace=src/static/app
  ```

- Run scripts in a specific workspace:
  ```bash
  npm run <script-name> --workspace=src/static/app
  ```

- List all workspaces:
  ```bash
  npm ls --workspaces --depth=0
  ```

## Backend Development

The backend is built with Python. See the main README.md for Python/backend setup instructions.
