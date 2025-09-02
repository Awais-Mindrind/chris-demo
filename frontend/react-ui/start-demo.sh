#!/bin/bash

# Start Demo Script for Sales Quote Assistant
echo "🚀 Starting Sales Quote Assistant Demo..."

# Check if backend is running
if ! curl -s http://localhost:8000/healthz > /dev/null; then
    echo "❌ Backend server is not running on localhost:8000"
    echo "Please start the backend server first:"
    echo "  cd /Users/macbookpro/Desktop/chris-demo"
    echo "  uvicorn app.main:app --reload --port 8000"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "✅ Backend server is running"

# Start React development server
echo "🎨 Starting React UI..."
echo "📱 React app will be available at: http://localhost:5173"
echo "🔗 Backend API is available at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the demo"

npm run dev
