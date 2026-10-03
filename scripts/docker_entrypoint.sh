#!/usr/bin/env bash
set -eo pipefail

MODE="${1:-all}"

if [ "$MODE" = "backend" ]; then
    echo "Starting FastAPI backend on ${API_HOST:-0.0.0.0}:${API_PORT:-8001}..."
    exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8001}"

elif [ "$MODE" = "frontend" ]; then
    echo "Starting Streamlit frontend on port 8501..."
    exec streamlit run frontend/streamlit_app.py --server.port 8501 --server.address 0.0.0.0

elif [ "$MODE" = "all" ]; then
    echo "Starting both FastAPI backend and Streamlit frontend in container..."
    
    # Start backend in background
    uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8001}" &
    BACKEND_PID=$!
    
    # Wait for backend health check
    echo "Waiting for backend to be ready..."
    for i in {1..30}; do
        if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${API_PORT:-8001}/health')" 2>/dev/null; then
            echo "Backend is ready!"
            break
        fi
        sleep 1
    done
    
    # Start frontend in foreground
    streamlit run frontend/streamlit_app.py --server.port 8501 --server.address 0.0.0.0 &
    FRONTEND_PID=$!
    
    # Trap SIGTERM / SIGINT and forward to child processes
    trap "kill -TERM $BACKEND_PID $FRONTEND_PID 2>/dev/null; wait" SIGTERM SIGINT
    
    wait -n
    exit $?

else
    exec "$@"
fi
